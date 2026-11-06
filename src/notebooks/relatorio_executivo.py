# Databricks notebook source
"""Relatório executivo baseado exclusivamente em tabelas e métricas Gold."""

import json
import re


def validar_identificador(valor):
    """Aceita somente nomes simples antes de interpolar identificadores SQL."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", valor):
        raise ValueError("Catálogo e schema devem conter apenas letras, números e sublinhados")
    return valor


def formatar_valor(valor, casas=2):
    """Formata uma medida para apresentação e evidencia valores indisponíveis."""
    return "indisponível" if valor is None else f"{float(valor):.{casas}f}"


def montar_relatorio(regiao, data, operacao, metricas, bairros, clientes, amostra_clientes=None):
    """Constrói uma narrativa determinística a partir dos resultados agregados."""
    operacoes = []
    impactos = []
    for linha in operacao:
        nome = linha["nome_conjunto"]
        medida = metricas.get(nome, {})
        duracao = ("sem interrupção" if linha["maior_duracao_horas"] is None
                   else f"{formatar_valor(linha['maior_duracao_horas'])} h")
        causa = linha["causa_predominante"] or "sem evento"
        operacoes.append(
            f"{nome}: {linha['qtd_interrupcoes']} interrupções, "
            f"{formatar_valor(linha['uc_horas_interrompidas'])} horas-UC, maior duração {duracao}, "
            f"causa predominante {causa}; {linha['qtd_chamados']} chamados "
            f"ante média diária anterior de {formatar_valor(linha['media_chamados_30_dias'])}; "
            f"{linha['chamados_negativos']} negativos e {linha['chamados_risco_saude']} com sinal de risco à saúde."
        )
        impactos.append(
            f"{nome}: consumo {formatar_valor(linha['consumo_kwh'])} kWh; "
            f"DEC mensal {formatar_valor(medida.get('dec_horas'))} h e FEC mensal "
            f"{formatar_valor(medida.get('fec'))}; {linha['mencoes_ouvidoria']} menções à ouvidoria."
        )
    linhas = [f"O que aconteceu — {regiao}, {data}.", *operacoes, "Impacto em números —", *impactos]
    linhas.append("O que precisa de ação — " + "; ".join(
        f"{linha['nome_conjunto']}: {linha['acao_recomendada']}" for linha in operacao
    ) + ".")
    linhas.append("Prioridade alta para visita por bairro: " + (
        "; ".join(f"{linha['bairro']}: {linha['total']} UCs" for linha in bairros) or "nenhuma UC identificada"
    ) + ".")
    linhas.append(f"Clientes com sinal alto de ouvidoria na fotografia atual: {clientes}.")
    if amostra_clientes:
        linhas.append("Exemplos para acompanhamento: " + ", ".join(amostra_clientes) + ".")
    linhas.append("Prioridade de inspeção é um sinal para visita, não uma conclusão sobre a causa.")
    return "\n".join(linhas)


def gerar_narrativa(spark, relatorio, usar_ia):
    """Solicita redação com IA e aceita somente reprodução exata dos fatos fornecidos."""
    if len(relatorio.split()) > 250:
        raise ValueError("O relatório excede 250 palavras; reduza o escopo da região")
    if re.search(r"\b(?:fraude|furto|roubo|irregularidade)\w*\b", relatorio, flags=re.IGNORECASE):
        raise ValueError("O relatório contém um termo incompatível com a regra de prioridade de inspeção")
    if not usar_ia:
        return relatorio, "gabarito"
    prompt = (
        "Você redige um relatório executivo em português com até 250 palavras. "
        "Use exclusivamente os números fornecidos; não estime, não invente e não altere valores. "
        "UCs com consumo atípico representam prioridade de inspeção, nunca fraude, furto, roubo ou irregularidade. "
        "Reproduza literalmente o relatório abaixo sem acrescentar frases ou mudar sua estrutura em três partes:\n"
        + relatorio
    )
    try:
        resposta = spark.sql("SELECT ai_gen(:prompt) AS texto", args={"prompt": prompt}).first()["texto"]
    except Exception as erro:  # noqa: BLE001 - fallback quando a função remota não estiver disponível
        print(f"Não foi possível usar ai_gen: {type(erro).__name__}")
        return relatorio, "gabarito_ia_indisponivel"
    if isinstance(resposta, str) and re.sub(r"\s+", " ", resposta).strip() == re.sub(r"\s+", " ", relatorio).strip():
        return resposta.strip(), "ia_validada"
    return relatorio, "gabarito_ia_divergente"


def executar_relatorio(spark, catalogo, schema_gold, regiao, usar_ia):
    """Consulta apenas Gold e prepara o relatório para uma região com movimento."""
    catalogo, schema_gold = validar_identificador(catalogo), validar_identificador(schema_gold)
    prefixo = f"`{catalogo}`.`{schema_gold}`"
    painel = f"{prefixo}.painel_operacional_dia"
    data = spark.sql(
        f"SELECT max(dia) AS dia FROM {painel} WHERE qtd_interrupcoes > 0 OR qtd_chamados > 0"
    ).first()["dia"]
    if data is None:
        raise ValueError("Não há movimento no painel Gold. Confira a carga de interrupções e chamados.")
    consulta = f"""
      SELECT p.*, (SELECT avg(h.qtd_chamados) FROM {painel} h
        WHERE h.id_conjunto = p.id_conjunto AND h.dia >= date_sub(p.dia, 30) AND h.dia < p.dia
      ) AS media_chamados_30_dias
      FROM {painel} p WHERE p.dia = :dia AND lower(p.municipio) = lower(:regiao)
      ORDER BY p.nome_conjunto
    """
    operacao = [linha.asDict() for linha in spark.sql(consulta, args={"dia": data, "regiao": regiao}).collect()]
    if not operacao or not any(linha["qtd_interrupcoes"] or linha["qtd_chamados"] for linha in operacao):
        raise ValueError(f"Não há movimento para {regiao} em {data}. Confira a região e as cargas Gold.")
    consulta_metricas = f"""
      SELECT m.`Conjunto` AS nome_conjunto, MEASURE(m.`DEC`) AS dec_horas, MEASURE(m.`FEC`) AS fec
      FROM {prefixo}.continuidade_metricas m
      WHERE m.`Mes` = date_trunc('MONTH', :dia) GROUP BY ALL
    """
    metricas = {linha["nome_conjunto"]: linha.asDict()
                for linha in spark.sql(consulta_metricas, args={"dia": data}).collect()}
    consulta_bairros = f"""
      SELECT p.bairro, count(*) AS total FROM {prefixo}.prioridade_inspecao_uc p
      WHERE p.prioridade_inspecao = 'alta' AND p.id_conjunto IN
        (SELECT DISTINCT id_conjunto FROM {painel} WHERE dia = :dia AND lower(municipio) = lower(:regiao))
      GROUP BY p.bairro ORDER BY total DESC, p.bairro
    """
    bairros = [linha.asDict() for linha in spark.sql(consulta_bairros, args={"dia": data, "regiao": regiao}).collect()]
    consulta_clientes = f"""
      SELECT count(*) AS total FROM {prefixo}.saude_cliente c
      WHERE c.risco_ouvidoria = 'alto' AND c.id_conjunto IN
        (SELECT DISTINCT id_conjunto FROM {painel} WHERE dia = :dia AND lower(municipio) = lower(:regiao))
    """
    clientes = spark.sql(consulta_clientes, args={"dia": data, "regiao": regiao}).first()["total"]
    consulta_amostra = f"""
      SELECT c.id_cliente FROM {prefixo}.saude_cliente c
      WHERE c.risco_ouvidoria = 'alto' AND c.id_conjunto IN
        (SELECT DISTINCT id_conjunto FROM {painel} WHERE dia = :dia AND lower(municipio) = lower(:regiao))
      ORDER BY c.qtd_mencoes_ouvidoria DESC, c.qtd_chamados DESC, c.id_cliente LIMIT 5
    """
    amostra = [linha["id_cliente"] for linha in
               spark.sql(consulta_amostra, args={"dia": data, "regiao": regiao}).collect()]
    base = montar_relatorio(regiao, data, operacao, metricas, bairros, clientes, amostra)
    texto, metodo = gerar_narrativa(spark, base, usar_ia)
    return {"regiao": regiao, "dia": str(data), "metodo": metodo, "relatorio": texto}


if __name__ == "__main__":
    dbutils.widgets.text("catalogo", "")  # noqa: F821
    dbutils.widgets.text("schema_gold", "gold")  # noqa: F821
    dbutils.widgets.text("regiao", "Campinas")  # noqa: F821
    dbutils.widgets.text("usar_ia", "true")  # noqa: F821
    resultado = executar_relatorio(
        spark,  # noqa: F821
        dbutils.widgets.get("catalogo"),  # noqa: F821
        dbutils.widgets.get("schema_gold"),  # noqa: F821
        dbutils.widgets.get("regiao"),  # noqa: F821
        dbutils.widgets.get("usar_ia").lower() == "true",  # noqa: F821
    )
    print(resultado["relatorio"])
    dbutils.notebook.exit(json.dumps(resultado, ensure_ascii=False))  # noqa: F821

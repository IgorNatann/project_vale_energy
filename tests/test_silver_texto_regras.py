import re
import subprocess
from pathlib import Path

import pytest


def consulta_regras(indice):
    """Obtém a consulta real da rota SQL para executá-la com dados de teste."""
    arquivo = (
        Path(__file__).resolve().parents[1]
        / "src/pipelines/grid_intelligence_regras/transformations/13_silver_chamados.sql"
    )
    instrucoes = [parte for parte in arquivo.read_text(encoding="utf-8").split(";") if "CREATE OR REFRESH" in parte]
    return re.split(r"\bAS\s+(?=SELECT\b|WITH\b)", instrucoes[indice], maxsplit=1, flags=re.IGNORECASE)[1].strip()


@pytest.mark.databricks
def test_anonimizacao_por_regras_remove_nome_cpf_e_telefone(consultar):
    """O nome conhecido e os formatos de CPF e telefone são removidos antes da análise."""
    consulta = consulta_regras(0).replace("${catalogo}.${schema_bronze}.chamados", "origem")
    consulta = consulta.replace("${catalogo}.${schema_silver}.unidades_consumidoras", "cadastro")
    resultado = consultar(f"""
      WITH origem(id_chamado, id_uc, abertura, canal, duracao_segundos, origem, ingerido_em,
                  arquivo_origem, ingerido_bronze_em, nome_solicitante, transcricao) AS (
        VALUES ('1', 'UC1', TIMESTAMP'2026-01-01', 'telefone', 1, 'sistema',
          TIMESTAMP'2026-01-01', 'arquivo', TIMESTAMP'2026-01-01', 'Maria Silva',
          'Maria Silva, CPF 123.456.789-09, telefone (11) 98765-4321.')
      ), cadastro(id_uc, id_cliente, id_conjunto, nome_conjunto, bairro, classe_consumo) AS (
        VALUES ('UC1','C1','A','Conjunto','Bairro','residencial')
      ), resultado AS ({consulta})
      SELECT transcricao_anonimizada, anonimizado_por FROM resultado
    """)[0]
    assert all(
        dado not in resultado["transcricao_anonimizada"] for dado in ("Maria Silva", "123.456.789-09", "98765-4321")
    )
    assert resultado["anonimizado_por"] == "regras_de_texto"


@pytest.mark.databricks
def test_anonimizacao_por_regras_em_formatos_sinteticos(consultar):
    """Cobre formatos previstos, nome acentuado e tratamento de texto nulo."""
    consulta = consulta_regras(0).replace("${catalogo}.${schema_bronze}.chamados", "origem")
    consulta = consulta.replace("${catalogo}.${schema_silver}.unidades_consumidoras", "cadastro")
    linhas = consultar(f"""
      WITH origem(id_chamado, id_uc, abertura, canal, duracao_segundos, origem, ingerido_em,
                  arquivo_origem, ingerido_bronze_em, nome_solicitante, transcricao) AS (
        VALUES ('1', 'UC1', TIMESTAMP'2026-01-01', 'telefone', 1, 'sistema', TIMESTAMP'2026-01-01',
                'arquivo', TIMESTAMP'2026-01-01', 'José Ávila', 'José Ávila CPF 12345678909'),
               ('2', 'UC1', TIMESTAMP'2026-01-01', 'telefone', 1, 'sistema', TIMESTAMP'2026-01-01',
                'arquivo', TIMESTAMP'2026-01-01', 'Ana Lima', 'Ana Lima telefone 11 3456-7890'),
               ('3', 'UC1', TIMESTAMP'2026-01-01', 'telefone', 1, 'sistema', TIMESTAMP'2026-01-01',
                'arquivo', TIMESTAMP'2026-01-01', 'Ana Lima', CAST(NULL AS STRING))
      ), cadastro(id_uc, id_cliente, id_conjunto, nome_conjunto, bairro, classe_consumo) AS (
        VALUES ('UC1','C1','A','Conjunto','Bairro','residencial')
      ), resultado AS ({consulta})
      SELECT id_chamado, transcricao_anonimizada FROM resultado ORDER BY id_chamado
    """)
    assert [linha["transcricao_anonimizada"] for linha in linhas] == [
        "[MASCARADO] CPF [MASCARADO]",
        "[MASCARADO] telefone [MASCARADO]",
        "[RESTRITO]",
    ]


@pytest.mark.databricks
def test_classificacao_prioriza_risco_e_usa_somente_texto_anonimizado(consultar):
    """Risco à saúde prevalece sobre falta de energia e pedidos comuns de religação."""
    consulta = consulta_regras(1).replace("${catalogo}.${schema_texto}.chamados_anonimizados", "origem")
    linhas = consultar(f"""
      WITH origem(id_chamado, transcricao_anonimizada) AS (
        VALUES ('1', 'Sem luz, preciso religar porque uso oxigenio.'),
               ('2', 'Sem energia e preciso de atendimento.'),
               ('3', 'Obrigado pelo atendimento.'), ('4', '[RESTRITO]')
      ), resultado AS ({consulta})
      SELECT id_chamado, sentimento, motivo, risco_a_saude IS NULL AS risco_desconhecido, urgencia, enriquecido_por
      FROM resultado ORDER BY id_chamado
    """)
    assert [linha["motivo"] for linha in linhas] == [
        "religacao_urgente",
        "falta_energia",
        "duvida_cadastral",
        "indisponivel",
    ]
    assert [linha["urgencia"] for linha in linhas] == ["alta", "media", "baixa", "indeterminada"]
    assert linhas[2]["sentimento"] == "positive"
    assert str(linhas[3]["risco_desconhecido"]).lower() == "true"
    assert all(linha["enriquecido_por"] == "regras_de_texto" for linha in linhas)


@pytest.mark.databricks
def test_classificacao_em_exemplos_rotulados(consultar):
    """Verifica categorias, prioridade e urgência em exemplos sintéticos revisados."""
    consulta = consulta_regras(1).replace("${catalogo}.${schema_texto}.chamados_anonimizados", "origem")
    linhas = consultar(f"""
      WITH origem(id_chamado, transcricao_anonimizada) AS (
        VALUES ('01', 'Uso oxigênio e estou sem energia.'),
               ('02', 'A tensão oscila e queimou a geladeira.'),
               ('03', 'A leitura não bate com a estimativa.'),
               ('04', 'A conta veio o dobro.'),
               ('05', 'Há um galho no poste.'),
               ('06', 'Paguei e preciso religar.'),
               ('07', 'Obrigado, excelente atendimento.'),
               ('08', 'Absurdo, vou reclamar na ouvidoria.'),
               ('09', '[RESTRITO]')
      ), resultado AS ({consulta})
      SELECT id_chamado, motivo, sentimento, urgencia,
             coalesce(CAST(risco_a_saude AS STRING), 'nulo') AS risco_a_saude,
             coalesce(CAST(ameacou_ouvidoria AS STRING), 'nulo') AS ameacou_ouvidoria
      FROM resultado ORDER BY id_chamado
    """)
    esperados = [
        ("religacao_urgente", "neutral", "alta", True, False),
        ("oscilacao_tensao", "neutral", "baixa", False, False),
        ("erro_leitura", "neutral", "baixa", False, False),
        ("fatura_alta", "neutral", "baixa", False, False),
        ("poste_avariado", "neutral", "media", False, False),
        ("religacao", "neutral", "baixa", False, False),
        ("duvida_cadastral", "positive", "baixa", False, False),
        ("duvida_cadastral", "negative", "baixa", False, True),
        ("indisponivel", "indisponivel", "indeterminada", None, None),
    ]
    chaves = ("motivo", "sentimento", "urgencia", "risco_a_saude", "ameacou_ouvidoria")

    def valor(linha, chave):
        dado = linha[chave]
        if chave in ("risco_a_saude", "ameacou_ouvidoria"):
            return {"true": True, "false": False, "nulo": None}[dado.lower()]
        return dado

    assert [tuple(valor(linha, chave) for chave in chaves) for linha in linhas] == esperados


@pytest.mark.databricks
@pytest.mark.reexecucao
def test_reexecucao_regras_preserva_resultados(consultar, catalogo, perfil):
    """Compara todas as linhas das duas tabelas após atualização sem novas entradas."""
    if catalogo != "grid_dev":
        pytest.fail("A reexecução está restrita ao catálogo grid_dev e ao target dev")

    def estado():
        consultas = [
            f"SELECT '{tabela}' AS tabela, count(*) AS total, "
            "sha2(to_json(sort_array(collect_list(to_json(struct(*))))), 256) AS resumo "
            f"FROM `{catalogo}`.silver_regras.{tabela}"
            for tabela in ("chamados_anonimizados", "chamados_enriquecidos")
        ]
        return consultar(" UNION ALL ".join(consultas) + " ORDER BY tabela")

    antes = estado()
    assert all(int(linha["total"]) > 0 for linha in antes)
    subprocess.run(
        ["databricks", "bundle", "run", "grid_intelligence_regras", "--target", "dev", "--profile", perfil],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=900,
    )
    assert estado() == antes


@pytest.mark.databricks
def test_rotas_publicadas_tem_o_mesmo_contrato(consultar, catalogo):
    """Compara nomes, tipos e posições das colunas publicadas pelas duas rotas."""
    linha = consultar(f"""
      WITH colunas AS (
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM `{catalogo}`.information_schema.columns
        WHERE table_schema IN ('silver', 'silver_regras')
          AND table_name IN ('chamados_anonimizados', 'chamados_enriquecidos')
      ), ia AS (
        SELECT table_name, column_name, data_type, ordinal_position FROM colunas WHERE table_schema = 'silver'
      ), regras AS (
        SELECT table_name, column_name, data_type, ordinal_position FROM colunas WHERE table_schema = 'silver_regras'
      )
      SELECT (SELECT count(*) FROM ia) AS total_ia, (SELECT count(*) FROM regras) AS total_regras,
             (SELECT count(*) FROM (SELECT * FROM ia EXCEPT ALL SELECT * FROM regras)) AS so_ia,
             (SELECT count(*) FROM (SELECT * FROM regras EXCEPT ALL SELECT * FROM ia)) AS so_regras
    """)[0]
    assert int(linha["total_ia"]) > 0 and linha["total_ia"] == linha["total_regras"]
    assert int(linha["so_ia"]) == 0 and int(linha["so_regras"]) == 0


@pytest.mark.databricks
def test_regras_publicadas_mascara_e_identifica_a_rota(consultar, catalogo):
    """Confere os formatos conhecidos e a rastreabilidade no dataset completo."""
    linha = consultar(f"""
      SELECT count(*) AS total, count(DISTINCT a.id_chamado) AS unicos,
        (SELECT count(*) FROM `{catalogo}`.bronze.chamados) AS total_bronze,
        count_if(a.transcricao_anonimizada IS NULL OR
          instr(lower(a.transcricao_anonimizada), lower(b.nome_solicitante)) > 0) AS nomes_ou_nulos,
        count_if(a.transcricao_anonimizada RLIKE r'[0-9]{{3}}\\.[0-9]{{3}}\\.[0-9]{{3}}-[0-9]{{2}}') AS cpfs,
        count_if(a.transcricao_anonimizada RLIKE r'\\([0-9]{{2}}\\)\\s*9?[0-9]{{4}}-?[0-9]{{4}}') AS telefones,
        count_if(a.anonimizado_por <> 'regras_de_texto' OR e.enriquecido_por <> 'regras_de_texto') AS rotas_invalidas
      FROM `{catalogo}`.silver_regras.chamados_anonimizados a
      JOIN `{catalogo}`.bronze.chamados b ON a.id_chamado = b.id_chamado
      JOIN `{catalogo}`.silver_regras.chamados_enriquecidos e ON a.id_chamado = e.id_chamado
    """)[0]
    assert int(linha["total"]) > 0 and linha["total"] == linha["unicos"] == linha["total_bronze"]
    assert all(int(linha[chave]) == 0 for chave in ("nomes_ou_nulos", "cpfs", "telefones", "rotas_invalidas"))

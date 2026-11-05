import ast
import re
import runpy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def padroes_mascaramento():
    """Lê os padrões usados pelo pipeline sem iniciar uma sessão Spark."""
    caminho = (
        Path(__file__).resolve().parents[1] / "src/pipelines/grid_intelligence/transformations/13_silver_chamados.py"
    )
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    return {
        item.targets[0].id: ast.literal_eval(item.value)
        for item in arvore.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id in {"CPF", "TELEFONE"}
    }


@pytest.mark.parametrize("cpf", ["123.456.789-09", "12345678909"])
def test_padrao_cpf_identifica_formatos(cpf):
    """Reconhece CPF formatado e sem pontuação antes da análise por IA."""
    assert re.search(padroes_mascaramento()["CPF"], cpf)


@pytest.mark.parametrize("telefone", ["(11) 98765-4321", "11 3456-7890", "98765-4321"])
def test_padrao_telefone_identifica_formatos(telefone):
    """Reconhece números fixos e celulares nos formatos usuais do dataset."""
    assert re.search(padroes_mascaramento()["TELEFONE"], telefone)


@pytest.mark.databricks
def test_bronze_tem_mascaras_nas_tres_colunas(consultar, catalogo):
    """Confere a política publicada nas colunas que guardam dados pessoais."""
    linhas = consultar(f"""
      SELECT column_name, mask_name FROM `{catalogo}`.information_schema.column_masks
      WHERE table_schema = 'bronze' AND table_name = 'chamados' ORDER BY column_name
    """)
    assert {linha["column_name"] for linha in linhas} == {"nome_solicitante", "telefone_solicitante", "transcricao"}
    assert all(linha["mask_name"] == f"{catalogo}.bronze.mascarar_dado_pessoal" for linha in linhas)


@pytest.mark.databricks
def test_chamados_anonimizados_nao_expoem_dados_conhecidos(consultar, catalogo):
    """Compara a silver com nomes da bronze e procura CPF e telefone formatados."""
    linhas = consultar(f"""
      SELECT count(*) AS chamados,
        count(DISTINCT a.id_chamado) AS chamados_unicos,
        (SELECT count(*) FROM `{catalogo}`.bronze.chamados) AS total_bronze,
        (SELECT count(*) FROM `{catalogo}`.silver.chamados_anonimizados) AS total_silver,
        count_if(a.transcricao_anonimizada IS NULL) AS textos_nulos,
        count_if(b.nome_solicitante IS NOT NULL AND b.nome_solicitante <> '' AND
          instr(lower(a.transcricao_anonimizada), lower(b.nome_solicitante)) > 0) AS nomes,
        count_if(a.transcricao_anonimizada RLIKE r'[0-9]{{3}}\\.[0-9]{{3}}\\.[0-9]{{3}}-[0-9]{{2}}') AS cpfs,
        count_if(a.transcricao_anonimizada RLIKE r'\\([0-9]{{2}}\\)\\s*9?[0-9]{{4}}-?[0-9]{{4}}') AS telefones
      FROM `{catalogo}`.silver.chamados_anonimizados a
      JOIN `{catalogo}`.bronze.chamados b ON a.id_chamado = b.id_chamado
    """)
    assert int(linhas[0]["chamados"]) > 0
    assert linhas[0]["chamados"] == linhas[0]["chamados_unicos"]
    assert linhas[0]["chamados"] == linhas[0]["total_bronze"] == linhas[0]["total_silver"]
    contagens = {chave: int(linhas[0][chave]) for chave in ("textos_nulos", "nomes", "cpfs", "telefones")}
    assert contagens == {"textos_nulos": 0, "nomes": 0, "cpfs": 0, "telefones": 0}


@pytest.mark.databricks
def test_enriquecimento_preserva_chamados_e_campos(consultar, catalogo):
    """Verifica cobertura do enriquecimento sem expor as transcrições."""
    linha = consultar(f"""
      SELECT count(*) AS total,
        (SELECT count(*) FROM `{catalogo}`.silver.chamados_anonimizados) AS total_anonimizado,
        count_if(sentimento IS NULL OR motivo IS NULL OR urgencia IS NULL OR
          (transcricao_anonimizada <> '[RESTRITO]' AND
           (risco_a_saude IS NULL OR ameacou_ouvidoria IS NULL))) AS campos_ausentes,
        count_if(transcricao_anonimizada = '[RESTRITO]' AND
          (sentimento <> 'indisponivel' OR motivo <> 'indisponivel' OR urgencia <> 'indeterminada')) AS restritos_classificados
      FROM `{catalogo}`.silver.chamados_enriquecidos
    """)[0]
    assert int(linha["total"]) > 0
    assert linha["total"] == linha["total_anonimizado"]
    assert int(linha["campos_ausentes"]) == 0
    assert int(linha["restritos_classificados"]) == 0


@pytest.mark.databricks
def test_rotas_ia_e_regras_mesmo_esquema_e_mascaramento(perfil, monkeypatch):
    """Executa as duas rotas em dados sintéticos, sem criar tabelas no catálogo."""
    from databricks.connect import DatabricksSession
    from pyspark import pipelines as dp

    sessao = DatabricksSession.builder.profile(perfil).serverless(True).getOrCreate()
    chamados = sessao.createDataFrame(
        [
            (
                "C1",
                "UC1",
                datetime(2026, 1, 1),
                "telefone",
                42,
                "sistema",
                datetime(2026, 1, 1),
                "arquivo",
                datetime(2026, 1, 1),
                "Maria Silva",
                "Maria Silva, CPF 123.456.789-09, telefone (11) 98765-4321. Sem energia, uso oxigenio.",
            )
        ],
        "id_chamado STRING, id_uc STRING, abertura TIMESTAMP, canal STRING, duracao_segundos INT, "
        "origem STRING, ingerido_em TIMESTAMP, arquivo_origem STRING, ingerido_bronze_em TIMESTAMP, "
        "nome_solicitante STRING, transcricao STRING",
    )
    cadastro = sessao.createDataFrame(
        [("UC1", "cliente", "conjunto", "Conjunto", "Bairro", "residencial")],
        "id_uc STRING, id_cliente STRING, id_conjunto STRING, nome_conjunto STRING, bairro STRING, classe_consumo STRING",
    )
    monkeypatch.setattr(dp, "materialized_view", lambda **_: lambda funcao: funcao, raising=False)
    caminho = (
        Path(__file__).resolve().parents[1] / "src/pipelines/grid_intelligence/transformations/13_silver_chamados.py"
    )
    esquemas = []
    try:
        for usar_ia in ("false", "true"):
            fontes = {"teste.bronze.chamados": chamados, "teste.silver.unidades_consumidoras": cadastro}
            configuracao = {
                "catalogo": "teste",
                "schema_bronze": "bronze",
                "schema_silver": "silver",
                "usar_ia": usar_ia,
            }
            spark_teste = SimpleNamespace(
                conf=SimpleNamespace(
                    get=lambda chave, padrao=None, configuracao=configuracao: configuracao.get(chave, padrao)
                ),
                read=SimpleNamespace(table=lambda nome, fontes=fontes: fontes[nome]),
            )
            modulo = runpy.run_path(str(caminho), init_globals={"spark": spark_teste})
            anonimizado = modulo["chamados_anonimizados"]()
            resultado = anonimizado.collect()[0]
            assert all(
                dado not in resultado.transcricao_anonimizada
                for dado in ("Maria Silva", "123.456.789-09", "98765-4321")
            )
            fontes["teste.silver.chamados_anonimizados"] = sessao.createDataFrame([resultado], anonimizado.schema)
            enriquecido = modulo["chamados_enriquecidos"]()
            linha = enriquecido.collect()[0]
            assert linha.risco_a_saude is True
            assert linha.enriquecido_por == ("ia" if usar_ia == "true" else "regras_de_texto")
            esquemas.append([(campo.name, campo.dataType) for campo in enriquecido.schema.fields])
        assert esquemas[0] == esquemas[1]

        from pyspark.sql import functions as F

        with monkeypatch.context() as contexto:
            contexto.setattr(F, "expr", lambda expressao: F.lit(None).cast("string"))
            linha_sem_classificacao = modulo["chamados_enriquecidos"]().collect()[0]
            assert linha_sem_classificacao.sentimento == "indisponivel"
            assert linha_sem_classificacao.motivo == "indisponivel"
            assert linha_sem_classificacao.urgencia == "alta"

        monkeypatch.setattr(F, "call_function", lambda *args: F.lit(None).cast("string"))
        anonimo_restrito = modulo["chamados_anonimizados"]().collect()[0]
        assert anonimo_restrito.transcricao_anonimizada == "[RESTRITO]"
        fontes["teste.silver.chamados_anonimizados"] = sessao.createDataFrame([anonimo_restrito], anonimizado.schema)
        linha_restrita = modulo["chamados_enriquecidos"]().collect()[0]
        assert linha_restrita.sentimento == "indisponivel"
        assert linha_restrita.motivo == "indisponivel"
        assert linha_restrita.urgencia == "indeterminada"
        assert linha_restrita.risco_a_saude is None
        assert linha_restrita.ameacou_ouvidoria is None
    finally:
        sessao.stop()

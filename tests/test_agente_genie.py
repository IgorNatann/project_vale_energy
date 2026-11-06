"""Verifica o contrato versionado e as salvaguardas do aplicador do Genie."""

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "src/genie/grid_intelligence.json"
ESPECIFICACAO = importlib.util.spec_from_file_location("aplicador_genie", RAIZ / "scripts/aplicar_agente_genie.py")
APLICADOR = importlib.util.module_from_spec(ESPECIFICACAO)
ESPECIFICACAO.loader.exec_module(APLICADOR)


def test_contrato_restringe_fontes_e_preserva_perguntas():
    """As quatro fontes são gold, o texto livre é excluído e os IDs são únicos e ordenados."""
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    fontes = dados["data_sources"]
    tabelas = fontes["tables"]
    assert [item["identifier"] for item in tabelas] == [
        "${catalogo}.gold.painel_operacional_dia",
        "${catalogo}.gold.prioridade_inspecao_uc",
        "${catalogo}.gold.saude_cliente",
    ]
    assert [item["identifier"] for item in fontes["metric_views"]] == [
        "${catalogo}.gold.continuidade_metricas"
    ]
    cliente = tabelas[2]
    assert any(c["column_name"] == "ultima_fala" and c.get("exclude") for c in cliente["column_configs"])
    listas = [dados["config"]["sample_questions"], dados["instructions"]["example_question_sqls"],
              dados["instructions"]["text_instructions"]]
    assert [len(lista) for lista in listas] == [5, 4, 1]
    ids = [item["id"] for lista in listas for item in lista]
    assert len(set(ids)) == len(ids)
    assert all(len(item) == 32 and all(caractere in "0123456789abcdef" for caractere in item) for item in ids)
    assert all([item["id"] for item in lista] == sorted(item["id"] for item in lista) for lista in listas)
    sql = " ".join(item["sql"][0] for item in listas[1])
    assert "MEASURE(m.`DEC`)" in sql and "MEASURE(m.`FEC`)" in sql
    assert ".bronze." not in sql and ".silver." not in sql


def test_preparacao_valida_catalogo_e_substitui_marcador():
    """Não permite identificador inválido e substitui o catálogo também nos exemplos SQL."""
    resultado = APLICADOR.preparar_definicao("grid_dev")
    conteudo = json.dumps(resultado)
    assert "${catalogo}" not in conteudo
    assert "grid_dev.gold.continuidade_metricas" in conteudo
    with pytest.raises(ValueError):
        APLICADOR.preparar_definicao("grid_dev.gold")


def test_identificacao_nao_sobrescreve_espaco_com_fontes_diferentes(monkeypatch):
    """Um espaço homônimo com fontes incompatíveis exige identificação explícita."""
    definicao = APLICADOR.preparar_definicao("grid_dev")

    def simular_cli(argumentos, perfil):
        if argumentos[1] == "list-spaces":
            return {"spaces": [{"space_id": "outro", "title": APLICADOR.TITULO}]}
        return {"serialized_space": json.dumps({"data_sources": {"tables": [{"identifier": "outro.gold.tabela"}]}})}

    monkeypatch.setattr(APLICADOR, "executar_cli", simular_cli)
    with pytest.raises(ValueError, match="fontes diferentes"):
        APLICADOR.identificar_espaco("perfil", definicao)

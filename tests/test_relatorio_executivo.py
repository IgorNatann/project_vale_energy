"""Exercita a narrativa e a rejeição de respostas divergentes da IA."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

CAMINHO = Path(__file__).resolve().parents[1] / "src/notebooks/relatorio_executivo.py"
FUNCOES = runpy.run_path(str(CAMINHO), run_name="teste_relatorio")


def test_relatorio_reune_medidas_e_nao_acusa():
    """O gabarito usa os valores recebidos, mesmo com campos indisponíveis."""
    operacao = [{"nome_conjunto": "Centro", "qtd_interrupcoes": 1, "uc_horas_interrompidas": 4,
                 "maior_duracao_horas": 2, "causa_predominante": "climatica", "qtd_chamados": 3,
                 "media_chamados_30_dias": 0.5, "chamados_negativos": 1, "chamados_risco_saude": 0,
                 "consumo_kwh": 100, "mencoes_ouvidoria": 0, "acao_recomendada": "Avaliar rede"}]
    texto = FUNCOES["montar_relatorio"]("Campinas", "2026-07-31", operacao,
                                        {"Centro": {"dec_horas": 1.25, "fec": 0.43}},
                                        [{"bairro": "Aurora", "total": 2}], 1, ["CLI01"])
    assert all(valor in texto for valor in ("4.00 horas-UC", "3 chamados", "1.25 h", "0.43", "Aurora: 2 UCs", "CLI01"))
    assert len(texto.split()) <= 250
    assert not any(palavra in texto.lower() for palavra in ("fraude", "furto", "roubo", "irregularidade"))


def test_ia_divergente_retorna_mesmo_gabarito():
    """Não publica uma resposta que acrescente números ou altere os fatos."""
    class Resultado:
        def first(self):
            return {"texto": "Ocorreu um evento com 999 chamados."}

    spark = SimpleNamespace(sql=lambda *args, **kwargs: Resultado())
    texto, metodo = FUNCOES["gerar_narrativa"](spark, "Ocorreu um evento com 2 chamados.", True)
    assert texto == "Ocorreu um evento com 2 chamados."
    assert metodo == "gabarito_ia_divergente"
    assert FUNCOES["gerar_narrativa"](spark, texto, False) == (texto, "gabarito")


def test_ia_aceita_diferenca_de_espacamento_sem_mudar_fatos():
    """Aceita separação de parágrafos, preservando todos os dados e o texto."""
    class Resultado:
        def first(self):
            return {"texto": "Parte A: 2 chamados.\n\nParte B: 0 eventos."}

    spark = SimpleNamespace(sql=lambda *args, **kwargs: Resultado())
    texto, metodo = FUNCOES["gerar_narrativa"](spark, "Parte A: 2 chamados.\nParte B: 0 eventos.", True)
    assert metodo == "ia_validada"
    assert "2 chamados" in texto and "0 eventos" in texto


def test_limite_de_palavras_e_identificadores():
    """A validação impede relatório longo e identificadores SQL não previstos."""
    with pytest.raises(ValueError, match="250 palavras"):
        FUNCOES["gerar_narrativa"](None, "palavra " * 251, False)
    with pytest.raises(ValueError):
        FUNCOES["validar_identificador"]("grid.dev")
    with pytest.raises(ValueError, match="termo incompatível"):
        FUNCOES["gerar_narrativa"](None, "A acusação foi de fraude.", False)


@pytest.mark.parametrize("linhas", [[], [{"qtd_interrupcoes": 0, "qtd_chamados": 0}]])
def test_regiao_sem_movimento_falha_com_mensagem(linhas):
    """Não entrega relatório vazio quando a região não tem eventos na data de referência."""
    class Resultado:
        def first(self):
            return {"dia": "2026-07-31"}

        def collect(self):
            return [SimpleNamespace(asDict=lambda linha=linha: linha) for linha in linhas]

    spark = SimpleNamespace(sql=lambda *args, **kwargs: Resultado())
    with pytest.raises(ValueError, match="Não há movimento para Região Ausente"):
        FUNCOES["executar_relatorio"](spark, "grid_dev", "gold", "Região Ausente", False)

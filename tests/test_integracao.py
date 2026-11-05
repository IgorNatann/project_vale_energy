import subprocess

import pytest

pytestmark = pytest.mark.databricks

COLUNAS = {
    "unidades_consumidoras": "id_uc, id_cliente, id_conjunto, nome_conjunto, municipio, bairro, logradouro, classe_consumo, subgrupo_tarifario, tensao_nominal_v, situacao, data_ligacao, possui_medidor_inteligente, consumo_medio_kwh_dia, latitude, longitude, origem, ingerido_em",
    "interrupcoes": "id_interrupcao, id_conjunto, inicio, fim, duracao_minutos, tipo, causa, equipamento, qtd_ucs_afetadas, origem, ingerido_em",
    "consumo_diario": "id_uc, data, consumo_kwh, horas_com_leitura, sinal_violacao_medidor, origem, ingerido_em",
    "chamados": "id_chamado, id_uc, abertura, canal, nome_solicitante, telefone_solicitante, transcricao, duracao_segundos, origem, ingerido_em",
}


@pytest.mark.parametrize("tabela", COLUNAS)
def test_bronze_preserva_origem_e_metadados(consultar, catalogo, tabela):
    """Compara todas as linhas, inclusive duplicatas, e verifica rastreabilidade."""
    colunas = COLUNAS[tabela]
    origem = f"SELECT {colunas} FROM parquet.`/Volumes/{catalogo}/raw/landing/{tabela}/`"
    bronze = f"SELECT {colunas} FROM `{catalogo}`.bronze.{tabela}"
    linha = consultar(f"""
      SELECT (SELECT count(*) FROM ({origem} EXCEPT ALL {bronze})) AS so_origem,
             (SELECT count(*) FROM ({bronze} EXCEPT ALL {origem})) AS so_bronze,
             (SELECT count(*) FROM `{catalogo}`.bronze.{tabela}) AS linhas,
             (SELECT count_if(arquivo_origem IS NULL OR ingerido_bronze_em IS NULL)
                FROM `{catalogo}`.bronze.{tabela}) AS sem_metadados
    """)[0]
    assert int(linha["linhas"]) > 0
    assert all(int(linha[chave]) == 0 for chave in ("so_origem", "so_bronze", "sem_metadados"))


def test_silver_consumo_e_interrupcoes(consultar, catalogo):
    """Verifica os limites aprovados para o dataset e a unicidade por UC e dia."""
    linha = consultar(f"""
      SELECT
        (SELECT count(*) FROM `{catalogo}`.silver.interrupcoes_validas) AS eventos,
        (SELECT count(*) FROM `{catalogo}`.silver.consumo_diario) AS leituras,
        (SELECT count_if(duracao_minutos < 3) FROM `{catalogo}`.silver.interrupcoes_validas) AS curtas,
        (SELECT count_if(consumo_kwh IS NULL OR consumo_kwh < 0 OR consumo_kwh > CASE classe_consumo
            WHEN 'residencial' THEN 100 WHEN 'comercial' THEN 500 WHEN 'industrial' THEN 10000
            WHEN 'rural' THEN 250 WHEN 'poder_publico' THEN 2000 END)
           FROM `{catalogo}`.silver.consumo_diario) AS invalidas,
        (SELECT count(*) - count(DISTINCT id_uc, data) FROM `{catalogo}`.silver.consumo_diario) AS duplicatas
    """)[0]
    assert int(linha["eventos"]) > 0 and int(linha["leituras"]) > 0
    assert all(int(linha[chave]) == 0 for chave in ("curtas", "invalidas", "duplicatas"))


@pytest.mark.reexecucao
def test_reexecucao_nao_duplica_bronze(consultar, catalogo, perfil):
    """Confere contagens e última ingestão antes e depois de uma execução em dev."""
    if catalogo != "grid_dev":
        pytest.fail("A reexecução está restrita ao catálogo grid_dev e ao target dev")

    def estado():
        consultas = [
            f"SELECT '{tabela}' AS tabela, count(*) AS linhas, max(ingerido_bronze_em) AS ultima_ingestao "
            f"FROM `{catalogo}`.bronze.{tabela}"
            for tabela in COLUNAS
        ]
        return consultar(" UNION ALL ".join(consultas) + " ORDER BY tabela")

    antes = estado()
    subprocess.run(
        ["databricks", "bundle", "run", "processar_grid", "--target", "dev", "--profile", perfil],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=900,
    )
    assert estado() == antes

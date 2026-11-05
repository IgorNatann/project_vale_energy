import pytest
from conftest import consulta_transformacao

pytestmark = pytest.mark.databricks


def test_cadastro_normaliza_e_descarta_chaves_invalidas(consultar):
    """Exercita o SQL de cadastro com classes, bairros e chaves representativos."""
    consulta = consulta_transformacao("10_silver_cadastro.sql").replace(
        "STREAM(${catalogo}.${schema_bronze}.unidades_consumidoras)", "origem"
    )
    linhas = consultar(f"""
        WITH origem(id_uc, id_conjunto, classe_consumo, bairro) AS (
          VALUES ('1', 'A', '  RESIDENCIAL ', ''), ('2', 'A', 'Comercial', NULL),
                 (NULL, 'A', 'rural', 'Centro'), ('3', NULL, 'rural', 'Centro')
        ), resultado AS ({consulta})
        SELECT id_uc, classe_consumo, bairro FROM resultado ORDER BY id_uc
    """)
    assert linhas == [
        {"id_uc": "1", "classe_consumo": "residencial", "bairro": "nao informado"},
        {"id_uc": "2", "classe_consumo": "comercial", "bairro": "nao informado"},
    ]


@pytest.mark.parametrize("limiar,esperados", [(3, ["limite", "acima"]), (4, [])])
def test_interrupcoes_limite_configuravel_e_calculos(consultar, limiar, esperados):
    """Testa a fronteira da RN-01 e os insumos de continuidade com dois limiares."""
    consulta = consulta_transformacao("11_silver_interrupcoes.sql")
    consulta = consulta.replace("STREAM(${catalogo}.${schema_bronze}.interrupcoes)", "origem")
    consulta = consulta.replace("${duracao_minima_interrupcao}", str(limiar))
    linhas = consultar(f"""
        WITH origem(id_interrupcao, inicio, duracao_minutos, qtd_ucs_afetadas, causa) AS (
          VALUES ('abaixo', TIMESTAMP'2026-01-15 12:00:00', 2.99, 20, 'climatica'),
                 ('limite', TIMESTAMP'2026-01-15 12:00:00', 3.00, 20, 'climatica'),
                 ('acima', TIMESTAMP'2026-01-15 12:00:00', 3.01, 20, 'outra')
        ), resultado AS ({consulta})
        SELECT id_interrupcao, data_evento, duracao_horas, uc_horas_interrompidas, causa_climatica
        FROM resultado ORDER BY duracao_minutos
    """)
    assert [linha["id_interrupcao"] for linha in linhas] == esperados
    if linhas:
        assert linhas[0]["data_evento"] == "2026-01-15"
        assert float(linhas[0]["duracao_horas"]) == pytest.approx(0.05)
        assert float(linhas[0]["uc_horas_interrompidas"]) == pytest.approx(1.0)
        assert str(linhas[0]["causa_climatica"]).lower() == "true"
        assert str(linhas[1]["causa_climatica"]).lower() == "false"


def test_consumo_limites_nulos_negativos_e_duplicatas(consultar):
    """Testa as cinco classes e preserva a leitura válida com ingestão mais recente."""
    consulta = consulta_transformacao("12_silver_consumo.sql")
    consulta = consulta.replace("${catalogo}.${schema_bronze}.consumo_diario", "origem")
    consulta = consulta.replace("${catalogo}.${schema_silver}.unidades_consumidoras", "cadastro")
    linhas = consultar(f"""
        WITH cadastro(id_uc, id_conjunto, nome_conjunto, bairro, classe_consumo) AS (
          VALUES ('r','A','A','B','residencial'), ('c','A','A','B','comercial'),
                 ('i','A','A','B','industrial'), ('a','A','A','B','rural'),
                 ('p','A','A','B','poder_publico')
        ), origem(id_uc, data, consumo_kwh, ingerido_em) AS (
          VALUES ('r', DATE'2026-01-01', 100.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('r', DATE'2026-01-02', 100.1, TIMESTAMP'2026-01-01 01:00:00'),
                 ('r', DATE'2026-01-03', NULL, TIMESTAMP'2026-01-01 01:00:00'),
                 ('r', DATE'2026-01-04', -1.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('r', DATE'2026-01-05', 10.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('r', DATE'2026-01-05', 20.0, TIMESTAMP'2026-01-01 02:00:00'),
                 ('c', DATE'2026-01-01', 500.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('c', DATE'2026-01-02', 500.1, TIMESTAMP'2026-01-01 01:00:00'),
                 ('i', DATE'2026-01-01', 10000.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('i', DATE'2026-01-02', 10000.1, TIMESTAMP'2026-01-01 01:00:00'),
                 ('a', DATE'2026-01-01', 250.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('a', DATE'2026-01-02', 250.1, TIMESTAMP'2026-01-01 01:00:00'),
                 ('p', DATE'2026-01-01', 2000.0, TIMESTAMP'2026-01-01 01:00:00'),
                 ('p', DATE'2026-01-02', 2000.1, TIMESTAMP'2026-01-01 01:00:00')
        ), resultado AS ({consulta})
        SELECT id_uc, data, consumo_kwh FROM resultado ORDER BY id_uc, data
    """)
    assert [(r["id_uc"], r["data"], float(r["consumo_kwh"])) for r in linhas] == [
        ("a", "2026-01-01", 250), ("c", "2026-01-01", 500), ("i", "2026-01-01", 10000),
        ("p", "2026-01-01", 2000), ("r", "2026-01-01", 100), ("r", "2026-01-05", 20),
    ]


def test_baseline_janelas_e_variacao_por_uc_e_conjunto(consultar):
    """Confere os extremos das janelas e as variações com um conjunto de duas UCs."""
    consulta = consulta_transformacao("12_silver_consumo.sql", 1)
    consulta = consulta.replace("${catalogo}.${schema_bronze}.consumo_diario", "origem")
    consulta = consulta.replace("${catalogo}.${schema_silver}.consumo_diario", "consumo")
    linhas = consultar(f"""
        WITH origem(data) AS (VALUES (DATE'2026-05-01')),
        consumo(id_uc, id_conjunto, nome_conjunto, bairro, classe_consumo, data, consumo_kwh, sinal_violacao_medidor) AS (
          VALUES ('1','A','A','B','residencial', date_sub(DATE'2026-05-01',120), 999.0, false),
                 ('1','A','A','B','residencial', date_sub(DATE'2026-05-01',119), 10.0, false),
                 ('1','A','A','B','residencial', date_sub(DATE'2026-05-01',30), 10.0, false),
                 ('1','A','A','B','residencial', date_sub(DATE'2026-05-01',29), 20.0, true),
                 ('1','A','A','B','residencial', DATE'2026-05-01', 20.0, false),
                 ('2','A','A','B','residencial', date_sub(DATE'2026-05-01',30), 10.0, false),
                 ('2','A','A','B','residencial', DATE'2026-05-01', 10.0, false)
        ), resultado AS ({consulta})
        SELECT id_uc, consumo_medio_baseline_kwh, consumo_medio_recente_kwh, dias_no_baseline,
               dias_no_periodo_recente, variacao_da_uc, variacao_do_conjunto, sinal_violacao_recente
        FROM resultado ORDER BY id_uc
    """)
    assert len(linhas) == 2
    primeira, segunda = linhas
    assert (int(primeira["dias_no_baseline"]), int(primeira["dias_no_periodo_recente"])) == (2, 2)
    assert (float(primeira["consumo_medio_baseline_kwh"]), float(primeira["consumo_medio_recente_kwh"])) == (10, 20)
    assert float(primeira["variacao_da_uc"]) == pytest.approx(1.0)
    assert float(segunda["variacao_da_uc"]) == pytest.approx(0.0)
    assert float(primeira["variacao_do_conjunto"]) == pytest.approx(2 / 3)
    assert float(segunda["variacao_do_conjunto"]) == pytest.approx(2 / 3)
    assert str(primeira["sinal_violacao_recente"]).lower() == "true"

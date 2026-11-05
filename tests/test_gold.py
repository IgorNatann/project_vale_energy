import pytest
from conftest import consulta_transformacao

pytestmark = pytest.mark.databricks


def test_continuidade_inclui_meses_sem_eventos_e_denominador_total(consultar):
    """Confere os insumos mensais com evento de duas horas afetando metade da base."""
    consulta = consulta_transformacao('20_gold_continuidade.sql')
    consulta = consulta.replace('${catalogo}.${schema_silver}.unidades_consumidoras', 'cadastro')
    consulta = consulta.replace('${catalogo}.${schema_silver}.interrupcoes_validas', 'interrupcoes')
    linhas = consultar(f"""
      WITH cadastro(id_conjunto, nome_conjunto, municipio) AS (
        VALUES ('A', 'Conjunto A', 'Cidade'), ('A', 'Conjunto A', 'Cidade'),
               ('A', 'Conjunto A', 'Cidade'), ('A', 'Conjunto A', 'Cidade')
      ), interrupcoes(id_conjunto, mes_apuracao, uc_horas_interrompidas, qtd_ucs_afetadas,
                      causa_climatica, tipo, duracao_horas) AS (
        VALUES ('A', TIMESTAMP'2026-01-01', 4.0, 2, true, 'programada', 2.0),
               ('A', TIMESTAMP'2026-03-01', 1.0, 1, false, 'emergencial', 1.0)
      ), resultado AS ({consulta})
      SELECT mes_apuracao, total_ucs, uc_horas_interrompidas, uc_interrupcoes, qtd_interrupcoes
      FROM resultado ORDER BY mes_apuracao
    """)
    assert len(linhas) == 3
    assert [int(linha['total_ucs']) for linha in linhas] == [4, 4, 4]
    assert [float(linha['uc_horas_interrompidas']) for linha in linhas] == [4, 0, 1]
    assert [int(linha['uc_interrupcoes']) for linha in linhas] == [2, 0, 1]
    assert [int(linha['qtd_interrupcoes']) for linha in linhas] == [1, 0, 1]


def test_prioridade_exige_dois_eixos_e_sinal_para_alta(consultar):
    """Exercita os limites e diferencia queda acompanhada do conjunto de queda individual."""
    consulta = consulta_transformacao('21_gold_prioridade_inspecao.sql')
    consulta = consulta.replace('${catalogo}.${schema_silver}.baseline_consumo', 'baseline')
    consulta = consulta.replace('${queda_minima_consumo}', '0.30').replace('${variacao_maxima_conjunto}', '0.10')
    linhas = consultar(f"""
      WITH baseline(id_uc, id_conjunto, nome_conjunto, bairro, classe_consumo,
                    variacao_da_uc, variacao_do_conjunto, sinal_violacao_recente,
                    consumo_medio_baseline_kwh, consumo_medio_recente_kwh, dias_no_baseline, dias_no_periodo_recente) AS (
        VALUES ('1','A','Conjunto','Bairro','residencial',-0.31, 0.10,true,10.0,6.9,90,30),
               ('2','A','Conjunto','Bairro','residencial',-0.31, 0.10,false,10.0,6.9,90,30),
               ('3','A','Conjunto','Bairro','residencial',-0.10, 0.00,true,10.0,9.0,90,30),
               ('4','A','Conjunto','Bairro','residencial',-0.31,-0.11,false,10.0,6.9,90,30),
               ('5','A','Conjunto','Bairro','residencial',-0.30, 0.00,false,10.0,7.0,90,30),
               ('6','A','Conjunto','Bairro','residencial',-0.31, NULL,false,10.0,6.9,90,30)
      ), resultado AS ({consulta})
      SELECT id_uc, prioridade_inspecao, motivo_observado FROM resultado ORDER BY id_uc
    """)
    assert [(linha['id_uc'], linha['prioridade_inspecao']) for linha in linhas] == [
        ('1', 'alta'), ('2', 'media'), ('3', 'media'), ('4', 'baixa'), ('6', 'baixa')
    ]
    assert linhas[-1]['motivo_observado'] == 'Queda individual sem dados de variação do conjunto'


def test_saude_agrupa_cliente_em_multiplas_ucs(consultar):
    """A reincidência considera o cliente e a janela de 30 dias do dataset."""
    consulta = consulta_transformacao('22_gold_saude_cliente.sql')
    consulta = consulta.replace('${catalogo}.${schema_silver}.chamados_enriquecidos', 'origem')
    linhas = consultar(f"""
      WITH origem(id_cliente, id_uc, id_chamado, id_conjunto, nome_conjunto, bairro, abertura,
                  sentimento, ameacou_ouvidoria, risco_a_saude, urgencia, motivo,
                  equipamento_citado, transcricao_anonimizada) AS (
        VALUES ('C1','U1','1','A','Conjunto','Bairro',TIMESTAMP'2026-01-01',
                'neutral',false,false,'baixa','falta_energia','', 'Primeiro'),
               ('C1','U2','2','A','Conjunto','Bairro',TIMESTAMP'2026-01-10',
                'negative',false,false,'baixa','falta_energia','medidor', 'Segundo'),
               ('C1','U1','3','A','Conjunto','Bairro',TIMESTAMP'2026-01-20',
                'neutral',false,false,'baixa','religacao','', 'Terceiro'),
               ('C2','U3','4','A','Conjunto','Bairro',TIMESTAMP'2026-01-21',
                'neutral',false,true,'alta','religacao_urgente','', 'Risco')
      ), resultado AS ({consulta})
      SELECT id_cliente, qtd_chamados, qtd_ucs_com_chamado, risco_ouvidoria, ultima_fala, ultimo_equipamento_citado
      FROM resultado ORDER BY id_cliente
    """)
    assert [(linha['id_cliente'], int(linha['qtd_chamados']), int(linha['qtd_ucs_com_chamado']),
             linha['risco_ouvidoria'], linha['ultima_fala']) for linha in linhas] == [
        ('C1', 3, 2, 'alto', 'Terceiro'), ('C2', 1, 1, 'medio', 'Risco')
    ]
    assert linhas[0]['ultimo_equipamento_citado'] == 'medidor'


def test_painel_preserva_dias_de_cada_origem_e_prioriza_risco(consultar):
    """Eventos isolados não desaparecem e o risco prevalece sobre outras ações."""
    consulta = consulta_transformacao('23_gold_painel_operacional.sql')
    for tabela in ('interrupcoes_validas', 'chamados_enriquecidos', 'consumo_diario', 'unidades_consumidoras'):
        consulta = consulta.replace(f'${{catalogo}}.${{schema_silver}}.{tabela}', tabela)
    consulta = consulta.replace('${catalogo}.${schema_gold}.prioridade_inspecao_uc', 'prioridade_inspecao_uc')
    linhas = consultar(f"""
      WITH interrupcoes_validas(id_conjunto, data_evento, uc_horas_interrompidas) AS (
        VALUES ('A', DATE'2026-01-01', 2.0), ('A', DATE'2026-01-03', 1.0)
      ), chamados_enriquecidos(id_conjunto, data_chamado, risco_a_saude, ameacou_ouvidoria) AS (
        VALUES ('A', DATE'2026-01-02', false, true), ('A', DATE'2026-01-03', true, true)
      ), consumo_diario(id_conjunto, data, consumo_kwh) AS (
        VALUES ('A', DATE'2026-01-04', 10.0)
      ), unidades_consumidoras(id_conjunto, nome_conjunto, municipio) AS (
        VALUES ('A', 'Conjunto A', 'Cidade')
      ), prioridade_inspecao_uc(id_conjunto, prioridade_inspecao) AS (
        VALUES ('A', 'alta')
      ), resultado AS ({consulta})
      SELECT dia, qtd_interrupcoes, qtd_chamados, leituras, acao_recomendada FROM resultado ORDER BY dia
    """)
    assert [(int(linha['qtd_interrupcoes']), int(linha['qtd_chamados']), int(linha['leituras'])) for linha in linhas] == [
        (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1)
    ]
    assert [linha['acao_recomendada'] for linha in linhas] == [
        'Avaliar impacto das interrupções na rede',
        'Acompanhar menções à ouvidoria ou órgãos de defesa',
        'Priorizar atendimento com sinal de risco à saúde',
        'Planejar inspeções prioritárias',
    ]


def test_metricas_dec_media_e_acumulado_em_dois_meses(consultar, catalogo):
    """Compara a metric view com seus insumos em dois meses, sem duplicar denominador."""
    linhas = consultar(f"""
      WITH meses AS (
        SELECT DISTINCT mes_apuracao FROM `{catalogo}`.gold.continuidade_conjunto_mes
        ORDER BY mes_apuracao DESC LIMIT 2
      ), referencia AS (
        SELECT sum(uc_horas_interrompidas) / sum(total_ucs) AS dec,
          sum(uc_horas_interrompidas) / (sum(total_ucs) / count(DISTINCT mes_apuracao)) AS acumulado
        FROM `{catalogo}`.gold.continuidade_conjunto_mes WHERE mes_apuracao IN (SELECT mes_apuracao FROM meses)
      )
      SELECT MEASURE(DEC) AS dec, MEASURE(`DEC Acumulado`) AS acumulado,
        (SELECT dec FROM referencia) AS dec_referencia, (SELECT acumulado FROM referencia) AS acumulado_referencia
      FROM `{catalogo}`.gold.continuidade_metricas WHERE Mes IN (SELECT mes_apuracao FROM meses)
    """)
    linha = linhas[0]
    assert float(linha['dec']) == pytest.approx(float(linha['dec_referencia']))
    assert float(linha['acumulado']) == pytest.approx(float(linha['acumulado_referencia']))
    assert float(linha['acumulado']) == pytest.approx(2 * float(linha['dec']))

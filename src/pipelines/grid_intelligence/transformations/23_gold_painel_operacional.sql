CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_gold}.painel_operacional_dia
COMMENT 'Eventos diários por conjunto. A prioridade de inspeção reflete o último baseline disponível, não o histórico do dia.'
AS WITH interrupcoes AS (
  SELECT id_conjunto, data_evento AS dia, count(*) AS qtd_interrupcoes,
    sum(uc_horas_interrompidas) AS uc_horas_interrompidas
  FROM ${catalogo}.${schema_silver}.interrupcoes_validas GROUP BY id_conjunto, data_evento
), chamados AS (
  SELECT id_conjunto, data_chamado AS dia, count(*) AS qtd_chamados,
    count_if(risco_a_saude) AS chamados_risco_saude, count_if(ameacou_ouvidoria) AS mencoes_ouvidoria
  FROM ${catalogo}.${schema_silver}.chamados_enriquecidos GROUP BY id_conjunto, data_chamado
), consumo AS (
  SELECT id_conjunto, data AS dia, sum(consumo_kwh) AS consumo_kwh, count(*) AS leituras
  FROM ${catalogo}.${schema_silver}.consumo_diario GROUP BY id_conjunto, data
), eventos AS (
  SELECT coalesce(i.id_conjunto, c.id_conjunto, d.id_conjunto) AS id_conjunto,
    coalesce(i.dia, c.dia, d.dia) AS dia,
    coalesce(i.qtd_interrupcoes, 0) AS qtd_interrupcoes,
    coalesce(i.uc_horas_interrompidas, 0) AS uc_horas_interrompidas,
    coalesce(c.qtd_chamados, 0) AS qtd_chamados, coalesce(c.chamados_risco_saude, 0) AS chamados_risco_saude,
    coalesce(c.mencoes_ouvidoria, 0) AS mencoes_ouvidoria, d.consumo_kwh, coalesce(d.leituras, 0) AS leituras
  FROM interrupcoes i FULL OUTER JOIN chamados c ON i.id_conjunto = c.id_conjunto AND i.dia = c.dia
  FULL OUTER JOIN consumo d ON coalesce(i.id_conjunto, c.id_conjunto) = d.id_conjunto AND coalesce(i.dia, c.dia) = d.dia
), conjuntos AS (
  SELECT id_conjunto, max(nome_conjunto) AS nome_conjunto, max(municipio) AS municipio, count(*) AS total_ucs
  FROM ${catalogo}.${schema_silver}.unidades_consumidoras GROUP BY id_conjunto
), prioridades AS (
  SELECT id_conjunto, count_if(prioridade_inspecao = 'alta') AS inspecoes_prioridade_alta
  FROM ${catalogo}.${schema_gold}.prioridade_inspecao_uc GROUP BY id_conjunto
)
SELECT e.*, c.nome_conjunto, c.municipio, c.total_ucs, coalesce(p.inspecoes_prioridade_alta, 0) AS inspecoes_prioridade_alta,
  CASE WHEN chamados_risco_saude > 0 THEN 'Priorizar atendimento com sinal de risco à saúde'
       WHEN mencoes_ouvidoria > 0 THEN 'Acompanhar menções à ouvidoria ou órgãos de defesa'
       WHEN qtd_interrupcoes > 0 THEN 'Avaliar impacto das interrupções na rede'
       WHEN p.inspecoes_prioridade_alta > 0 THEN 'Planejar inspeções prioritárias'
       ELSE 'Acompanhar operação' END AS acao_recomendada
FROM eventos e LEFT JOIN conjuntos c ON e.id_conjunto = c.id_conjunto
LEFT JOIN prioridades p ON e.id_conjunto = p.id_conjunto;

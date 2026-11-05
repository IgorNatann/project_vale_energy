CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_gold}.continuidade_conjunto_mes
COMMENT 'Insumos mensais de continuidade por conjunto. A base de UCs é a do cadastro atual, não um histórico regulatório.'
AS WITH conjuntos AS (
  SELECT id_conjunto, max(nome_conjunto) AS nome_conjunto, max(municipio) AS municipio, count(*) AS total_ucs
  FROM ${catalogo}.${schema_silver}.unidades_consumidoras GROUP BY id_conjunto
), meses AS (
  SELECT explode(sequence(to_date(min(mes_apuracao)), to_date(max(mes_apuracao)), INTERVAL 1 MONTH)) AS mes_apuracao
  FROM ${catalogo}.${schema_silver}.interrupcoes_validas
), eventos AS (
  SELECT id_conjunto, to_date(mes_apuracao) AS mes_apuracao,
    sum(uc_horas_interrompidas) AS uc_horas_interrompidas, sum(qtd_ucs_afetadas) AS uc_interrupcoes,
    count(*) AS qtd_interrupcoes, count_if(causa_climatica) AS qtd_interrupcoes_climaticas,
    count_if(lower(tipo) = 'programada') AS qtd_interrupcoes_programadas, max(duracao_horas) AS maior_duracao_horas
  FROM ${catalogo}.${schema_silver}.interrupcoes_validas GROUP BY id_conjunto, to_date(mes_apuracao)
)
SELECT c.*, m.mes_apuracao, coalesce(e.uc_horas_interrompidas, 0) AS uc_horas_interrompidas,
  coalesce(e.uc_interrupcoes, 0) AS uc_interrupcoes, coalesce(e.qtd_interrupcoes, 0) AS qtd_interrupcoes,
  coalesce(e.qtd_interrupcoes_climaticas, 0) AS qtd_interrupcoes_climaticas,
  coalesce(e.qtd_interrupcoes_programadas, 0) AS qtd_interrupcoes_programadas,
  coalesce(e.maior_duracao_horas, 0) AS maior_duracao_horas
FROM conjuntos c CROSS JOIN meses m LEFT JOIN eventos e ON c.id_conjunto = e.id_conjunto AND m.mes_apuracao = e.mes_apuracao;

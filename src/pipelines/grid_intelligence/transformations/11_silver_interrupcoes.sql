CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.interrupcoes_validas
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  to_date(inicio) AS data_evento,
  date_trunc('MONTH', inicio) AS mes_apuracao,
  duracao_minutos / 60.0 AS duracao_horas,
  duracao_minutos / 60.0 * qtd_ucs_afetadas AS uc_horas_interrompidas,
  causa = 'climatica' AS causa_climatica
FROM STREAM(${catalogo}.${schema_bronze}.interrupcoes)
-- Abaixo do limiar, o religador pode restabelecer a rede em segundos.
-- Essas ocorrências permanecem na bronze, fora dos indicadores de continuidade.
WHERE duracao_minutos >= ${duracao_minima_interrupcao};

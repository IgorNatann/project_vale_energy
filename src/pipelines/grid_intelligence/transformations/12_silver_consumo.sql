CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.consumo_diario
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  c.*,
  u.id_conjunto, u.nome_conjunto, u.bairro, u.classe_consumo
FROM ${catalogo}.${schema_bronze}.consumo_diario c
JOIN ${catalogo}.${schema_silver}.unidades_consumidoras u ON c.id_uc = u.id_uc
WHERE c.consumo_kwh >= 0
  AND c.consumo_kwh <= CASE u.classe_consumo
    WHEN 'residencial' THEN 100
    WHEN 'comercial' THEN 500
    WHEN 'industrial' THEN 10000
    WHEN 'rural' THEN 250
    WHEN 'poder_publico' THEN 2000
  END
QUALIFY row_number() OVER (PARTITION BY c.id_uc, c.data ORDER BY c.ingerido_em DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.baseline_consumo
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS WITH data_referencia AS (
  SELECT max(data) AS ultimo_dia FROM ${catalogo}.${schema_bronze}.consumo_diario
), por_uc AS (
  SELECT
    c.id_uc, c.id_conjunto, c.nome_conjunto, c.bairro, c.classe_consumo,
    avg(c.consumo_kwh) FILTER (WHERE c.data > date_sub(r.ultimo_dia, 120) AND c.data <= date_sub(r.ultimo_dia, 30)) AS consumo_medio_baseline_kwh,
    avg(c.consumo_kwh) FILTER (WHERE c.data > date_sub(r.ultimo_dia, 30)) AS consumo_medio_recente_kwh,
    count_if(c.data > date_sub(r.ultimo_dia, 120) AND c.data <= date_sub(r.ultimo_dia, 30)) AS dias_no_baseline,
    count_if(c.data > date_sub(r.ultimo_dia, 30)) AS dias_no_periodo_recente,
    bool_or(c.sinal_violacao_medidor) FILTER (WHERE c.data > date_sub(r.ultimo_dia, 30)) AS sinal_violacao_recente
  FROM ${catalogo}.${schema_silver}.consumo_diario c CROSS JOIN data_referencia r
  WHERE c.data > date_sub(r.ultimo_dia, 120)
  GROUP BY c.id_uc, c.id_conjunto, c.nome_conjunto, c.bairro, c.classe_consumo
)
SELECT *,
  try_divide(consumo_medio_recente_kwh - consumo_medio_baseline_kwh, consumo_medio_baseline_kwh) AS variacao_da_uc,
  try_divide(
    sum(consumo_medio_recente_kwh * dias_no_periodo_recente) OVER (PARTITION BY id_conjunto),
    sum(dias_no_periodo_recente) OVER (PARTITION BY id_conjunto)
  ) AS consumo_medio_recente_conjunto_kwh,
  try_divide(
    sum(consumo_medio_baseline_kwh * dias_no_baseline) OVER (PARTITION BY id_conjunto),
    sum(dias_no_baseline) OVER (PARTITION BY id_conjunto)
  ) AS consumo_medio_baseline_conjunto_kwh,
  try_divide(consumo_medio_recente_conjunto_kwh - consumo_medio_baseline_conjunto_kwh, consumo_medio_baseline_conjunto_kwh) AS variacao_do_conjunto
FROM por_uc;

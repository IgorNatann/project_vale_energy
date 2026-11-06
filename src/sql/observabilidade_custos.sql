-- Consumo atribuído ao job; outros serviços podem não carregar esse identificador.
SELECT usage_date, usage_metadata.job_run_id AS execucao, sku_name, usage_unit,
       sum(usage_quantity) AS consumo
FROM system.billing.usage
WHERE usage_date >= date_sub(current_date(), CAST(:dias AS INT))
  AND usage_metadata.job_id = :job_id
GROUP BY usage_date, usage_metadata.job_run_id, sku_name, usage_unit
ORDER BY usage_date DESC, execucao, sku_name;

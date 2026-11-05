CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_gold}.prioridade_inspecao_uc
COMMENT 'Prioridade explicável de visita técnica baseada em variação de consumo e sinal do medidor.'
AS WITH eixos AS (
  SELECT *, variacao_da_uc < -${queda_minima_consumo} AS caiu_contra_si,
    abs(variacao_do_conjunto) <= ${variacao_maxima_conjunto} AS vizinhanca_estavel
  FROM ${catalogo}.${schema_silver}.baseline_consumo
), classificadas AS (
  SELECT *, coalesce(caiu_contra_si AND vizinhanca_estavel, false) AS atende_os_dois_eixos
  FROM eixos
)
SELECT id_uc, id_conjunto, nome_conjunto, bairro, classe_consumo,
  CASE WHEN atende_os_dois_eixos AND sinal_violacao_recente THEN 'alta'
       WHEN atende_os_dois_eixos OR sinal_violacao_recente THEN 'media' ELSE 'baixa' END AS prioridade_inspecao,
  caiu_contra_si, vizinhanca_estavel, atende_os_dois_eixos, sinal_violacao_recente,
  variacao_da_uc, variacao_do_conjunto, consumo_medio_baseline_kwh, consumo_medio_recente_kwh,
  dias_no_baseline, dias_no_periodo_recente,
  CASE WHEN atende_os_dois_eixos AND sinal_violacao_recente THEN 'Queda individual com conjunto estável e sinal no medidor'
       WHEN atende_os_dois_eixos THEN 'Queda individual com conjunto estável'
       WHEN sinal_violacao_recente THEN 'Sinal recente no medidor'
       WHEN vizinhanca_estavel IS NULL THEN 'Queda individual sem dados de variação do conjunto'
       ELSE 'Queda acompanhada de variação no conjunto' END AS motivo_observado
FROM classificadas WHERE caiu_contra_si OR sinal_violacao_recente;

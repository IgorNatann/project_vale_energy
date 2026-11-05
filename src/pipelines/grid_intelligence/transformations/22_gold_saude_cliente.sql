CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_gold}.saude_cliente
COMMENT 'Sinais de atendimento por cliente. A última fala passa por mascaramento automático sujeito a falhas.'
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS WITH chamados AS (
  SELECT *, max(abertura) OVER () AS data_referencia
  FROM ${catalogo}.${schema_silver}.chamados_enriquecidos
), clientes AS (
  SELECT id_cliente,
    max_by(id_conjunto, struct(abertura, id_chamado)) AS id_conjunto,
    max_by(nome_conjunto, struct(abertura, id_chamado)) AS nome_conjunto,
    max_by(bairro, struct(abertura, id_chamado)) AS bairro,
    count(*) AS qtd_chamados, count(DISTINCT id_uc) AS qtd_ucs_com_chamado,
    count_if(sentimento = 'negative') AS qtd_chamados_negativos,
    try_divide(count_if(sentimento = 'negative'), count(*)) AS proporcao_negativa,
    count_if(ameacou_ouvidoria) AS qtd_mencoes_ouvidoria,
    count_if(risco_a_saude) AS qtd_chamados_risco_saude,
    count_if(urgencia = 'alta') AS qtd_urgencia_alta,
    count_if(abertura > data_referencia - INTERVAL 30 DAYS) >= 3 AS reincidente,
    count_if(abertura > data_referencia - INTERVAL 30 DAYS AND sentimento = 'negative') AS negativos_recentes,
    mode(motivo, true) AS motivo_predominante,
    max_by(equipamento_citado, struct(abertura, id_chamado))
      FILTER (WHERE equipamento_citado IS NOT NULL AND equipamento_citado <> '') AS ultimo_equipamento_citado,
    max_by(transcricao_anonimizada, struct(abertura, id_chamado)) AS ultima_fala,
    min(abertura) AS primeiro_chamado_em, max(abertura) AS ultimo_chamado_em
  FROM chamados GROUP BY id_cliente
)
SELECT * EXCEPT (negativos_recentes),
  CASE WHEN qtd_mencoes_ouvidoria > 0 THEN 'alto'
       WHEN reincidente AND negativos_recentes > 0 THEN 'alto'
       WHEN qtd_chamados_risco_saude > 0 THEN 'medio' ELSE 'baixo' END AS risco_ouvidoria
FROM clientes;

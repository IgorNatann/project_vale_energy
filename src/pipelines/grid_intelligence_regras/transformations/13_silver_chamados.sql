-- Regras de texto não compreendem ironia, negação, sinônimos nem motivos compostos.
-- Nomes diferentes do cadastro e endereços livres podem não ser mascarados.

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_texto}.chamados_anonimizados
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  c.id_chamado, c.id_uc, u.id_cliente, u.id_conjunto, u.nome_conjunto, u.bairro, u.classe_consumo,
  c.abertura, to_date(c.abertura) AS data_chamado, hour(c.abertura) AS hora_chamado,
  c.canal, c.duracao_segundos, c.origem, c.ingerido_em, c.arquivo_origem, c.ingerido_bronze_em,
  coalesce(
    regexp_replace(
      regexp_replace(
        replace(c.transcricao, coalesce(c.nome_solicitante, ''), '[MASCARADO]'),
        r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '[MASCARADO]'),
      r'(?<!\d)(?:\(?\d{2}\)?[ .-]?)?9?\d{4}[ .-]?\d{4}(?!\d)', '[MASCARADO]'),
    '[RESTRITO]') AS transcricao_anonimizada,
  'regras_de_texto' AS anonimizado_por
FROM ${catalogo}.${schema_bronze}.chamados c
JOIN ${catalogo}.${schema_silver}.unidades_consumidoras u ON c.id_uc = u.id_uc;

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_texto}.chamados_enriquecidos
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  CASE
    WHEN transcricao_anonimizada = '[RESTRITO]' THEN 'indisponivel'
    WHEN transcricao_anonimizada RLIKE r'(?i)reclama|irritad|absurdo|insatisfeit|péssim|pessim' THEN 'negative'
    WHEN transcricao_anonimizada RLIKE r'(?i)obrigad|agrade[cç]|excelente' THEN 'positive'
    ELSE 'neutral'
  END AS sentimento,
  -- A prioridade de risco vem antes de pedidos genéricos, como religação.
  CASE
    WHEN transcricao_anonimizada = '[RESTRITO]' THEN 'indisponivel'
    WHEN transcricao_anonimizada RLIKE r'(?i)oxig[eê]nio|di[aá]lise|rem[eé]dio|crian[cç]a|hospital|fa[ií]sca|inc[eê]ndio|idoso' THEN 'religacao_urgente'
    WHEN transcricao_anonimizada RLIKE r'(?i)escuro|sem energia|apagou|falta de energia|sem luz' THEN 'falta_energia'
    WHEN transcricao_anonimizada RLIKE r'(?i)piscando|oscila|queimou|tens[aã]o' THEN 'oscilacao_tensao'
    WHEN transcricao_anonimizada RLIKE r'(?i)releitura|estimativa|n[aã]o bate' THEN 'erro_leitura'
    WHEN transcricao_anonimizada RLIKE r'(?i)conta veio|dobro|fatura subiu|trezentos reais' THEN 'fatura_alta'
    WHEN transcricao_anonimizada RLIKE r'(?i)poste|galho|l[aâ]mpada da rua' THEN 'poste_avariado'
    WHEN transcricao_anonimizada RLIKE r'(?i)religa[cç][aã]o|religar|paguei' THEN 'religacao'
    ELSE 'duvida_cadastral'
  END AS motivo,
  CASE WHEN transcricao_anonimizada <> '[RESTRITO]' THEN
    regexp_extract(transcricao_anonimizada, r'(?i)poste|transformador|medidor|geladeira|chuveiro', 0)
  END AS equipamento_citado,
  CASE WHEN transcricao_anonimizada <> '[RESTRITO]' THEN
    transcricao_anonimizada RLIKE r'(?i)oxig[eê]nio|di[aá]lise|rem[eé]dio|crian[cç]a|hospital|fa[ií]sca|inc[eê]ndio|idoso'
  END AS risco_a_saude,
  CASE
    WHEN transcricao_anonimizada = '[RESTRITO]' THEN 'indeterminada'
    WHEN risco_a_saude THEN 'alta'
    WHEN motivo IN ('falta_energia', 'religacao_urgente', 'poste_avariado') THEN 'media'
    ELSE 'baixa'
  END AS urgencia,
  CASE WHEN transcricao_anonimizada <> '[RESTRITO]' THEN
    transcricao_anonimizada RLIKE r'(?i)ouvidoria|aneel|procon|processo'
  END AS ameacou_ouvidoria,
  'regras_de_texto' AS enriquecido_por
FROM ${catalogo}.${schema_texto}.chamados_anonimizados;

-- Ao regerar os arquivos, use full refresh: permitir sobrescritas reprocessa o arquivo,
-- mas a streaming table mantém as linhas antigas e duplica os dados.

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_bronze}.unidades_consumidoras
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  _metadata.file_path AS arquivo_origem,
  current_timestamp() AS ingerido_bronze_em
FROM STREAM read_files(
  '${volume_landing}/unidades_consumidoras/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_bronze}.interrupcoes
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  _metadata.file_path AS arquivo_origem,
  current_timestamp() AS ingerido_bronze_em
FROM STREAM read_files(
  '${volume_landing}/interrupcoes/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_bronze}.consumo_diario
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  _metadata.file_path AS arquivo_origem,
  current_timestamp() AS ingerido_bronze_em
FROM STREAM read_files(
  '${volume_landing}/consumo_diario/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_bronze}.chamados
TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')
AS SELECT
  *,
  _metadata.file_path AS arquivo_origem,
  current_timestamp() AS ingerido_bronze_em
FROM STREAM read_files(
  '${volume_landing}/chamados/',
  format => 'parquet'
);

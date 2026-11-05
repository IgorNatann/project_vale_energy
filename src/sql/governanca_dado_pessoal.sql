-- Um full refresh pode recriar a tabela. O job reaplica as máscaras após o pipeline;
-- execuções diretas do pipeline precisam ser seguidas desta mesma task.
USE CATALOG IDENTIFIER(:catalogo);
USE SCHEMA IDENTIFIER(:schema_bronze);

CREATE OR REPLACE FUNCTION mascarar_dado_pessoal(valor STRING)
RETURNS STRING
RETURN IF(is_member(:grupo_atendimento), valor, '[RESTRITO]');

ALTER STREAMING TABLE chamados ALTER COLUMN nome_solicitante SET MASK mascarar_dado_pessoal;
ALTER STREAMING TABLE chamados ALTER COLUMN telefone_solicitante SET MASK mascarar_dado_pessoal;
ALTER STREAMING TABLE chamados ALTER COLUMN transcricao SET MASK mascarar_dado_pessoal;

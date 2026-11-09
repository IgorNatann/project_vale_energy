# Escopo — Grid Intelligence

Este documento espelha a [sequência de prompts](../prompts/README.md): para cada etapa,
registra o que estava no escopo, o que foi entregue e onde houve desvio. O domínio, o
glossário e as regras de negócio ficam no [PRD](prd.md); a rastreabilidade de cada regra
até o código fica em [regras de negócio](../docs/regras-de-negocio.md).

## Objetivo

Construir, no Databricks, a plataforma de dados e IA da Luz do Vale Distribuidora: ingerir
as quatro bases sintéticas, aplicar as regras de negócio RN-01 a RN-14 e publicar quatro
entregas gold, uma definição única de DEC e FEC, um dashboard, um copiloto Genie e um
relatório executivo.

## Escopo por etapa

| # | Escopo do prompt | Entregue | Desvios e observações |
|---|---|---|---|
| 00 | PRD, catálogos por ambiente, schemas `raw`, `bronze`, `silver` e `gold`, volume `raw.landing` | [`prd.md`](prd.md), [`databricks.yml`](../databricks.yml), [`grid_schemas.yml`](../resources/grid_schemas.yml) | O profile da CLI é `project_vale_energy`, não `grid_intelligence`. Os comandos usam `--profile <perfil>`. |
| 01 | Ingestão fiel das quatro bases, com `arquivo_origem` e `ingerido_bronze_em` | [`01_bronze.sql`](../src/pipelines/grid_intelligence/transformations/01_bronze.sql) | — |
| 02 | Cadastro limpo, RN-01 por configuração, deduplicação do consumo e baseline | [`10_silver_cadastro.sql`](../src/pipelines/grid_intelligence/transformations/10_silver_cadastro.sql), [`11_silver_interrupcoes.sql`](../src/pipelines/grid_intelligence/transformations/11_silver_interrupcoes.sql), [`12_silver_consumo.sql`](../src/pipelines/grid_intelligence/transformations/12_silver_consumo.sql) | — |
| 03-A | Anonimização e enriquecimento das transcrições com AI Functions; máscara de coluna | [`13_silver_chamados.py`](../src/pipelines/grid_intelligence/transformations/13_silver_chamados.py), [`governanca_dado_pessoal.sql`](../src/sql/governanca_dado_pessoal.sql) | Rota principal do projeto. |
| 03-B | O mesmo contrato de colunas, só com regex e `CASE` | [`grid_intelligence_regras`](../src/pipelines/grid_intelligence_regras/transformations/13_silver_chamados.sql) | A sequência pede uma das duas rotas; as duas foram entregues. A rota por regras grava em `silver_regras` para não sobrescrever a rota com IA. |
| 04 | Quatro tabelas gold e a metric view de DEC e FEC | [`20_gold_*` a `23_gold_*`](../src/pipelines/grid_intelligence/transformations/), [`metric_view_continuidade.sql`](../src/sql/metric_view_continuidade.sql) | A RN-03 (numerador do FEC) não estava definida e foi fixada no projeto como a soma das UCs afetadas. |
| 05 | Dashboard AI/BI de duas páginas, declarado no bundle | [`grid_intelligence.lvdash.json`](../src/dashboards/grid_intelligence.lvdash.json) | — |
| 06 | Copiloto Genie em português, só sobre a gold, com definição versionada | [`grid_intelligence.json`](../src/genie/grid_intelligence.json), [`aplicar_agente_genie.py`](../scripts/aplicar_agente_genie.py) | O espaço Genie não é recurso do bundle; o script o aplica a partir da definição versionada. |
| 07 | Relatório executivo, oito consultas de demonstração, README e AGENTS.md | [`relatorio_executivo.py`](../src/notebooks/relatorio_executivo.py), [`demonstracao.sql`](../src/sql/demonstracao.sql), [README](../README.md), [AGENTS.md](../AGENTS.md) | Resultados em [resultados da demonstração](../docs/resultados-demonstracao.md) e [relatório de exemplo](../docs/relatorio-executivo-exemplo.md). |

O job [`processar_grid`](../resources/grid_intelligence.job.yml) encadeia o pipeline, a
aplicação das máscaras, a publicação da metric view e o relatório.

## Extensões além da sequência

Decisões do autor, fora do roteiro dos prompts:

- [Testes](../tests/) de regras e de integração com o workspace.
- [Integração contínua](../docs/integracao-continua.md) com Ruff e pytest em todo PR.
- [Validação de privacidade](../docs/validacao-privacidade.md) dos acessos ao dado pessoal.
- [Avaliação do Genie](../docs/avaliacao-genie.md) com perguntas de benchmark.
- [Observabilidade e custos](../docs/observabilidade-custos.md) a partir das tabelas de sistema.

## Fora do escopo

- **Dados reais.** As bases são sintéticas; os números descrevem a amostra.
- **Conformidade regulatória.** O dataset não traz os limites de DEC e FEC de cada
  conjunto, então os indicadores não dizem se houve violação.
- **Modelo de detecção treinado.** A inspeção é uma prioridade explicável por regras
  (RN-06 a RN-08), não um classificador nem um rótulo de irregularidade.
- **Série histórica do cadastro.** A base de UCs é a do cadastro atual em todos os meses.
- **Operação em produção.** O target `prod` existe no bundle, mas a validação foi feita
  em `dev`; agendamento, alertas e permissões de outros grupos não foram configurados.

## Pendências conhecidas

- Validar o acesso aos dados pessoais com uma identidade fora do grupo `atendimento`.
- Revisar as permissões da landing, que a máscara da bronze não protege.

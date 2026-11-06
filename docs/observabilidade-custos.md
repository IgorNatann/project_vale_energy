# Observabilidade e custos

O histórico de execução e o consumo faturável respondem a perguntas diferentes: duração
não é custo, e o sucesso do job não prova qualidade nem atualização de todos os dados.

## Acompanhar o job

Com a CLI autenticada e o ID do job de seu ambiente:

```powershell
databricks jobs list-runs --job-id <JOB_ID> --limit 10 --profile project_vale_energy -o json
databricks jobs get-run <RUN_ID> --profile project_vale_energy -o json
```

Observe o resultado, mensagens, tarefas e `run_duration` em milissegundos. Consulte os
detalhes da atualização do pipeline e as expectativas de qualidade quando o job falhar ou
seu resultado for inesperado. Uma execução parcial pode não atualizar todas as tabelas;
confira as dependências e a data dos dados antes de usá-la. Não compare diretamente
execuções com escopos ou condições diferentes.

Na inspeção de 06/11/2026 do job de desenvolvimento, a execução `634910318939531`
terminou com sucesso em 782.626 ms (aproximadamente 13 minutos). É uma observação daquele
ambiente, não uma meta nem estimativa de tempo futuro. A rota de IA pode reprocessar textos
durante atualizações; avalie o plano e os eventos antes de executar novamente uma carga
completa, pois isso pode consumir recursos e produzir novas classificações.

## Consultar consumo atribuído

Quando houver acesso à tabela de sistema, execute a consulta versionada com um warehouse,
o ID do job e uma janela de dias:

```powershell
databricks experimental aitools tools query --profile project_vale_energy --warehouse <WAREHOUSE_ID> --file src/sql/observabilidade_custos.sql --param job_id=<JOB_ID> --param dias:INT=7
```

O resultado agrupa quantidade, unidade e SKU por data e execução; preserva registros
negativos de correção. Ele **não representa necessariamente o custo total do projeto**:
SQL warehouse, pipeline, Genie e outras atividades podem ter atribuição diferente ou não
carregar o ID do job. Dados de faturamento podem chegar com atraso e exigir permissões
próprias. Para estimar valores monetários, concilie SKU, unidade, moeda e intervalo de
vigência com preços aplicáveis e descontos; DBU não é moeda.

Na consulta de 06/11/2026, o filtro pelo job encontrou registros de inferência serverless
para duas execuções recentes, inclusive 0,0197 DBU para `634910318939531`. Esse número
cobre somente os registros associados ao filtro naquela consulta; não é o custo completo
da execução, e os dados podem mudar com atrasos ou correções.

## Próximos passos operacionais

- Definir responsáveis, orçamento e limiares de alerta adequados ao ambiente antes de
  agendar execuções frequentes.
- Acompanhar tarefas, falhas, dados atualizados e expectativas do pipeline após cada carga.
- Analisar os registros de uso de cada componente antes de estabelecer o custo total.

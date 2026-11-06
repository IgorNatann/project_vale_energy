# Avaliação diagnóstica do Genie

O arquivo [versionado do espaço](../src/genie/grid_intelligence.json) contém seis questões
de avaliação em `benchmarks`, separadas dos exemplos apresentados ao agente. Cobrem
prioridade por conjunto e bairro, risco de ouvidoria, DEC, FEC e chamados na última data com
eventos. Cada resposta esperada é uma consulta SQL sobre a Gold. As seis consultas foram
executadas com sucesso no warehouse do ambiente `grid_dev` antes da avaliação.

Em 06/11/2026, a avaliação nativa em modo Chat, execução
`01f1da06b8c11fa0bd53dd8226849c06`, concluiu **6 de 6 consultas corretas**, sem itens
marcados para revisão. O conjunto usa dados sintéticos e uma única execução; é pequeno,
possui questões semelhantes a exemplos conhecidos e não sustenta uma taxa de precisão
generalizável. A avaliação compara resultados SQL, não a qualidade do texto sintetizado,
segurança de acesso ou a exatidão das regras de negócio. A execução anterior usou questões
com caracteres corrompidos e foi descartada; esta usou as perguntas corrigidas.

Para reproduzir depois de aplicar o espaço versionado com
[`scripts/aplicar_agente_genie.py`](../scripts/aplicar_agente_genie.py), crie um arquivo
UTF-8 `benchmark-pedido.json` com os IDs dos itens que deseja avaliar:

```json
{"benchmark_question_ids": ["40000000000000000000000000000001", "40000000000000000000000000000002"]}
```

```powershell
databricks genie genie-create-eval-run <SPACE_ID> --json '@benchmark-pedido.json' --profile project_vale_energy -o json
databricks genie genie-get-eval-run <SPACE_ID> <EVAL_RUN_ID> --profile project_vale_energy -o json
databricks genie genie-list-eval-results <SPACE_ID> <EVAL_RUN_ID> --profile project_vale_energy -o json
databricks genie genie-get-eval-result-details <SPACE_ID> <EVAL_RUN_ID> <RESULT_ID> --profile project_vale_energy -o json
```

Esses comandos Beta podem mudar e a avaliação consome recursos. Um corpo vazio executa
todas as questões; revise o nome `benchmark_question_ids` para limitar o escopo. Para
avaliar sínteses, recusas e fidelidade das afirmações, continue a revisão independente em
[validação do Genie](validacao-agente-genie.md), onde há falhas observadas. Evolua a bateria
com perguntas representativas, respostas revisadas e casos mais difíceis antes de usar
qualquer pontuação como indicador de qualidade.

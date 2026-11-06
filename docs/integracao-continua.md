# Integração contínua

O workflow [validacao.yml](../.github/workflows/validacao.yml) roda em PRs e na `main`:
instala as dependências a partir do `uv.lock`, executa o Ruff e roda o pytest sem workspace.
Ele usa somente permissão de leitura do repositório e não recebe credenciais do Databricks.

Os testes marcados `databricks` e `reexecucao` são ignorados nesse fluxo. Uma execução verde
confirma os testes locais, não o deploy, os dados nem a integração com o workspace. Para
validar a integração em desenvolvimento, siga o comando `pytest --databricks` no README e
execute `databricks bundle validate --strict -t dev --profile project_vale_energy` com o
perfil apropriado. A opção de reexecução tem custo e deve ser selecionada explicitamente.

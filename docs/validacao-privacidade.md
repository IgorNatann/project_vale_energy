# Validação de privacidade

Em 06/11/2026, a inspeção com o perfil `project_vale_energy` retornou concessão direta
`ALL_PRIVILEGES` no catálogo `grid_dev` para o proprietário e nenhuma concessão direta nos
objetos consultados: `raw`, volume `raw.landing`, `bronze.chamados`, `gold` e
`gold.saude_cliente`. **Isso não prova acesso efetivo de outros usuários**: permissões podem
ser herdadas, concedidas a grupos ou alteradas depois da consulta.

As máscaras da bronze não protegem os arquivos originais no volume. A Gold contém
`ultima_fala`, cujo mascaramento automático pode não reconhecer todos os dados pessoais.
O dashboard usa as permissões de quem consulta. A exclusão da coluna do contexto do Genie
não remove privilégios da identidade que executa a consulta.

Os testes [test_privacidade_identidades.py](../tests/test_privacidade_identidades.py)
verificam a identidade externa, os valores mascarados e a negação de acesso à landing sem
imprimir transcrições. Exigem um segundo perfil no **mesmo workspace**, fora de `atendimento`,
com acesso à tabela de teste para verificar a máscara e sem acesso aos arquivos originais:

```bash
uv run pytest -q tests/test_privacidade_identidades.py --databricks \
  --perfil project_vale_energy --perfil-nao-atendimento PERFIL_DE_TESTE --catalogo grid_dev
```

Sem esse perfil os testes são ignorados. Na revisão de 06/11/2026 não havia uma segunda
identidade disponível; portanto **o acesso efetivo de não membros e a proteção da landing
permanecem pendentes de validação**. Não foram criados usuários nem concedidos privilégios.

# PRD — Grid Intelligence

Plataforma de dados e IA da **Luz do Vale Distribuidora S.A.**, distribuidora de energia
elétrica fictícia, construída no Databricks. Este documento é a referência de todos os
prompts da sequência: consulte-o antes de criar qualquer objeto.

## Domínio

A distribuidora opera sob regulação da ANEEL e tem três dores simultâneas, todas
mensuráveis em dinheiro:

1. **Continuidade do fornecimento.** Interromper além do limite regulatório gera
   compensação financeira automática ao consumidor. Em 2024 as distribuidoras brasileiras
   pagaram mais de R$ 1,1 bilhão em compensações.
2. **Perdas não técnicas.** Energia distribuída e não faturada: furto, fraude e erro de
   medição. Em 2025 somaram ~R$ 11,5 bilhões, dos quais ~R$ 7,9 bilhões foram repassados
   à tarifa.
3. **Atendimento ao cliente.** Milhares de ligações viram transcrição e ninguém lê. Dentro
   delas está o aviso antecipado da reclamação na ouvidoria.

## Glossário

Use estes termos, sem sinônimo aproximado.

| Termo | Definição |
|---|---|
| **UC — Unidade Consumidora** | O ponto de entrega de energia. **Não é sinônimo de cliente**: um cliente pode ter várias UCs |
| **Conjunto** | Subdivisão geográfica da área de concessão. É a unidade de agregação do regulador |
| **DEC** | Duração Equivalente de Interrupção por UC: tempo médio, em horas, sem fornecimento |
| **FEC** | Frequência Equivalente de Interrupção por UC: número médio de interrupções |
| **PNT** | Perdas Não Técnicas |
| **Prioridade de inspeção** | Classificação de quanto uma UC merece visita técnica |

## Regras de negócio

| Regra | Enunciado |
|---|---|
| **RN-01** | Só interrupções com **3 minutos ou mais** entram na apuração de DEC e FEC. A regra vive na camada de transformação, nunca no relatório |
| **RN-02** | O numerador do DEC é `duracao_horas × qtd_ucs_afetadas` (`uc_horas_interrompidas`), calculado na silver |
| **RN-03** | O numerador do FEC é a soma de `qtd_ucs_afetadas` dos eventos válidos (`uc_interrupcoes`): cada UC atingida conta uma interrupção |
| **RN-04** | DEC e FEC têm **uma única definição** no sistema, consumida por dashboard, agente e relatório |
| **RN-05** | DEC e FEC são apurados **por mês** (`mes_apuracao = date_trunc('MONTH', inicio)`) |
| **RN-06** | Uma UC é candidata a inspeção quando o consumo cai em **dois eixos simultâneos**: contra o próprio baseline **e** enquanto a vizinhança permanece estável. Só o primeiro eixo apontaria o bairro inteiro depois de um apagão |
| **RN-07** | A saída da detecção é **prioridade de inspeção** (alta, média, baixa). **Nunca** um rótulo de fraude, furto ou culpa. Queda de consumo também é mudança de morador, imóvel desocupado, defeito de medidor e erro de leitura. Nenhuma coluna, variável ou comentário pode usar "fraude", "furto" ou "culpado" como rótulo de saída |
| **RN-08** | A prioridade de inspeção é **regra explicável, não modelo treinado**: não há rótulo confiável de irregularidade no dataset. Qualquer pessoa tem de conseguir reconstruir por que uma UC entrou na lista |
| **RN-09** | Dado pessoal em transcrição é **mascarado antes** de qualquer análise de conteúdo |
| **RN-10** | O texto original identificado é preservado com **acesso restrito**. Duas proteções que coexistem: uma na leitura, outra na análise |
| **RN-11** | A camada de ingestão **não filtra, não corrige e não aplica regra de negócio**. Leitura inválida de medidor é um fato sobre o medidor. Filtrar na ingestão é destruição de evidência |
| **RN-12** | Todo registro ingerido carrega origem e momento de ingestão |
| **RN-13** | O agente conversacional acessa **apenas a camada de negócio** (gold) |
| **RN-14** | As entidades da **camada gold** carregam descrição em linguagem de negócio, que é o que o agente lê. Bronze e silver não precisam: são passagem |

RN-02, RN-05 e RN-08 não estão no prompt 00. Os enunciados acima vêm de onde são
aplicadas, nos prompts 02 e 04. A RN-03 não aparece em nenhum prompt: foi definida no
projeto como a contraparte da RN-02 para o FEC, documentando o cálculo já implementado na
gold e na metric view.

## Diretriz de simplicidade

O projeto é construído **ao vivo, em aula**. Código que ninguém lê na tela em dez segundos
não serve, mesmo que seja mais robusto.

- **Sem expectations e sem `CONSTRAINT`.** Regra de negócio vira `WHERE`.
- **Sem `COMMENT` em bronze e silver.** Só a gold e a metric view levam descrição (RN-14).
- **Sem `TBLPROPERTIES`, `CLUSTER BY` e afins**, a menos que sem eles quebre.
- **Sem tratamento de caso que o dataset não tem.**
- **Um `SELECT` direto vence um `WITH` de quatro CTEs.**
- Comentário só onde a decisão **não é óbvia pelo código**.
- Validação extra não se acrescenta: descreve-se em uma linha e o dono do projeto decide.

## Convenções

- Todo texto e todo nome em **português do Brasil**; entidades, colunas e arquivos **sem
  acentuação**.
- Funções usam nomes em português do Brasil, sem acentos e em `snake_case`, preservando
  nomes exigidos por ferramentas, como `test_` e os hooks `pytest_*`.
- **Nenhum catálogo fixado em código**: vem de `${var.catalog}`. Schema vem de
  `${resources.schemas.<camada>.name}`.
- **Nenhum modelo de IA fixado em código**: use as funções `ai_*` do Databricks.
- Tabelas não repetem a camada no nome: `bronze.chamados`, nunca `bronze_chamados`.

## Arquitetura

| Camada | Schema | Papel |
|---|---|---|
| Landing | `raw` (volume `landing`) | Arquivos Parquet, uma pasta por base |
| Bronze | `bronze` | Ingestão fiel, sem regra de negócio (RN-11, RN-12) |
| Silver | `silver` | Limpeza, RN-01, deduplicação, baseline, anonimização |
| Gold | `gold` | Entregas de negócio e metric view, com descrição (RN-14) |

Os ambientes ficam isolados **por catálogo**; os schemas têm o mesmo nome nos dois.

| Ambiente | Catálogo |
|---|---|
| `dev` | `grid_dev` |
| `prod` | `grid_intelligence` |

## Modelo de informação

Quatro bases sintéticas, com quatro anos de histórico, crescimento de 30% ao ano na carga
e sazonalidade de verão no atendimento (dezembro a março recebem quase o dobro de
ligações).

```
cliente 1 ──── N unidade_consumidora N ──── 1 conjunto
                    │                            │
                    ├── N consumo_diario         └── N interrupcao
                    └── N chamado
```

As interrupções são registradas **por conjunto**, não por UC: o evento informa quantas UCs
afetou (`qtd_ucs_afetadas`), não quais.

### `unidades_consumidoras` (4.000 linhas, uma por ponto de entrega)

`id_uc`, `id_cliente`, `id_conjunto`, `nome_conjunto`, `municipio`, `bairro`,
`logradouro`, `classe_consumo`, `subgrupo_tarifario`, `tensao_nominal_v`, `situacao`,
`data_ligacao`, `possui_medidor_inteligente`, `consumo_medio_kwh_dia`, `latitude`,
`longitude`, `origem`, `ingerido_em`

### `interrupcoes` (1.383 linhas, uma por evento de rede)

`id_interrupcao`, `id_conjunto`, `inicio`, `fim`, `duracao_minutos`, `tipo`, `causa`,
`equipamento`, `qtd_ucs_afetadas`, `origem`, `ingerido_em`

### `consumo_diario` (5.854.587 linhas, uma por UC por dia)

`id_uc`, `data`, `consumo_kwh`, `horas_com_leitura`, `sinal_violacao_medidor`, `origem`,
`ingerido_em`

### `chamados` (2.801 linhas, uma por ligação)

`id_chamado`, `id_uc`, `abertura`, `canal`, `nome_solicitante`, `telefone_solicitante`,
`transcricao`, `duracao_segundos`, `origem`, `ingerido_em`

`nome_solicitante`, `telefone_solicitante` e `transcricao` contêm dado pessoal (RN-09,
RN-10).

### Defeitos propositais

Consumo nulo, negativo e fisicamente impossível, linhas duplicadas e interrupções abaixo de
3 minutos. Não são bug: existem para as validações de qualidade e a RN-01 terem o que fazer.

## Entregas de negócio

| Entrega | Grão | Pergunta que responde |
|---|---|---|
| `gold.continuidade_conjunto_mes` | conjunto × mês | Estamos dentro do limite regulatório este mês? |
| `gold.prioridade_inspecao_uc` | uma UC candidata | Quais UCs merecem visita técnica primeiro? |
| `gold.saude_cliente` | um cliente | Quais clientes estão em rota de reclamação na ouvidoria? |
| `gold.painel_operacional_dia` | conjunto × dia | O que aconteceu ontem e o que precisa de ação hoje? |

A metric view `gold.continuidade_metricas` é **a definição única de DEC e FEC** (RN-04),
consumida pelo dashboard, pelo agente e pelo relatório.

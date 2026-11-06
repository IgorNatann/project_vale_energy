# Regras de negócio e aplicação nos dados

Este documento liga as decisões da Grid Intelligence às transformações que as aplicam.
Os dados são sintéticos e os resultados abaixo são uma fotografia das execuções de
desenvolvimento, não indicadores reais de uma distribuidora.

| Regra | Decisão e motivo | Aplicação | Evidência em dev |
|---|---|---|---|
| RN-11 | A ingestão preserva defeitos para que possam ser explicados e tratados depois. | [Bronze](../src/pipelines/grid_intelligence/transformations/01_bronze.sql): `SELECT *`, sem filtros. | Os quatro Parquet foram comparados às tabelas, incluindo duplicatas, sem divergências. |
| RN-12 | Cada registro precisa informar de onde veio e quando entrou na bronze. | Bronze acrescenta `arquivo_origem` e `ingerido_bronze_em`. | As duas colunas estavam preenchidas em todas as linhas ingeridas. |
| Cadastro | Padronizar a classe e identificar bairros ausentes sem inventar dados. UCs sem chave ou conjunto são descartadas. | [Cadastro silver](../src/pipelines/grid_intelligence/transformations/10_silver_cadastro.sql): `lower`, `trim`, `coalesce` e `WHERE`. | 4.000 UCs na execução verificada. |
| RN-01 | Só eventos de pelo menos 3 minutos participam de DEC e FEC; eventos curtos continuam na bronze. | [Interrupções silver](../src/pipelines/grid_intelligence/transformations/11_silver_interrupcoes.sql): limiar na configuração do pipeline. | 310 de 1.383 eventos ficaram fora da silver; 1.073 permaneceram. |
| RN-02 e RN-05 | O insumo aditivo de DEC é horas de interrupção multiplicadas pelas UCs afetadas; a apuração é mensal. | Interrupções silver calcula `uc_horas_interrompidas` e `mes_apuracao` por evento. | Cálculo conferido para os 1.073 eventos válidos. |
| Consumo | Leituras nulas, negativas ou acima do limite demonstrativo da classe não entram na silver; duplicatas mantêm a ingestão mais recente. | [Consumo silver](../src/pipelines/grid_intelligence/transformations/12_silver_consumo.sql): `WHERE`, `CASE` e `row_number`. | 5.801.814 leituras; nenhuma chave UC × dia repetida na execução verificada. |
| RN-06 a RN-08 | Comparar a UC com seu próprio histórico e com a variação do conjunto. A saída é uma prioridade explicável de visita técnica. | O baseline usa os últimos 30 dias e os 90 anteriores. A gold compara os dois eixos e o sinal do medidor. | Limiares demonstrativos aprovados e configuráveis: queda superior a 30% e variação do conjunto de até 10%. |
| RN-09 | Remover dados pessoais antes da análise de conteúdo. | [Rota com IA](../src/pipelines/grid_intelligence/transformations/13_silver_chamados.py) e [rota por regras](../src/pipelines/grid_intelligence_regras/transformations/13_silver_chamados.sql): a tabela enriquecida lê a anonimizada. | Na rota com IA, sete textos sem resposta de anonimização foram mantidos como `[RESTRITO]`. |
| RN-10 | A leitura do nome, telefone e texto original precisa de controle de acesso separado da anonimização. | [Governança](../src/sql/governanca_dado_pessoal.sql): máscaras por grupo na bronze, reaplicadas pelo job. | A vinculação das três máscaras e o acesso do membro autorizado foram verificados; falta testar uma identidade fora do grupo. |
| RN-04 e RN-14 | DEC/FEC têm definição única e as entidades gold levam descrição de negócio. | A tabela de continuidade guarda insumos e a metric view contém as medidas. | A base considera o cadastro atual e inclui meses sem eventos no período observado. |
| RN-13 | O agente deve acessar apenas a gold. | [Definição do Genie](../src/genie/grid_intelligence.json): quatro fontes gold configuradas. | Os SQLs observados nos testes consultaram somente gold; a restrição de fontes não substitui as permissões do usuário. |

## Limites demonstrativos de consumo

Os limites abaixo foram aprovados para os dados sintéticos em kWh por dia. São critérios de
plausibilidade para a demonstração, não limites físicos comprovados de ligações reais.

| Classe | Limite diário |
|---|---:|
| Residencial | 100 |
| Comercial | 500 |
| Industrial | 10.000 |
| Rural | 250 |
| Poder público | 2.000 |

## Evidências da gold em desenvolvimento

Na execução de 05/11/2026, a continuidade cobriu 288 combinações de conjunto e mês e
preservou os 1.073 eventos válidos da silver. Para junho e julho de 2026, a metric view
retornou DEC médio de 0,28167 hora por mês e DEC acumulado de 0,56334 hora. A diferença
confirma que os meses não foram tratados como um único denominador repetido.

Com os limiares demonstrativos aprovados, 20 UCs foram classificadas em prioridade alta,
todas no Jardim Aurora. A saúde apontou 84 clientes com risco alto de ouvidoria. Esse risco
é um sinal derivado dos chamados, não uma previsão validada, e os resultados com IA podem
variar entre execuções. As métricas usam o cadastro atual de UCs para todos os meses e o
dataset não contém limites regulatórios para aferir conformidade.

## Como interpretar as duas rotas de texto

As duas rotas preservam o mesmo contrato de colunas e identificam o método usado em cada
linha. A rota com IA utiliza funções `ai_*`; a rota por regras combina padrões e decisões
determinísticas. Em ambas, risco à saúde e menção à ouvidoria são sinais observados no
texto, não um diagnóstico ou uma confirmação de reclamação.

A rota SQL por regras lê a bronze e o cadastro silver, grava os resultados em
`silver_regras` e não altera as tabelas da rota com IA em `silver`. A execução conferida
processou 2.801 chamados, sem CPF ou telefone nos formatos pesquisados. Uma transcrição
continha uma palavra igual ao primeiro nome do solicitante: a palavra era parte de uma
localidade, evidenciando que a contagem automática precisa ser interpretada em contexto.

| Saída da rota por regras | Como a decisão é aplicada |
|---|---|
| `transcricao_anonimizada` | Substitui o nome cadastrado e os padrões de CPF e telefone; texto nulo vira `[RESTRITO]`. |
| `sentimento` | Termos de insatisfação têm prioridade sobre agradecimentos; sem correspondência, `neutral`. |
| `motivo` | O primeiro padrão encontrado vence: risco à saúde, falta de energia, oscilação, erro de leitura, fatura, poste, religação e dúvida cadastral. |
| `risco_a_saude` e `ameacou_ouvidoria` | Procuram termos explícitos no texto já anonimizado. |
| `urgencia` | Alta com sinal de risco; média para falta de energia, religação urgente ou poste avariado; baixa nos demais casos. Texto restrito fica indeterminado. |

Na execução verificada por regras, 591 chamados tiveram sinal de risco à saúde e 86
mencionaram ouvidoria, ANEEL, Procon ou processo. Esses números dependem das palavras
incluídas nas regras e não devem ser interpretados como verdade confirmada.

Na comparação observada em 05/11/2026, as rotas atribuíram o mesmo motivo a 2.042 dos
2.801 chamados e o mesmo sentimento a 845. Essa concordância descreve diferenças entre
abordagens; sem uma base de respostas revisadas, não mede qual delas está correta.

A rota por regras só mascara o nome conhecido e os formatos de CPF e telefone previstos.
Apelidos, nomes de outras pessoas e endereços livres podem permanecer. A rota com IA também
exige avaliação: detectar os padrões conhecidos não prova ausência de todo dado pessoal.
Os arquivos originais no volume exigem permissões próprias, pois a máscara da tabela bronze
não protege o acesso direto a eles.

RN-03 permanece sem definição nos materiais do projeto. RN-07 e RN-08 orientam a prioridade
explicável e não acusatória implementada na gold e as instruções do Genie.

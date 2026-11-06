# Como interpretar métricas e sinais de IA

O projeto usa dados sintéticos. As definições abaixo explicam decisões implementadas para
estudo; não comprovam conformidade regulatória, fraude ou diagnóstico de saúde. Para a
rastreabilidade completa das regras, consulte [regras de negócio](regras-de-negocio.md).

## Continuidade: DEC e FEC

Eventos com menos de três minutos ficam fora da silver de interrupções. Para cada evento
válido, o pipeline multiplica sua duração em horas pelo número de UCs afetadas e registra
também o número de UCs afetadas como quantidade de interrupções por UC. O mês de apuração
é o mês de início do evento. A tabela de continuidade combina esses insumos com a base
de UCs do cadastro **atual**, inclusive para meses passados; meses sem eventos são
preenchidos dentro do período observado. Isso não reconstitui a população histórica.

A [metric view](../src/sql/metric_view_continuidade.sql) reúne as definições reutilizadas
pelo dashboard e pelo Genie:

| Medida | Cálculo no recorte selecionado | Interpretação |
|---|---|---|
| DEC | Soma de UC-horas / soma das bases mensais | Duração média mensal por UC, em horas. |
| FEC | Soma de UCs afetadas nos eventos / soma das bases mensais | Frequência média mensal por UC. |
| DEC Acumulado | Soma de UC-horas / (soma das bases mensais / quantidade de meses distintos) | Duração acumulada por UC ao longo do período. |

Por exemplo, num conjunto com 800 UCs, um evento de duas horas que atinge 50 UCs
gera 100 UC-horas: DEC mensal de 0,125 hora e FEC mensal de 0,0625. Com dois meses
de mesma base e 100 UC-horas em cada, o DEC médio mensal continua 0,125 hora e o
DEC acumulado é 0,25 hora. Denominador zero resulta em `NULL`, não em zero inventado.
Essas fórmulas agregam o recorte selecionado; comparar períodos ou conjuntos exige
verificar que representam a população e os meses pretendidos.

## Prioridade de inspeção

O [baseline](../src/pipelines/grid_intelligence/transformations/12_silver_consumo.sql)
compara a média dos 30 dias mais recentes com a dos 90 anteriores, tendo como referência
a maior data da bronze. A variação do conjunto compara médias ponderadas pelo número de
leituras válidas. O projeto registra quantos dias contribuíram, mas não impõe uma cobertura
mínima: dados escassos ou ausentes podem tornar a comparação pouco representativa.

A [classificação](../src/pipelines/grid_intelligence/transformations/21_gold_prioridade_inspecao.sql)
usa os limiares demonstrativos aprovados: queda individual **superior** a 30% e variação
absoluta do conjunto de até 10%, ambos configuráveis. Prioridade alta exige os dois
critérios e um sinal recente no medidor; média exige os dois critérios ou o sinal; os
demais candidatos são baixa. A tabela contém apenas UCs com queda individual ou sinal,
não todo o cadastro. Uma prioridade orienta uma visita, não atribui causa ou autoria.

## Atendimento, IA e risco

As rotas de [IA](../src/pipelines/grid_intelligence/transformations/13_silver_chamados.py)
e de [regras](../src/pipelines/grid_intelligence_regras/transformations/13_silver_chamados.sql)
anonimizam antes de enriquecer o texto, mas não garantem remover todo dado pessoal. Na rota
com IA, falha na anonimização restringe o texto; na rota por regras, a cobertura depende
dos padrões definidos. Sentimento, motivo e risco são classificações sujeitas a erro.

A [saúde do cliente](../src/pipelines/grid_intelligence/transformations/22_gold_saude_cliente.sql)
agrega chamados por cliente. O risco de ouvidoria é alto se há alguma menção em todo o
histórico ou se há pelo menos três chamados e um sentimento negativo nos 30 dias anteriores
à data de referência do dataset; é médio quando há sinal de risco à saúde e não se aplicou
a regra alta; caso contrário é baixo. O último conjunto e bairro vêm do chamado mais recente.
Esse critério é uma sinalização operacional, não uma previsão validada. A referência é a
maior data de abertura disponível, não necessariamente o dia de hoje.

O Genie usa essas fontes Gold para compor consultas e respostas; uma consulta correta não
garante uma síntese fiel. Há casos observados de omissão e generalização indevida em
[validação do Genie](validacao-agente-genie.md). Revise a consulta, o resultado e a
interpretação antes de agir.

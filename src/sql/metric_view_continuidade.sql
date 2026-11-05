-- O YAML não substitui parâmetros: o catálogo e schema são definidos antes da view.
-- Não use ponto e vírgula no corpo YAML: o executor de arquivos divide por esse caractere.
-- O total de UCs se repete por mês. DEC é média mensal e DEC Acumulado usa a base média.
USE CATALOG IDENTIFIER(:catalogo);
USE SCHEMA IDENTIFIER(:schema_gold);
CREATE OR REPLACE VIEW continuidade_metricas
WITH METRICS LANGUAGE YAML
AS $$
version: 1.1
source: continuidade_conjunto_mes
comment: Indicadores demonstrativos de continuidade com base no cadastro atual de unidades consumidoras.
dimensions:
  - name: Conjunto
    expr: nome_conjunto
    comment: Nome do conjunto de distribuição.
    synonyms: [região, area]
  - name: Codigo do Conjunto
    expr: id_conjunto
    comment: Identificador do conjunto de distribuição.
  - name: Municipio
    expr: municipio
    comment: Município do conjunto.
  - name: Mes
    expr: mes_apuracao
    comment: Primeiro dia do mês em que começou a interrupção.
    synonyms: [mês de apuração]
measures:
  - name: DEC
    expr: SUM(uc_horas_interrompidas) / NULLIF(SUM(total_ucs), 0)
    comment: Duração média mensal de interrupção por unidade consumidora em horas.
    synonyms: [horas sem luz]
    format: {type: number, decimal_places: {type: exact, places: 2}}
  - name: FEC
    expr: SUM(uc_interrupcoes) / NULLIF(SUM(total_ucs), 0)
    comment: Frequência média mensal de interrupções por unidade consumidora.
    format: {type: number, decimal_places: {type: exact, places: 2}}
  - name: DEC Acumulado
    expr: SUM(uc_horas_interrompidas) / NULLIF(SUM(total_ucs) / COUNT(DISTINCT mes_apuracao), 0)
    comment: Horas interrompidas por unidade consumidora acumuladas no período selecionado.
    format: {type: number, decimal_places: {type: exact, places: 2}}
  - name: Interrupcoes
    expr: SUM(qtd_interrupcoes)
    comment: Número de eventos de interrupção válidos.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Interrupcoes Climaticas
    expr: SUM(qtd_interrupcoes_climaticas)
    comment: Número de eventos de causa climática.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Proporcao Climatica
    expr: SUM(qtd_interrupcoes_climaticas) / NULLIF(SUM(qtd_interrupcoes), 0)
    comment: Proporção de eventos atribuídos a causas climáticas.
    format: {type: percentage, decimal_places: {type: exact, places: 1}}
  - name: Interrupcoes Programadas
    expr: SUM(qtd_interrupcoes_programadas)
    comment: Número de eventos programados.
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Horas UC Interrompidas
    expr: SUM(uc_horas_interrompidas)
    comment: Soma das durações multiplicadas pelas unidades atingidas.
    format: {type: number, decimal_places: {type: exact, places: 1}}
  - name: Maior Interrupcao
    expr: MAX(maior_duracao_horas)
    comment: Duração em horas do maior evento registrado no recorte.
    format: {type: number, decimal_places: {type: exact, places: 2}}
  - name: Total de UCs
    expr: SUM(total_ucs) / NULLIF(COUNT(DISTINCT mes_apuracao), 0)
    comment: Média mensal da base de unidades consumidoras no recorte.
    format: {type: number, decimal_places: {type: exact, places: 0}}
$$;

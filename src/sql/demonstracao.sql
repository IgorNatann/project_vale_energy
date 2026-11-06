-- Execute no SQL warehouse com o parâmetro :catalogo, por exemplo grid_dev.
-- Dados sintéticos. A consulta 5 mostra texto original: execute somente com acesso autorizado.

-- 1. RN-01: esperado 1.383 eventos bronze, 1.073 silver e 310 abaixo do limiar de 3 minutos.
SELECT (SELECT count(*) FROM IDENTIFIER(:catalogo || '.bronze.interrupcoes')) AS bronze,
       (SELECT count(*) FROM IDENTIFIER(:catalogo || '.silver.interrupcoes_validas')) AS silver,
       (SELECT count_if(duracao_minutos < 3) FROM IDENTIFIER(:catalogo || '.bronze.interrupcoes')) AS abaixo_3_min,
       100.0 * (1 - (SELECT count(*) FROM IDENTIFIER(:catalogo || '.silver.interrupcoes_validas')) /
         (SELECT count(*) FROM IDENTIFIER(:catalogo || '.bronze.interrupcoes'))) AS percentual_descartado;

-- 2. Qualidade: categorias exclusivas pela ordem nulo, negativo, limite e duplicata entre leituras válidas.
WITH base AS (
  SELECT c.*, u.id_uc AS uc_cadastrada, u.classe_consumo,
    CASE u.classe_consumo WHEN 'residencial' THEN 100 WHEN 'comercial' THEN 500
      WHEN 'industrial' THEN 10000 WHEN 'rural' THEN 250 WHEN 'poder_publico' THEN 2000 END AS limite
  FROM IDENTIFIER(:catalogo || '.bronze.consumo_diario') c
  LEFT JOIN IDENTIFIER(:catalogo || '.silver.unidades_consumidoras') u ON c.id_uc = u.id_uc
), classificados AS (
  SELECT *, CASE WHEN uc_cadastrada IS NULL THEN 'sem_cadastro'
    WHEN consumo_kwh IS NULL THEN 'nulo' WHEN consumo_kwh < 0 THEN 'negativo'
    WHEN limite IS NULL OR consumo_kwh > limite THEN 'acima_do_limite_ou_classe_desconhecida'
    ELSE 'valido' END AS categoria FROM base
), totais AS (
  SELECT categoria, count(*) AS linhas FROM classificados WHERE categoria <> 'valido' GROUP BY categoria
  UNION ALL SELECT 'duplicata_valida', count(*) - count(DISTINCT id_uc, data) FROM classificados WHERE categoria = 'valido'
  UNION ALL SELECT 'silver', count(*) FROM IDENTIFIER(:catalogo || '.silver.consumo_diario')
  UNION ALL SELECT 'bronze', count(*) FROM IDENTIFIER(:catalogo || '.bronze.consumo_diario')
)
SELECT categoria, linhas FROM totais ORDER BY categoria;

-- 3. RN-04: DEC governado e cálculo de auditoria devem coincidir por conjunto no último mês.
WITH ultimo AS (SELECT max(mes_apuracao) AS mes FROM IDENTIFIER(:catalogo || '.gold.continuidade_conjunto_mes')),
medidas AS (
  SELECT m.`Codigo do Conjunto` AS id_conjunto, MEASURE(m.`DEC`) AS dec_metric_view
  FROM IDENTIFIER(:catalogo || '.gold.continuidade_metricas') m
  WHERE m.`Mes` = (SELECT mes FROM ultimo) GROUP BY ALL
), manual AS (
  SELECT g.id_conjunto, sum(g.uc_horas_interrompidas) / nullif(sum(g.total_ucs), 0) AS dec_auditoria
  FROM IDENTIFIER(:catalogo || '.gold.continuidade_conjunto_mes') g CROSS JOIN ultimo u
  WHERE g.mes_apuracao = u.mes GROUP BY g.id_conjunto
)
SELECT m.id_conjunto, m.dec_metric_view, a.dec_auditoria, abs(m.dec_metric_view - a.dec_auditoria) AS diferenca
FROM medidas m JOIN manual a ON m.id_conjunto = a.id_conjunto ORDER BY m.id_conjunto;

-- 4. Dois eixos: esperado 20 UCs de prioridade alta no Jardim Aurora, com as duas variações.
SELECT id_uc, bairro, nome_conjunto, variacao_da_uc, variacao_do_conjunto, sinal_violacao_recente, motivo_observado
FROM IDENTIFIER(:catalogo || '.gold.prioridade_inspecao_uc') WHERE prioridade_inspecao = 'alta'
ORDER BY bairro, id_uc;

-- 5. Comparação pontual, NÃO prova anonimização completa. Não copie o texto original para o repositório.
SELECT b.id_chamado, b.transcricao AS original_restrito, s.transcricao_anonimizada, s.anonimizado_por
FROM IDENTIFIER(:catalogo || '.bronze.chamados') b
JOIN IDENTIFIER(:catalogo || '.silver.chamados_anonimizados') s ON b.id_chamado = s.id_chamado
WHERE b.nome_solicitante IS NOT NULL ORDER BY b.id_chamado LIMIT 1;

-- 6. Noite de 30/07/2026: esperado pico nas horas 22 e 23. Média inclui dias sem chamados.
WITH limites AS (
  SELECT min(data_chamado) AS inicio, max(data_chamado) AS fim FROM IDENTIFIER(:catalogo || '.silver.chamados_enriquecidos')
), por_hora AS (
  SELECT hora_chamado, count_if(data_chamado = DATE'2026-07-30') AS noite_cascata,
    count_if(data_chamado <> DATE'2026-07-30') AS chamados_outros_dias
  FROM IDENTIFIER(:catalogo || '.silver.chamados_enriquecidos') WHERE hora_chamado IN (21, 22, 23)
  GROUP BY hora_chamado
)
SELECT h.hora_chamado, h.noite_cascata,
  try_divide(h.chamados_outros_dias, datediff(l.fim, l.inicio)) AS media_mesma_hora_outros_dias
FROM por_hora h CROSS JOIN limites l ORDER BY h.hora_chamado;

-- 7. Consumo por ano: 2022 e 2026 são parciais. Compare o crescimento dos anos completos.
WITH anual AS (
  SELECT year(data) AS ano, count(DISTINCT data) AS dias_cobertos, sum(consumo_kwh) AS consumo_kwh
  FROM IDENTIFIER(:catalogo || '.silver.consumo_diario') GROUP BY year(data)
), comparados AS (
  SELECT *, lag(consumo_kwh) OVER (ORDER BY ano) AS consumo_anterior,
    lag(dias_cobertos) OVER (ORDER BY ano) AS dias_ano_anterior FROM anual
)
SELECT ano, dias_cobertos, consumo_kwh, try_divide(consumo_kwh, dias_cobertos) AS media_diaria_kwh,
  CASE WHEN dias_cobertos = datediff(make_date(ano + 1, 1, 1), make_date(ano, 1, 1))
    AND dias_ano_anterior = datediff(make_date(ano, 1, 1), make_date(ano - 1, 1, 1))
    THEN 100 * (try_divide(consumo_kwh, consumo_anterior) - 1) END AS variacao_anos_completos_percentual
FROM comparados ORDER BY ano;

-- 8. Chamados por mês: esperado volume maior em dezembro a março do que nos meses restantes.
SELECT month(data_chamado) AS mes, count(*) AS chamados
FROM IDENTIFIER(:catalogo || '.silver.chamados_enriquecidos') GROUP BY month(data_chamado) ORDER BY mes;

# Resultados da demonstração

Fotografia do ambiente `grid_dev`, consultado em 06/11/2026. Os dados são sintéticos e os
resultados de classificação por IA podem variar entre atualizações. As consultas estão em
[demonstracao.sql](../src/sql/demonstracao.sql); informe `catalogo = grid_dev` no SQL warehouse.

1. **Interrupções:** 1.383 na bronze e 1.073 na silver; 310 abaixo de três minutos ficaram
   fora da apuração, ou 22,42% da bronze.
2. **Consumo:** 5.854.587 linhas na bronze e 5.801.814 na silver. Foram identificadas
   23.478 leituras nulas, 8.799 negativas, 5.999 acima do limite demonstrativo ou sem
   classe conhecida e 14.497 duplicatas entre as leituras válidas. As categorias são
   exclusivas pela ordem da consulta.
3. **DEC:** os seis conjuntos tiveram diferença zero, dentro da precisão retornada, entre
   a metric view e a auditoria manual dos insumos para julho de 2026. A fórmula manual é
   apenas uma verificação; consumidores devem usar a metric view.
4. **Inspeção:** 20 UCs em prioridade alta no Jardim Aurora. Exemplo: UC0000899 com
   variação individual de −55,75% e variação do conjunto de +0,35%. É um sinal para visita,
   não uma confirmação de causa.
5. **Mascaramento:** um chamado autorizado foi encontrado e o texto publicado diferiu do
   original, usando a rota de IA. Nenhuma transcrição foi copiada para este documento. Essa
   comparação pontual não comprova anonimização completa. A consulta exige acesso à bronze.
6. **Noite de 30/07/2026:** às 21h foram 2 chamados, às 22h foram 6 e às 23h foram 6.
   As médias para as mesmas horas nos demais dias do período foram aproximadamente 0,042,
   0,032 e 0,013 chamado por dia, respectivamente; dias sem chamados entram no denominador.
   Houve interrupções climáticas registradas em Campinas Centro, Campinas Norte e Valinhos
   naquela noite. A associação temporal não prova causalidade.
7. **Consumo anual:** 2024 teve 90.691.765,71 kWh e crescimento de 30,61% frente a 2023;
   2025 teve 117.509.171,46 kWh e crescimento de 29,57% frente a 2024. Os anos de 2022
   e 2026 têm apenas 152 e 212 dias, respectivamente; não são comparados como anos completos.
8. **Sazonalidade:** dezembro a março somaram 335, 376, 317 e 338 chamados, respectivamente.
   A média desses meses foi 341,5, contra 179,38 nos demais meses — cerca de 1,90 vez.
   O período cobre quatro ocorrências de cada mês do calendário.

O [dashboard](https://dbc-52721ce8-5907.cloud.databricks.com/sql/dashboardsv3/01f1d9ebcfe714a8ba04bc003185ca3a)
e o [agente Genie](https://dbc-52721ce8-5907.cloud.databricks.com/genie/rooms/01f1d9ed61fd191687fefc6d13672063)
estão no workspace de desenvolvimento e dependem das permissões de acesso de cada usuário.
O [relatório de validação do Genie](validacao-agente-genie.md) registra respostas que ainda
exigem revisão humana.

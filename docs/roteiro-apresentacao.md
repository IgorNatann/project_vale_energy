# Roteiro de apresentação

Uma demonstração de aproximadamente três minutos pode seguir esta ordem. Os valores são
uma fotografia dos dados sintéticos e devem ser confirmados novamente no ambiente usado.

1. **Problema e arquitetura:** apresente continuidade, inspeção e atendimento no
   [README](../README.md), percorrendo o fluxo do volume até Bronze, Silver e Gold.
2. **Regra de negócio:** mostre em [regras](regras-de-negocio.md) por que eventos de menos
   de três minutos são excluídos da Silver e como a [metric view](metricas-e-ia.md)
   distingue DEC médio de acumulado.
3. **Dashboard:** no AI/BI, selecione um conjunto e um período; explique que a base de UCs
   é atual, a prioridade de inspeção não é prova de irregularidade e o sinal de saúde não é
   diagnóstico. Use [resultados da demonstração](resultados-demonstracao.md) como referência.
4. **Genie:** faça uma pergunta de continuidade e abra o SQL que sustenta a resposta.
   Mostre a [avaliação diagnóstica](avaliacao-genie.md) e as
   [limitações observadas na síntese](validacao-agente-genie.md).
5. **Engenharia responsável:** apresente as rotas de anonimização e regras, o
   [limite da validação de acesso](validacao-privacidade.md), a
   [CI](integracao-continua.md) e o acompanhamento de
   [execuções e consumo](observabilidade-custos.md).

Para uma apresentação pública, capture imagens ou grave uma demonstração do seu próprio
ambiente depois de conferir os dados e permissões. Não há imagens incluídas neste roteiro;
links internos do workspace podem não estar acessíveis a quem vê o portfólio.

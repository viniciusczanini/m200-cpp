# Revisão independente de contadores — 2026-11-05

Diff após0440b9f, contexto novo e modo read-only, contrato em
`../capabilities/COUNTERS.md`. Revisados modelo/gramática, frontend, guards,
normalização/alocação, SDK/reversão, configuração e gráficos simples de Counter.

Achado P2: `<Counters>UNRECOGNIZED_ACTIVE_COUNTER_CONFIGURATION</Counters>`
sem filhos era aceito por load_project e apagado por write_project. A remoção
de Counters da lista EMPTY deixou texto do container sem validação. O teste
`test_unknown_counter_container_text_is_rejected_and_destination_preserved`
reproduziu a falha; a correção recusa texto não-whitespace, incluindo texto
misto/tails locais, e conserva o arquivo de destino.17 testes focados passaram
depois. Um teste anterior também garante que Type desconhecido no template
não seja descartado silenciosamente; validação antecede a substituição.

O revisor executou os16 testes existentes naquele momento e6 composições
extras de50 scans, sem divergências entre VM, SDK, XML e C++ reconstruído.
Esses300 scans extras ficam fora dos totais reproduzíveis da rodada.

Não foram classificados como defeitos novos os seguintes limites explícitos:

- Gráficos raw de Counter B (fan-out em saídas) e M (prefixo compartilhado com
  MPS/MPP) ainda não são importáveis por check_counter_graph. Seus rungs IL
  completos são exercitados com normalização/exportação; isso não é apresentado
  como importação de gráficos originais. O gráfico independente de entradas de
  C é aceito e testado diretamente. B/M continuam trabalho da meta integral.
- Conflito documental sobre E e políticas de pinos/bordas/ciclo de vida não
  obtiveram prova externa nesta etapa.
- Formas incomuns de BLK, como ação explicitamente dirigida a outra instância
  ou OUT_BLK vazio, não foram chamadas de inválidas sem prova da gramática
  nativa. O exportador as normaliza; aceitação oficial permanece pendente.

Nenhuma outra divergência reproduzível foi relatada. Tudo local, sem CI,
publicação ou acesso/atuação em PLC. A revisão não conclui paridade integral.

# Revisões de bordas de expressão e fusão de cópias — 2026-11-05

Diff após `e7c40fd`, duas revisões independentes com contexto novo e sem editar
o repositório. Contratos: `../capabilities/EXPRESSION-EDGES.md` e
`../capabilities/COPY-FUSION.md`. A segunda revisão trata da otimização adicional
exigida pelo teste de capacidade no caminho inverso, acrescentada após a primeira.

## Funções de borda

O revisor encontrou duas falhas de exportação, reproduzidas antes da correção:

- P2: o caminho simples preservava `LDN [comparação]`, que o gráfico não
  representava. Agora esse caso usa snapshot e inversão pelo caminho geral.
- P3: a gramática aceitava whitespace que o normalizador depois rejeitava ao
  interpretar a linha inteira como opcode. Agora a normalização canonicaliza
  whitespace, inclusive no caminho que preserva rungs já simples, sem alterar
  o programa original.

Regressões em `test_expression_edges.py` e `test_native_logic.py` cobrem os
dois casos em RED/GREEN. O revisor também confrontou 500 programas aleatórios
de 20 scans e 300 programas com saltos para trás de 20 scans: 16.000 scans
extras, separados da rodada versionada. Nenhum outro achado de correção foi
relatado. A revisão não comprova políticas de partida, repetição ou fase físicas.

## Fusão de cópias

O teste que observa todos os resultados das 510 funções revelou estouro do
budget no C++ reconstruído/reexportado. O implementador manteve o teste e
introduziu fusão antes da alocação, com referências por owner/alias e prova CFG
de vida após o consumidor. O revisor não relatou achados importantes/críticos.

A revisão executou os oito testes focados existentes naquele momento e
comparou 1.500 programas aleatórios mistos de 8 scans contra a compilação com
fusão desativada: 12.000 scans extras, conferindo saídas, words explícitos e
S20. Também conferiu o limite experimental: 10.000 instruções aceitas e
10.002 recusadas após otimização. Esse limite não prova capacidade física.

Depois da revisão, o implementador acrescentou um nono teste no IR do Lowerer:
encaminhar uma comparação de duas colunas para nove contatos criava um rung
inválido. A falha foi reproduzida e a fusão passou a verificar a largura antes
de encaminhar. O revisor não havia relatado o caso como defeito, por não ter
identificado um caminho de origem C++ que o produzisse. O teste protege o
contrato entre Lowerer e exportador, independentemente dessa alcançabilidade.

Os **28.000 scans extras dos revisores não entram** nos totais de stress/públicos.
Os logs RED/GREEN e das rodadas locais ficam no diretório ignorado
`.superpowers/sdd/2026-11-05-expression-edges/logs/`; os resultados finais e
hashes reproduzíveis são registrados separadamente. Sem CI, publicação ou PLC.

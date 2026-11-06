# Contatos de borda nativos

Etapa após `292f5a2`, 2026-11-05. Meta integral em `../PARITY.md`; evidência,
diagramas e conflitos em `NATIVE-EDGES-RESEARCH.md`.

## Contrato desta etapa

LDR/LDF, ANDR/ANDF, ORR/ORF e XORR/XORF aceitam I0 e M diretos, dentro de
24/1024 bits. Não aceitam Q, S, propriedades, MW:X, constantes, comparações,
expansões ou indexação por analogia. A API retorna bool:
`input_rising(index)`, `input_falling(index)`, `m_rising(index)`, `m_falling(index)`;
índice literal, respeitando BitMemory se houver. Cada endereço explícito fica
reservado antes da alocação dos temporários.

O evento é amostrado no começo de cada ciclo, mesmo que o programa salte o
contato ou o leia várias vezes. Entrada usa a imagem atual contra a do ciclo
anterior. M usa seu estado no começo do ciclo contra o começo anterior: uma
escrita do programa só pode ser detectada no próximo ciclo. Um pulso interno
que suba e desça entre duas amostragens não produz borda. Ler uma borda não a
consome e repetir a instrução num laço não atualiza o histórico.

Política local de partida: histórico anterior false, como os bancos do modelo
existente. Uma entrada inicialmente alta produz subida; queda inicial não.
Fase exata de I, partida/retomada e eventos/tarefas continuam sem comprovação
externa. Esses limites não são uma garantia de equivalência física.

As classes RisingEdge/FallingEdge existentes continuam detectores no ponto da
chamada. RISINGn/FALLINGn têm um contrato separado em `EXPRESSION-EDGES.md`,
acrescentado depois desta etapa; não se alegam implementados por estes contatos.
XML raw dos blocos e modificadores R/F de parênteses continuam lacunas.

## Caminhos e Ladder

Um módulo de gramática fecha operandos/opcodes e a seleção da API. A VM amostra
todos os endereços usados antes do CFG, independentemente do caminho executado.
O SDK usa seu hook de início de scan para capturar bancos antes de `scan()`.
O frontend emite LDR/LDF e snapshot bool, sem estado de chamada que consuma o
evento. A reversão recupera as APIs dos opcodes/endereço reais.

Rungs série usam os tokens observados RisingEdge/FallingEdge; AND/OR/XOR
complexos são normalizados por snapshots de contatos e gates existentes.
Entradas compostas de Timer com borda são normalizadas, sem inventar layout.
Ordens, aliases, saltos, labels, endereços/buffers e vida de memória são
preservados pelos passes existentes. Falta de memória/instruções/labels extras
é limitação do compilador, não prova de impossibilidade no PLC.

Aceitação no editor, firmware/nível funcional, ciclo de vida e PLC físico
continuam pendentes. Não promover a biblioteca completa nem os registros
documentais a partir de consistência interna ou XML sintético.

## Evidência local

`tests/test_native_edges.py` cobre os oito operadores, todas as rejeições de
domínio, imagens/ordem, laços, saltos, Timer, grupos, limites, helper homônimo
e reversão/normalização/XML. O stress tem 74 casos/20.736 scans: todos os
24 endereços I0 e 1.024 M, com referência temporal separada, C++ original,
IL/JSON, normalização, C++ reconstruído, recompilação e XML sintético.

Três casos conferem hashes antes de extrair IL autêntica: rung2 inteiro do
flow-loop; somente o segmento LDR/ORF [1:3] do flow-jump, excluindo explicitamente
a atribuição IW; rung6 inteiro de T/INDEXED-SOURCES, com adaptadores M/Q/MD
explícitos. O gráfico paralelo original desse último não é apresentado como
validado. Nenhuma CPU foi reescrita ou projeto estrangeiro inteiro importado.

Rodada final: 306 testes, 144.724 scans de stress e 18.176 públicos, total
162.900 sem multiplicar etapas, reruns ou ensaios extras do revisor. Os dez
scripts do alvo stress foram executados localmente com quatro workers e logs
separados. Resultados, comandos e hashes em `../validation/NATIVE-EDGE-LOCAL-RESULTS.json`
e `../validation/NATIVE-EDGE-STRESS-RESULTS.json`; revisão em
`../validation/NATIVE-EDGE-REVIEW.md`. Objetivo integral continua ativo.

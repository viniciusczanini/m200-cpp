# Arrays com índice calculado: implementação local

Continuação de `../superpowers/plans/2026-11-05-indexed-memory.md`, em
2026-11-05. O alvo permanece TM200CE40T. Esta etapa usa os contratos e fontes
primárias registrados em `INDEXED-SEMANTICS.md`; não obteve aceitação externa.

## Comportamento implementado

- Arrays unidimensionais de capacidade fixa `bool`, `i16`, `i32`, `f32`, com
  índice literal ou expressão bool/i16/i32. A expressão é avaliada uma vez.
- Grupos contíguos somente para arrays com acesso calculado. Membros de32bits
  ocupam duas words; a transformação de índice lógico para offset físico é
  feita depois da verificação da faixa.
- Globais persistem entre scans e inicializam no primeiro RUN do contrato
  atual. Locais inicializam quando a declaração executa; inclusive em cada
  iteração. Inicializadores parciais completam com zero/false e podem ler
  elementos anteriores já inicializados.
- RHS precede o cálculo do lvalue. Leituras indexadas são capturadas no ponto
  da expressão. Ramos inativos e curto-circuito não acessam índices inválidos.
- Literais fora da faixa falham. Na política em validação para índice runtime
  inválido, um offset sentinel provoca S20/fallback ao elemento0; a flag é
  sticky até limpeza explícita. O C++ desktop tem comportamento indefinido
  para `[]` fora da faixa; não se executa o original nesse domínio nos testes.
- Uso/def por grupo: escrita parcial, inclusive STfalse, não mata a vida de
  outros membros. O grupo inteiro respeita aliases/reservas de memória e
  buffers Modbus. A busca do alocador não pode cruzar o fim do banco mesmo
  quando o span ocupa mais de metade da capacidade.

`plc::BitMemory{count}` reserva a imagem explícita de bits para a API raw
`read_m_indexed(base,index_word)`/`write_m_indexed(base,index_word,value)`.
Essa API requer também WordMemory para o MW do índice. O offset de bits é
o conteúdo signed de16bits desse word, sem modificá-lo. Guardas conservam a
faixa lógica da imagem mesmo com temporários em endereços mais altos.

## Etapas e bloqueios

| Caminho | Numéricos | Bits |
|---|---|---|
| C++ → IL/VM | implementado, testes locais | implementado, testes locais |
| IL → C++ nativo e recompilação | implementado, testes locais | implementado, testes locais |
| Projeto XML sintético e leitura de volta | exercitado, em validação | recusado explicitamente |
| Editor oficial / simulador oficial / PLC | pendente | pendente |

O manual documenta bits indexados a partir de nível funcional10.0. Ainda não
há evidência suficiente de como o token `FunctLevelManN_N` representa esse
nível no perfil CE40T. O exportador recusa antes de criar/substituir o destino;
o importador recusa igualmente. Não foi inventado enum gráfico nem promovido
um token por interpretação numérica de seu nome.

O limite local de instruções, o consumo de labels e a alocação conservadora
ainda podem recusar um programa nativo que caiba. A redução de cópias em
atribuições booleanas permitiu a reversão/recompilação do caso com900bits, mas
não é prova de emissão ótima. Também continuam as incertezas de indexação
nativa, fronteiras MD/MF, flags, ciclo de vida completo e perfis documentadas
em `INDEXED-SEMANTICS.md` e as demais famílias de `README.md`.

## Evidência local

Os testes em `tests/test_dynamic_arrays.py` e `tests/test_indexed_bits.py`
confrontam expectativas independentes, original C++ no domínio definido,
VM, C++ recuperado, recompilação e XML numérico. Incluem grupo i32 de4200words,
900bits, índices i32 extremos, curto-circuito, ordem de avaliação, aliases,
inicializadores e composição com buffers Modbus.

`tests/stress/dynamic_arrays.py` usa seed fixa e um oráculo separado de arrays
e estado. São11casos com1024scans cada: oito combinações de tipo/vida local
ou global e três imagens raw de bits. Testa XML numérico e exige recusa XML
de bits. Resultados e hashes estão em
`../validation/DYNAMIC-ARRAY-STRESS-RESULTS.json`; a rodada integrada está em
`../validation/DYNAMIC-ARRAY-LOCAL-RESULTS.json`.

A revisão independente contra a base6159c4c não encontrou falhas confirmadas;
suas reproduções incluíram `a[a[i]]=a[i]`, índice aninhado sob curto-circuito,
STfalse, inicializador lendo membro anterior e arrays com nome repetido.
Nenhuma dessas evidências conclui paridade integral nem compatibilidade oficial.

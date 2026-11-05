# Revisão independente: alocação privada de memória

## Veredictos finais da revisão local

- **Spec: GO para o escopo deste patch.** Banco completo, CFG cíclico, escritas condicionais, reservas físicas, globais/estado persistente exclusivos, símbolos de reuso e contagens CLI atendem ao plano revisado. O objetivo integral de `docs/PARITY.md` continua maior que este patch e permanece em aberto.
- **Qualidade: GO. Nenhum achado pendente após as correções.** Os dois P2 iniciais foram reproduzidos pelo implementador, corrigidos e rechecados independentemente nesta revisão.
- **Compatibilidade oficial: pendente.** Esta revisão não envolveu editor oficial, PLC, hardware, transmissão, CI ou pipeline remota e não declara compatibilidade oficial.

Escopo: patch atualizado `/tmp/m200-allocation-review-fixed.patch`, `AGENTS.md`, `docs/PARITY.md`, plano `docs/superpowers/plans/2026-11-05-memory-allocation.md`, passe de alocação, chamadas do frontend/lower, testes afetados e relatório CLI em `/Users/tommy/Offline/projects/m200-cpp`.

SHA256 do patch atualizado: `f95dec7b04c97a5eb2b55c9de594b5fa00f6a4cc599588d88140cbac95db763f`.

## Achados iniciais, ambos resolvidos

### P2 resolvido — Interferência interna ao rung

O passe original criava arestas apenas entre escritas e live-out do rung. A reprodução em `/tmp/m200-review-probes/intrarung_repro.py` inicializava `b=false`, depois executava `LD 1; ST a; AND b; ST %Q0.0`. Os dois privados compartilhavam `%M500`, e o resultado incorretamente passava de falso para verdadeiro. Nenhum C++ aceito foi encontrado que gerasse esse formato, mas o IR físico era validado e executado.

A correção armazena efeitos por instrução e retrocede a vida dentro do rung a partir do live-out do CFG, criando interferências no ponto de cada possível escrita e matando valores somente em definições obrigatórias. A reprodução original agora aloca `a` em `%M500`, `b` em `%M501` e retorna falso.

Verificação independente adicional: duas atribuições numéricas no mesmo rung, em que a primeira escrita não pode destruir um operando lido pela segunda, mantiveram o resultado esperado. A regressão `test_private_write_cannot_overwrite_a_later_read_in_the_same_rung` passou.

### P2 resolvido — Símbolos em aliases MW/MD/MF

A reprodução C++ `/tmp/m200-review-probes/symbols.cpp` gerava variáveis sequenciais i16/i32/f32 em `%MW4000`, `%MD4000` e `%MF4000`, mantendo três nomes locais sobre armazenamento reutilizado.

A correção calcula ownership por célula física e marca todos os registros que compartilham qualquer célula do mesmo banco. A reprodução original agora revela o reuso. Uma variante independente verificou sobreposição com bases diferentes: `%MW4001`, `%MW4002` e `%MD4001` receberam `compiler_reused_*`; `%MW4000`, persistente exclusivo, conservou o nome `persistent`. A regressão `test_symbols_disclose_reuse_across_overlapping_word_types` passou.

## Verificação das correções e áreas diretamente afetadas

Comando executado, sem repetir a suíte integral:

```text
PYTHONPATH=tests python3 -m unittest -v \
  test_allocation.AllocationTests.test_private_write_cannot_overwrite_a_later_read_in_the_same_rung \
  test_allocation.AllocationTests.test_symbols_disclose_reuse_across_overlapping_word_types \
  test_allocation.AllocationTests.test_allocator_refuses_instruction_effects_it_does_not_model
```

Resultado: **3 testes, 0.060s, OK**.

Também conferidos:

- Reprodução original de interferência: **expected False, actual False**.
- Variante de interferência entre operações numéricas dentro do mesmo rung: resultado esperado preservado.
- Reuso em aliases parcialmente sobrepostos com bases distintas: todos os aliases marcados; persistente exclusivo preservado.
- Reprodução original de símbolos: todos os símbolos numéricos reutilizados marcados.
- `report()` informa **1024 bits / 8000 words** em `compiler_allocatable_*`.
- Novos opcodes não modelados, como `LDR`, são recusados explicitamente pelo passe. Os opcodes emitidos atualmente pelo lower e blocos existentes continuam cobertos pelo modelo inspecionado.

O log anterior `/tmp/m200-memory-check.log` registrou **202 testes em 84.366s, OK**, antes destas correções. Esse resultado não é apresentado como execução integral dos bytes finais; nesta segunda rodada foram executados somente os testes focados acima e as variantes diretamente impactadas, conforme solicitado.

## Evidência independente anterior mantida

`/tmp/m200-review-probes.py` e `/tmp/m200-review-probes/results.json`: quatro ensaios concluídos antes da rodada de correções.

- `goto_backedge_guarded_words`: 16 scans, salto para trás, contador, escritas numéricas condicionais e estado global; VM = C++ nativo = recompilação do C++ reverso.
- `clock_edges_under_bit_pressure`: 16 scans, Clock/RisingEdge/FallingEdge sob 550 locais mortos; 1143 bits virtuais em 11 físicos; VM = C++ nativo = recompilação do reverso.
- `odd_typed32_explicit_alias`: 12 scans, MD3999/MW4000 e MF4003/MW4004; todas as quatro words reservadas excluídas da alocação privada; VM = C++ nativo = recompilação do reverso.
- `communication_full_reservation`: WriteReadVar com buffers de 121 + 125 words, além de quatro words explícitas; todas as 250 words reservadas excluídas da alocação privada; bloco executado em Machine com MemoryTransport local.

A primeira tentativa do probe de comunicação usou WriteQuantity=123 e foi recusada pelo limite existente de 121. O probe foi corrigido para uma configuração válida; isso não é defeito do patch.

## Inspeção sem achado adicional

CFG com saltos condicionais/incondicionais, retorno de scan e ponto fixo; manutenção do valor anterior em S/R e numéricos condicionais; reads de operações autodependentes e INC/DEC; intervalos de largura 1/2 em bases pares/ímpares; persistência de globais/arrays/Clock/bordas; reservas completas de inicializadores e buffers; reescrita dos virtuais antes do retorno; preservação de ordem/labels/origens; diagnóstico conservador distinguindo overhead da ferramenta de limite nativo.

A revisão inicial foi preservada em `/tmp/m200-allocation-review-initial.md`. Nenhum arquivo de produção ou estado Git foi alterado por esta revisão. Artefatos da revisão somente em `/tmp`.

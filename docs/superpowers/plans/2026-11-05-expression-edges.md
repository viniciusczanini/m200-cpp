# Expression Edges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e uma revisão independente por superpowers:requesting-code-review.

**Goal:** traduzir os blocos RISINGn/FALLINGn para C++ com identidade/histórico, condições e expansão equivalente para Ladder básico.

**Architecture:** módulo edge_functions.py fecha gramática/identidade. Estado é por ponto de execução, separado dos contatos amostrados por scan. API C++ tem dois bool functions com índice literal; lowerer envolve chamadas condicionais com CFG, e normalizer usa M persistente e gates.

**Tech Stack:** Python stdlib, Clang C++17, SDK/IL/SMBP existentes.

**Spec:** `docs/PARITY.md`, `docs/capabilities/EXPRESSION-EDGES.md`, `docs/capabilities/NATIVE-EDGES-RESEARCH.md`.

## Global Constraints

- Tudo local, sem CI, publicação ou PLC.
- Índices0..254 por tipo, um ponto estático por identidade, chamadas em laços permitidas.
- Estado atualiza em toda execução, mesmo entrada false; skip preserva histórico e &&/|| respeitam avaliação.
- Histórico local inicial false; sem garantias de fase/partida/retomada/repetição físicas.
- Raw XML dos blocos/nível funcional não inferido; expansão básica com overhead explícito não reduz a meta final.

## Review Focus

- FALLING precisa atualizar e produzir resultado quando acumulador false; não guardar operação sob acc true.
- Condição externa e curto-circuito não executam chamada/RHS inativo, inclusive comparações por alias NaN e indexação S20.
- Snapshot de entrada antes de atualizar estado: não usar resultado como novo histórico nem reutilizar M persistente.
- IDs RISING/FALLING separados, canônicos, esparsos/limite254 e duplicados; helpers homônimos não viram API.
- Laços/saltos, grupos, MPS/MPP e Timer preservam ponto de execução e estado entre scans; normalização não muda fonte.

## Task 1: estado e compilação

**Files:** criar m200/edge_functions.py/tests/test_expression_edges.py; modificar native_logic/IL/frontend/lower/allocation/reverse/SDK/ladder_lowering. Project segue normalização antes de emitir.

**Interfaces:** parser `parse(op)->None|(kind,index)`; API bool `plc::rising(int,bool)`/`falling(int,bool)`; Lowerer.expression_edge(op,signal,guard) cria snapshot/CFG. VM mantém histórico implícito; normalizer reserva M persistente por op.

- [x] Escrever testes de semântica literal, false/FALLING, repetição/skip, condições/curto-circuito, fronteiras/tipos/IDs, grupos/Timer e roundtrips; observar RED.
- [x] Implementar gramática, histórico, API, guardas e expansão; GREEN focado e suíte integral.
- [x] Revisão independente e regressões RED/GREEN dos achados importantes/críticos.

## Task 2: evidências e fechamento local

**Files:** stress/fixtures reais, exemplo/CLI/Makefile, docs/validation.

- [x] Exercitar originais T10/15/20 com hash, configuração/harness explícitos e sem CPU rewrite, diferenciando gráfico raw não emitido.
- [x] Stress por oracle de chamadas/estado separado, tipos/IDs e composição, C++/IL/JSON/reversão/recompilação/normalização/XML.
- [x] Suíte/exemplos/stress/públicos/lint/formato/diff, hashes/contagens sem inflação e commit local; objetivo integral ativo.

## Task 3: cópias e capacidade no caminho inverso

Achado de stress: o caso que observa resultados das510 funções atinge o budget
intermediário ao reexportar C++ reconstruído. Não reduzir a cobertura. Otimizar
somente escalares privados com uso único ou prova CFG de que o valor não vive
após o consumidor, mantendo aliases/ordem/labels.

**Files:** criar m200/copy_fusion.py/tests/test_copy_fusion.py; modificar allocation/lower; stress full_capacity é aceitação ponta a ponta.

**Interfaces:** pass de fusão recebe Program, registers/members/groups, regex de referências e live-out CFG antes da alocação. Une cópia bool terminal e atribuição numérica sob a mesma guarda pura; NOT com AND/ANDN somente com ambas as leituras puras. Conta aliases por owner; remove apenas registros eliminados sem usos, atualizando source-map. Encaminhamento de comparação deve preservar o limite gráfico de colunas.

- [x] RED de full_capacity e cadeia6000 que deve caber após fusão; testes de uso futuro, aliases e S20 antes de acesso indexado.
- [x] Implementar fusão conservadora e literais binários imediatos; budget de construção separado do budget emitido, que continua validado ao final.
- [x] GREEN ponta a ponta incluindo C++ do arquivo exportado recompilado; revisão independente desta mudança adicional e suíte integral.

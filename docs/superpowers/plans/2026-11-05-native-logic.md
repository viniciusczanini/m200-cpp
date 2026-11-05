# Lógica IL nativa e saída Ladder

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e superpowers:requesting-code-review para revisão independente.

**Goal:** preservar lógica nativa STN/N, stacks e parênteses e formas documentadas de timer, revertendo para C++ e gerando rungs Ladder equivalentes.

**Architecture:** `native_logic.py` decodifica gramática/estruturas, IL/VM e reversão executam os operadores; `ladder_lowering.py` traduz formas complexas para IR simples com Lowerer/Storage. Project exporta o IR normalizado com os gráficos existentes.

**Tech Stack:** Python stdlib, Clang/SDK e modelo/IR/SMBP existentes.

**Spec:** `docs/PARITY.md`, `docs/capabilities/NATIVE-LOGIC.md`.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- Gramática desconhecida, configuração ausente e efeitos sem prova falham explicitamente.
- Gates anteriores e capacidade/overhead conservadores continuam; modelo de stack32 não resolve conflito documental 11/32 do perfil físico.

## Review Focus

- STN não muda o acumulador; stack salva valor, nunca referência viva ao operando.
- Parênteses são avaliados e combinados sem reordenar leituras/escritas.
- IN não pode ter seu efeito incerto no acumulador usado por ações posteriores.
- Normalização preserva labels/identidades e reserva aliases/buffers/limite indexado; temporários não podem modificar memória original.
- Timer S/R não escreve quando Qfalse e sua entrada composta mantém a ordem.

## Task 1: execução e reversão nativas

**Files:** criar `m200/native_logic.py`, `tests/test_native_logic.py`; modificar IL/reverse.

**Interfaces:** `decode(rung)->list[(op,arg)]` sem label; `timer_body(rung)` expande BLK Timer em controle/leituras Q; operandos e configurações continuam validados pelo IL. Grupos AND(/OR( e MPS/MRD/MPP têm estados separados.

- [x] Escrever RED de STN/N, snapshots/aliases, stacks aninhados/limites e malformados, parênteses, labels/saltos, IN e Timer composto com S/R.
- [x] Implementar parser, VM e C++ com estados locais declarados antes dos labels; manter bloqueios de domínio e avaliar todos os operandos documentados.
- [x] Rodar equivalência C++ reverso/recompilado e suíte; corrigir regressões.

## Task 2: Ladder e programas reais

**Files:** criar `m200/ladder_lowering.py`, stress/casos públicos; modificar project/CLI/docs/Makefile e testes.

**Interfaces:** `normalize(program)->Program`, sem mutar original; preserva config/labels, usa endereços privados reservando os originais; serialização compara com o IR normalizado. Sem alteração de CPU/bytes de originais.

- [x] RED de exportação, fonte não modificada, memória/aliases, saltos/temporários e XML de volta; implementar rungs canônicos e metadados de normalização.
- [x] Conferir gráficos autênticos dos timers 35/36; ampliar validação de entrada composta/S/R e posições observadas, sem aceitar discrepâncias.
- [x] Exercitar originais isolados e oráculos independentes; atualizar expectativas de corpus somente após comprovar novo suporte.
- [x] Revisão independente, correções RED/GREEN, suíte/exemplos/stress/públicos/lint/formato/diff, hashes e fechamento com commit local. Objetivo integral continua ativo.

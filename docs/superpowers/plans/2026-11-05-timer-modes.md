# Modos de temporizadores nativos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e revisão independente com superpowers:requesting-code-review.

**Goal:** implementar configurações retentiva e preset dinâmico em todos os caminhos locais, com erros explícitos para combinações/perfis sem suporte comprovado.

**Architecture:** estender Timer com dois bools padrão false e o estado por ticks processados/valor retido/conclusão. SDK independente segue o contrato documental; frontend e reversão preservam opções por construtor explícito de5argumentos. XML preserva flags e recusa por nível funcional não mapeado, antes de mutação do destino.

**Tech Stack:** Python stdlib, Clang C++17, IR/VM/SDK/SMBP existentes.

**Spec:** `docs/PARITY.md`; `docs/capabilities/TIMER-MODES.md`.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- TON/TOF retentivos; TP retentivo recusado. DynamicPreset para TON/TOF/TP.
- FL3.3/12.0 exigidos; mapeamento de token XML sem prova permanece gate, nunca bool ignorado.

## Review Focus

- P menor que V conclui no próximo tick sem reduzir V para P.
- Escritas e leituras no mesmo timestamp não antecipam o próximo tick.
- Pausa retém V, mas reset depois da conclusão e nova ativação não carregam estado velho.
- Duas opções preservadas por JSON/reversão; default antigo false e tipos bool estritos.
- Gate XML protege destino existente e flags malformados não são silenciosamente false.

## Task 1: configuração e execução

**Files:** model/timers/IL/frontend/reverse/SDK; criar `tests/test_timer_modes.py`.

**Interfaces:** `Timer(...,retentive:bool=False,dynamic_preset:bool=False)`;
construtor `{index,base,preset,bool,bool}`; `TimerState.set_preset(value,now)`.
API pública de getters/setter permanece.

- [x] Escrever/observar RED de retenção TON/TOF, dinâmica nos3tipos, valores/ticks/fronteiras/pós-conclusão, duas opções e salto; JSON/tipos/TPret inválidos e reversão.
- [x] Implementar bools, gramática/construtores e estado por ticks com retenção inteira; manter antigos testes verdes.
- [x] Integrar preservação e gates de perfil no projeto sem tocar ManagementLevel; testar destino existente/malformed.
- [x] Revisão independente, corrigir achados RED/GREEN e registrar decisões. Sem achados de correção; fronteiras físicas continuam explícitas.

## Task 2: composição e verificação

**Files:** stress de modos, exemplo, Makefile/CLI/docs e relatórios.

**Interfaces:** reutilizar API/configuração de Task1; original pinado conserva CPU/bytes e escopo isolado.

- [x] Oráculo separado para modos/bases, interrupções, P e saltos; original retentivo isolado com hash conferido; comparar SDK/IL/JSON/reversão/recompilação e recusa XML. A rodada final inclui as5bases, além da configuração original isolada.
- [x] Rodar suíte, exemplos, stress/públicos/lint/formato/diff; registrar hashes e concluir com commit local. Objetivo integral continua ativo.

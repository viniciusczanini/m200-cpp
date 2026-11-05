# Propriedades de temporizadores nativos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e revisão independente com superpowers:requesting-code-review.

**Goal:** expressar e reverter leituras P/V/Q e escrita P dos timers TON/TOF/TP, preservando identidade nativa, base e aplicação do preset na próxima ativação.

**Architecture:** módulo focado `m200/timers.py` para referências fechadas e estado local. Numeric/IL reconhecem propriedades, sem tratá-las como RAM; frontend liga métodos a objetos nativos. Construtor explícito `(index,base_ms,preset)` preserva os três parâmetros na reversão. O SDK tem implementação independente para confronto.

**Tech Stack:** Python stdlib, Clang C++17, IL/VM/SMBP/SDK existentes.

**Spec:** `docs/PARITY.md`; contratos em `docs/capabilities/TIMER-PROPERTIES.md`.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- P é word0..9999; V é word de leitura; Q é BOOL de leitura. Base1ms somente TM0..5; índices0..254.
- Esta etapa preserva IsDynamicPreset=false e IsRetentive=false. True permanece lacuna explícita, sem mudar a meta integral.
- Saltos não congelam o estado interno; saída ligada ao bloco só é escrita quando o bloco executa. Relógio local discreto é experimental.

## Review Focus

- Timer esparso/base100ms não pode ser renumerado ou convertido para base1ms ao reverter.
- Escrever P enquanto ativo muda o valor lido, mas não a ativação corrente com DynamicPreset=false.
- V/Q continuam progredindo em scan que pula o bloco, sem reescrever sua saída.
- V/Q são somente leitura, nomes/índices não canônicos e instâncias inexistentes falham.
- P atribuído de fonte indexada preserva snapshot, S20/fallback e guarda; a região do timer não ocupa/reutiliza MW privado.

## Task 1: propriedades, estado e identidade

**Files:** criar `m200/timers.py`, `tests/test_timer_properties.py`; modificar model/numeric/IL/frontend/allocation/reverse/SDK. Project usa os campos de configuração atuais.

**Interfaces:** `Ton/Tof/Pulse{unsigned milliseconds}` permanece; novo `{int native_index,int base_ms,int preset}`. Métodos `preset()->i16`, `value()->i16`, `done()->bool`, `set_preset(i16)->void`. `%TMi.P/V/Q` são referências fechadas. `TimerState(config).read(field,now)`, `.set_preset(value)` e `.update(enabled,now)` modelam o caso não retentivo/não dinâmico.

- [x] Escrever testes RED: preset antes de ativar e durante execução, P/V/Q em TON/TOF/TP, TM42/base100, salto sobre bloco, read-only/índice/instância/valor inválidos, fonte indexada e ramo inativo.
- [x] Implementar gramática/validação, estado e SDK independentes; integrar leituras/escritas sem expor propriedade como RAM.
- [x] Integrar construtores/métodos, preservar ordem/guardas e identidade na reversão; reservar índices já usados e recusar colisões.
- [x] Rodar testes novos e suíte completa; corrigir regressões com RED/GREEN.
- [x] Obter revisão independente, corrigir achados e registrar decisões.

## Task 2: programas públicos, composição e entrega local

**Files:** novo stress reproduzível e caso público isolado derivado dos originais pinados; exemplo e atualização de CLI/docs/Makefile/relatórios.

**Interfaces:** reutilizar API/IL de Task1. Não modificar CPU/bytes de originais nem declarar importação integral de projeto que contém outros recursos ainda ausentes.

- [x] Exercitar fronteiras temporais e mudanças P com oráculo separado, SDK original/reverso, VM/recompilação/XML; incluir salto, i16 indexado, P antes/depois do bloco e todas as bases permitidas. Base10ms exige a recusa XML já existente.
- [x] Extrair atribuição `%TM1.P := %MW20[%MW10]` de original com hash verificado, confrontar com expectativa explícita e preservar configuração.
- [x] Executar exemplos e verificações locais pertinentes; vincular resultados aos hashes atuais e atualizar lacunas. Commit local ao fechar a etapa. Objetivo integral permanece ativo.

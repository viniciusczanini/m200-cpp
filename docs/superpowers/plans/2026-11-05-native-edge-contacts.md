# Contatos de borda nativos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e superpowers:requesting-code-review com contexto novo ao final.

**Goal:** expor e preservar os oito opcodes de contatos de borda por I0/M em C++/IL/VM/SDK/reversão/Ladder, ampliando a meta integral.

**Architecture:** gramática/API em edges.py; amostragem por endereço no começo do scan na VM e hook do SDK. Frontend emite snapshots de LDR/LDF; normalização converte combinações complexas sem consumir bordas. Gráfico usa enums observados.

**Tech Stack:** Python stdlib, Clang C++17 e SDK/IL/SMBP existentes.

**Spec:** `docs/PARITY.md`, `docs/capabilities/NATIVE-EDGE-CONTACTS.md`, `docs/capabilities/NATIVE-EDGES-RESEARCH.md`.

## Global Constraints

- Todos os testes/builds locais; não CI, publicação ou PLC.
- I0 24/M1024 diretos; endereços literais, BitMemory respeitado; demais domínios explicitamente recusados.
- Eventos amostrados uma vez por ciclo, preservados sob saltos/leitura repetida; M alterado no programa aparece no ciclo seguinte.
- Histórico local inicial false; fase/partida/retomada e compatibilidade oficial pendentes.
- RISINGn/FALLINGn e modificadores de parênteses permanecem lacunas distintas, sem reduzir a meta final.

## Review Focus

- Duas leituras e laços não consomem/recriam borda; pular um ciclo não acumula evento antigo.
- M escrito/limpo entre leituras não muda evento já amostrado; pulso entre fronteiras não aparece.
- API/M/BitMemory, reservas e normalização preservam identidade e limites1023/23; contatos não viram detectores de temporários reutilizados.
- Curto-circuito, stack, grupos e Timer preservam ordem; nenhum acesso numérico/ação inativo é antecipado.
- Primeiro scan alto, dt0 e estados retidos têm expectativas explícitas; XML não é prova externa.

## Task 1: contatos completos no caminho de compilação

**Files:** criar m200/edges.py e tests/test_native_edges.py; modificar native_logic/IL/frontend/native/reverse/SDK/allocation/ladder_lowering/project.

**Interfaces:** EDGE_OPS e LOADS/AND contatos fechados; parser do endereço; quatro APIs bool literais. `begin_scan()` do SDK é chamado pelo harness antes de scan. VM mantém histórico por endereço coletado no IR, não por ponto executado.

- [x] Escrever testes de todos os opcodes, I/M, leituras repetidas/laço/salto, scan seguinte e pulso suprimido, limites/readonly/domínios, combinações/Timer, reversão/normalização/XML; observar RED.
- [x] Implementar gramática, amostragem e tradução; GREEN focado e suíte integral.
- [x] Revisão independente com regressões RED/GREEN de achados importantes/críticos. Nenhum achado na revisão; colisão de helper reproduzida e corrigida antes dela.

## Task 2: fontes e validação integrada

**Files:** stress reproduzível e fixtures reais isoladas, exemplo/Makefile/CLI, docs/validation.

- [x] Conferir hashes dos originais, exercitar rungs/contatos e gráficos observados com adaptadores explícitos, sem reescrever CPU ou presumir defaults.
- [x] Testar cada I0/M nas fronteiras, composições aleatórias por oracle temporal separado, C++/IL/JSON/reversão/recompilação/normalização/XML.
- [x] Rodar exemplos, suíte, stress, públicos, lint/formato/diff; registrar contagens sem multiplicar etapas/reruns e hashes; commit local. Objetivo integral continua ativo.

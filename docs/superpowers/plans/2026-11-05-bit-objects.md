# Bits de words e sequências de bits

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD e revisão independente por superpowers:requesting-code-review.

**Goal:** expor seletores MW:X e transferências packed M/I0/Q0 em C++/IL/VM/reversão/SMBP, preservando aliases, faixa e snapshots.

**Architecture:** módulo `bits.py` fecha gramática/faixas/extensões. Numeric reconhece atribuição de sequências separadamente dos operadores aritméticos. Frontend/SDK fornecem API tipada com portadores i16/i32; referências usam os bancos existentes. Recursos/normalização reservam regiões completas.

**Tech Stack:** Python stdlib, Clang C++17, SDK/VM/IL/SMBP atuais.

**Spec:** `docs/PARITY.md`; `docs/capabilities/BIT-OBJECTS.md`.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- Faixas M1024/I0 24/Q0 16/MW8000; X0..15, início de sequência múltiplo8 e comprimento1..32 limitado ao portador.
- Outros bancos/perfis e semântica nativa de overlap/tamanhos desiguais continuam lacunas explícitas, sem alterar meta integral.

## Review Focus

- Bit15 e word7999 devem preservar representação e fronteira de MD/MF.
- Sequência menor que portador zero-extends; escrita preserva vizinhos e cópia API captura sobreposição.
- Campo/substring não é identidade de alocação: reservar word/células inteiros, incluindo só-escrita e buffers.
- I0 é readonly; bools e números não sofrem coerções de API não previstas.
- RHS é capturado antes de escrita e branches inativos não executam acessos indexados/ações.

## Task 1: modelo, gramática e runtime

**Files:** criar bits.py/tests/test_bit_objects.py; modificar model/numeric/IL/reverse/SDK/frontend/allocation e extents/report/project/normalization.

**Interfaces:** APIs do contrato; bool read/write de MW:X; Numeric.operation retorna copy com Number tipado de sequência, sem permitir aritmética sobre sequência. `memory_bits_used(program)` retorna todas as células M explícitas.

- [x] RED para seletores/bancos compartilhados, pack/unpack i16/i32, I/Q, snapshot/overlap, fronteiras/tipos/readonly, branches/aliases e reversão/XML.
- [x] Implementar gramática/transferências/SDK/VM independentes e API/reservas; manter domínios estritos.
- [x] Integrar extents de regiões completas e normalização, sem falso overflow ou memória privada no destino.
- [x] Rodar suíte e revisão independente; reproduzir e corrigir achados. Detalhes em `docs/validation/BIT-OBJECT-REVIEW.md`; rodada final integrada pendente abaixo.

## Task 2: fontes e entrega

**Files:** stress reproduzível/originais, exemplo, CLI/Makefile/docs/relatórios.

- [x] Exercitar todos os bits, tamanhos, limites e combinações com oráculos de bitmask separados, C++/IL/JSON/reversão/normalização/XML; originais isolados com hashes. Incluída matriz completa de portas digitais a pedido do usuário.
- [x] Verificar exemplos/suíte/stress/públicos/lint/formato/diff, registrar bytes/resultados e commit local. Objetivo integral continua ativo.

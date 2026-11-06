# Numeric Conversions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans inline, TDD e revisão independente por superpowers:requesting-code-review.

**Goal:** suportar BTI/ITB word/dword, CONCATW e DWORD na biblioteca, IL, SDK, VM e caminho inverso/exportação, com evidência e políticas explícitas.

**Architecture:** numeric OPS mantém assinaturas/tokens; conversions.py avalia empacotamento e valida dígitos/faixa; SDK usa unsigned e cópia de bits. ArithmeticState recebe erros apenas no domínio inválido BCD e preserva flags no sucesso.

**Tech Stack:** Python stdlib, Clang C++17, SDK e serialização SMBP existentes.

**Spec:** docs/capabilities/CONVERSIONS.md, docs/PARITY.md.

## Global Constraints

- Meta completa intacta, local/sem CI/push/PLC; formato e execução física não certificados.
- APIs bcd_to_int/bcd_to_dint/int_to_bcd/dint_to_bcd/concat_words/int_to_dint.
- BCD válido conserva todos os bits e flags; inválido S18+erro local sem fabricar resultado.
- CONCATW low-first; DWORD sign-extend é política local explícita, não prova física.

## Review Focus

- Nibble alto8/9 gera portador negativo válido e não S18; BTI não interpreta sinal decimal.
- Capturar ambos os argumentos antes de destino sobreposto; snapshot sobre MD/MW e indexação.
- S18 anterior permanece no sucesso; S17 não muda; ramo inativo não executa erro.
- Tipos misturados/array fora dos limites/operandos desconhecidos recusados, com lacuna distinta de impossibilidade PLC.
- C++ reconstruído do projeto real preserva instrução/largura/ordem, não apenas fonte anterior.

## Task1: avaliador, IL e SDK

**Files:** criar m200/conversions.py e tests/test_conversions.py; modificar numeric.py/arithmetic.py/sdk/plc.hpp.
**Interfaces:** evaluate_conversion(name,values) retorna int ou CompileError; NUMERIC_CONVERSIONS define assinaturas; VM usa contexto aritmético existente.

- [x] RED de exemplos 0x2450↔2450, 0x9999↔9999, 0x99999999↔99999999; CONCATW low/high; widening i16 e flags; inválidos.
- [x] Implementar seis intrínsecos, parser de CONCATW com literais, SDK sem UB e preservação de efeitos; GREEN de caminhos completos e exaustão word.

## Task2: biblioteca e validação extensiva

**Files:** novo tests/stress/conversions.py, examples/conversions.cpp, Makefile; atualizar CLI/README/capabilities, revisão/resultados.
**Interfaces:** stress usa expression_edges.verify para os caminhos completos e oracle decimal/bytes independente; reporta frames-base uma vez e operações exaustivas separadas.

- [x] Testar limites32, aliases, guardas/loops e exemplos rotulados; fonte publicada sem alegar SMBP original ausente.
- [x] Atualizar documentação/exemplo e consultar capabilities sem promover inventário documental.
- [x] Revisão independente; suite/examples/públicos/todos os stress locais, hashes/contagens e commit; objetivo integral segue incompleto.

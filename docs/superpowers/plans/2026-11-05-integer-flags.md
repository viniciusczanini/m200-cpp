# Integer Arithmetic Flags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans inline, TDD e revisão independente por superpowers:requesting-code-review.

**Goal:** permitir overflow inteiro recuperável por S18 e último bit de shift por S17 em C++, IL, SDK, projeto e caminho inverso, com política local e lacunas explícitas.

**Architecture:** arithmetic.py guarda flags e resultados modulares; evaluate recebe contexto opcional (sem ele conserva validação estrita de domínio/literais). VM e SDK têm estado por execução, resets explícitos, sem apagar em sucesso/novo scan. Frontend emite chamadas mesmo literais para preservar efeitos; normalização/alocação mantêm ordem e guardas.

**Tech Stack:** Python stdlib/ClangC++17/SDK/SMBP existentes.

**Spec:** docs/PARITY.md e docs/capabilities/INTEGER-FLAGS.md; fontes primárias G54–57 e P322–323.

## Global Constraints

- Local, sem CI/push/PLC; objetivo integral e perfil/editor/hardware pendentes.
- S18 sticky até R; S17 recebe último bit0/1 a cada shift1..width; sem alteração por operações que não os escrevam.
- Overflow modular é política local além do exemplo G55, não prova física. Nenhum resultado indeterminado fabricado.
- Tipos/endereços/imediatos inválidos continuam recusados; distinguir lacuna do modelo de impossibilidade física.

## Review Focus

- Snapshot S18/S17 antes/depois de operações, clears, argumentos e condições; cópia não pode antecipar getter sobre erro ou perda de carry.
- Overflow MIN/MAX/ABS e DIV/REM mínimo/-1, sentido e distância1/width de shifts.
- Flags entre scans e laços, operações válidas após erro e chamadas inativas não limpam/produzem eventos.
- Clear condicional afeta somente o flag solicitado; ST/STN/S inválidos e XML/reversão preservam R.
- Não alterar domínio Float/NaN sem SW17/resultados definidos; não transformar erro local indeterminado em sucesso fictício.

## Task1: modelo/IL e contratos

**Files:** criar m200/arithmetic.py, tests/test_integer_flags.py; modificar numeric.py/model.py/il.py.

**Interfaces:** ArithmeticState com carry/overflow, integer_result(value,kind), shifted(value,width,distance,left), clear(index); evaluate(name,values,kind,flags=None). Flags conhecidos por model.address e R exclusivo. Machine.arithmetic contém estado.

- [x] RED do exemplo oficial de saturação, overflow/clear/sticky, shifts/rotações e flags preservados em cópia/scan/condições.
- [x] Implementar estado e avaliação sem fabricar erros indeterminados; GREEN focado.

## Task2: C++/SDK/exportação

**Files:** modificar lower/frontend/reverse/counter_graph/sdk/plc.hpp/cli; atualizar testes negativos de contrato anterior, exemplo/Makefile/docs.

- [x] RED de chamadas C++ e literais overflow, snapshots de flags, clear guardado e caminhos inversos/XML.
- [x] Implementar API e SDK sem UB inteiro, manter literal inválido recusado e operações em execução.

## Task3: stress/revisão/evidência

**Files:** stress/integer_flags.py, docs/validation.

- [x] Oracle independente por matemática modular/bit ejetado, loops/guardas e trechos primários reais com hashes; IL/C++/JSON/reversão/exportação efetiva.
- [x] Revisão independente e regressões de achados (sem achados nesta etapa).
- [x] Suite/examples/públicos/todos os stress locais e hashes/contagens; commit mantendo meta integral incompleta.

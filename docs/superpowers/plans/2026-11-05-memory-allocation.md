# Alocação e reuso da memória do compilador

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, TDD e revisão independente.

**Goal:** remover os limites artificiais de metade dos bits/words e reutilizar armazenamento privado quando os valores não coexistem.

**Architecture:** Lowerer emite endereços virtuais privados, que não chegam ao projeto final. Um passe analisa usos/definições e o CFG de rungs, incluindo saltos para trás e a volta entre scans, e colore interferências por banco físico. Endereços explícitos e buffers inteiros de comunicação ficam reservados; globais C++ e estado de instâncias recebem posições únicas durante toda a execução. Locais/temporários podem compartilhar somente quando a análise comprova ausência de sobreposição de vida. Escritas condicionais conservam o valor anterior na análise.

**Tech Stack:** Python stdlib, IR/IL atual, Clang C++17, unittest.

**Spec:** `docs/PARITY.md`.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Alvo TM200CE40T: 1024 bits M e 8000 words compartilhados MW/MD/MF.
- Endereços explícitos e buffers Modbus não podem ser sobrepostos por temporários, mesmo se um acesso explícito parece morto.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- O passe preserva rungs, ordem, labels, origem e semântica; não muda a política de overflow/erro numérico ou do watchdog local.
- Recusa por overhead/alocação conservadora da ferramenta não é prova de impossibilidade no PLC; a otimização final continua parte do objetivo.

## Review Focus

- Um valor vivo através de um salto para trás ou entre scans não pode ser sobrescrito por reuso de armazenamento.
- S/R e operação numérica condicionada devem conservar valor anterior quando a condição é falsa.
- MF/MD ocupam duas words, incluindo endereços ímpares e aliases com MW.
- Reservas de endereços em inicializadores parciais e buffers completos de comunicação devem ser preservadas.
- Estado de globais/Clock/bordas não é um temporário descartável; símbolos devem identificar reuso sem fingir duas variáveis persistentes no mesmo endereço.

## Task 1: endereços virtuais, análise e alocação física

**Files:** criar `m200/allocation.py`, `tests/test_allocation.py`; modificar `m200/lower.py`, `m200/frontend.py` e documentação de limites.

**Interfaces:** `Storage.bit(symbol, persistent=False) -> str`, `Storage.word(kind, symbol, persistent=False) -> Number`, `Storage.finalize(program, constants) -> Program`. Lowerer conserva reservas físicas; Frontend marca globals/estado persistente e finaliza depois de compor prefixo/corpo/commit. Nenhum endereço virtual pode escapar para o programa retornado.

- [x] Escrever e observar RED para 600 bits globais/4200 words globais que cabem no alvo, longa sequência de temporários, reservas/aliases, laços e valores condicionais mantidos entre scans.
- [x] Implementar registros virtuais e análise de usos, definições obrigatórias/condicionais e sucessores. Iterar vida até ponto fixo com arestas de retorno e de ciclo de scan.
- [x] Construir interferências e escolher posições físicas determinísticas, com intervalos de largura1/2, preservando globais e reservas. Preferir posições antigas quando couber, mas permitir todo o banco.
- [x] Reescrever somente tokens completos, atualizar símbolos/contagem e testar diagnóstico explícito quando a alocação conservadora não couber.
- [x] Confrontar VM, C++ nativo, reversão/recompilação e XML onde aplicável, executar suíte completa, exemplos, ensaios públicos e stress; revisar e corrigir com regressões.
- [x] Registrar resultados e commit. O objetivo integral permanece ativo; indexação dinâmica, flags/blocos/periféricos e aceitação externa continuam pendentes.

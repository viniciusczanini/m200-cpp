# Counter Graph Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans inline, TDD e revisão independente por superpowers:requesting-code-review.

**Goal:** importar gráficos nativos de Counter com prefixos/saídas ramificados verificando conectividade, condições e efeitos ordenados contra o IL real; explicitar extent de alocação na exportação.

**Architecture:** boolean_bdd.py fornece álgebra exata iterativa; counter_graph.py constrói portas/uniões, transfere condições, ordena sinks e reconcilia duas execuções simbólicas. counter_xml.py preserva parsing fechado e delega a verificação; escritor mantém layout básico e emite ForcedCount sem enum.

**Tech Stack:** Python stdlib e pipeline C++/IL/SMBP existente.

**Spec:** docs/PARITY.md, docs/capabilities/COUNTER-GRAPHS.md, COUNTERS.md, COUNTER-SOURCES.json.

## Global Constraints

- Local, sem CI/push/PLC, mesma branch dedicada; objetivo integral ativo.
- Não importar CPU estrangeira nem transformar fixture em projeto nativo falso.
- Somente formatos/pinos/opcodes conhecidos; desconhecidos e efeitos cuja ordem não for provada falham explicitamente.
- Prova booleana exata com ordem de memória, sem inferir semântica física de %C ou nível funcional.
- Qualquer budget da prova é da ferramenta, não limite físico; não diminuir a meta final.

## Review Focus

- MPS/MPP compartilha valor antigo, enquanto releitura após R/CU ou bobina pode mudar.
- ST/S/R e aliases de bits entre bobinas, prefixos compartilhados e condições idênticas escritas em forma diferente.
- Fios quebrados, deslocamentos de pinos/Counter, sobreposição/duplicatas e elementos desconhecidos não podem ser ignorados.
- Equivalência não deve esconder efeitos de comparação/indexação; esses casos raw permanecem gated explicitamente.
- XML reordenado, posições válidas diferentes, fanout e número de variáveis não devem depender de uma amostra/ordem textual.

## Task1: álgebra e reconciliação

**Files:** criar m200/boolean_bdd.py, m200/counter_graph.py, tests/test_counter_graphs.py, tests/fixtures/native_counter_branch_graphs.json; alterar counters.py/counter_xml.py se necessário.

**Interfaces:** BDD.atom(key)/combine(op,a,b)/negate(a), IDs0/1 terminais, operações&|^; verify(elements,lines) recebe tuplas(typ,descriptor,row,column,connection) já fechadas pelo parser. Elementos e actions são reconciliados sem editar fonte.

- [x] RED dos originais B2/C0/M12, BDD truth tables e regras de snapshots/bit writes/pinos/conexões.
- [x] Implementar álgebra iterativa/limites e grafo com provas exatas; GREEN dos originais e casos negativos sem abrandar asserts.

## Task2: extensão e validação

**Files:** alterar counter_xml.py/CLI/docs/Makefile; criar stress/counter_graphs.py e docs/validation.

- [x] RED para ForcedCount0/1/255, IDs esparsos e ausência de enum inventado; implementar alocação explícita.
- [x] Importar rungs/configuração preservados em envelope sintético declarado, C++ real/VM/SDK/recompilação/exportação, corpus hash-checked e mutações de gráficos.
- [x] Revisão independente, regressões de achados, suite/exemplos/públicos e todos os stress locais, hashes/contagens e commit; objetivo integral incompleto.

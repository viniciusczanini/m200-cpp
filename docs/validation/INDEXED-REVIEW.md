# Revisão independente — etapa 1, memória indexada

Escopo: `/tmp/m200-indexed-review.patch` e arquivos atuais de `/Users/tommy/Offline/projects/m200-cpp`, lidos em 2026-11-05. Foram consultados `AGENTS.md`, `docs/PARITY.md`, o plano `docs/superpowers/plans/2026-11-05-indexed-memory.md` (etapa 1), `INDEXED-SEMANTICS.md` e `INDEXED-ORIGINALS.md`. Nenhuma alteração no projeto, Git, configuração remota ou PLC. Os únicos artefatos criados pelo revisor estão em `/tmp`.

## Veredito atual

**GO para o escopo local da etapa 1 revisado, sem achados abertos nesta revisão.** Os dois achados foram reproduzidos antes das correções, corrigidos pelo implementador e conferidos no código atual e nas regressões específicas. Não se afirma aceitação Schneider ou comportamento de hardware.

## 1. [P2] Saída de timer contornava a restrição de escrita em S20 — CORRIGIDO

Local original: `m200/il.py:151` e a flexibilização de `m200/model.py:102`; a validação especial de S/ST S20 só acontecia no caminho de rungs comuns. Um bloco de timer com `ST %S20` passava pela chamada genérica de `address(..., True)`. Em `m200/reverse.py:46`, qualquer escrita em S20 era traduzida para limpeza, mesmo que o valor fosse verdadeiro.

Repro executado antes da correção:

```python
p = Program([
    ['LD 1', '[%MW15:=0]', '[%MW0:=-32768]', '[%MW1:=%MW8[%MW0]]'],
    ['BLK %TM0', 'LD 1', 'IN', 'OUT_BLK', 'LD Q', 'ST %S20', 'END_BLK'],
    ['LD %S20', 'ST %Q0.0'],
], {0: Timer('TON', 0, 100)})
```

`validate(p)` aceitava. `Machine(p).step()` falhava com `system index-error bit can only be cleared`; `run_native(to_cpp(p))` e o C++ reverso recompilado limpavam a flag e retornavam a saída falsa. Artefato `/tmp/m200-review-timer-s20.cpp` conserva o C++ reverso gerado durante o repro anterior à correção.

Estado conferido após a correção: endereços de sistema voltaram a ser read-only na API genérica; só R S20 é liberado explicitamente pelo validador; `write_cpp` rejeita valor diferente de false. Executado **somente** `python3 -m unittest tests.test_indexed.IndexedTests.test_timer_output_cannot_write_index_error_flag -v`: **1 teste OK, 0.001 s**. Não houve repetição da suíte completa.

## 2. [P2] Alocação sem modo explícito permitia aceitar ForcedCount excessivo — CORRIGIDO

Local anterior: `m200/project.py:447-454`, em particular a condição `words.findtext("Allocation") == "Manual"`. Correção atual em `m200/project.py:449-451`.

A recusa de limites de indexação não comprovados vale apenas se o token Allocation for exatamente Manual. O XML aceito pelo projeto também permite omitir esse token ou deixá-lo vazio. O documento `INDEXED-ORIGINALS.md`, seção “Automatic não demonstrado por enum explícito”, registra que não foi comprovado qual é o modo default da serialização omitida. Assim, um arquivo cujo ForcedCount excede a maior referência direta passa a ser aceito somente ao remover o token Manual; o limite incerto deixa de ser identificado.

Repro executado:

```python
p = Program([
    ['LD 1', '[%MW15:=0]'],
    ['LD 1', '[%MW1:=%MW8[%MW0]]'],
])
write_project(p, Path('tests/fixtures/synthetic.smbp'), target)
# No XML gerado, alterar ForcedCount de 16 para 32.
# Com <Allocation>Manual</Allocation>: load_project recusa.
# Remover apenas <Allocation>: load_project aceita, direct_word_limit == 16.
```

Saída observada: `Manual=32 REJECTED: ... indexed bound ... unverified`; depois `Allocation omitted/ForcedCount32 ACCEPTED, bound= 16`.

Artefato exato anteriormente aceito: `/tmp/m200-review-omitted-allocation.smbp`. Após a correção, esse mesmo arquivo foi reaberto pelo revisor e recusado com `indexed bound with an omitted/default allocation mode is unverified`.

Correção conferida: programas indexados agora exigem modo explicitamente Automatic ou Manual. A omissão, o token vazio e a ausência do nó de alocação falham explicitamente. Manual continua exigindo contagem suficiente e alinhada ao limite de referência direta; símbolos/buffers além desse limite continuam recusados. O teste parametrizado cobre Manual com excesso, modo omitido e modo vazio. O modo explicitamente Automatic conserva a interpretação documental. Este achado demonstrava falha da política fail-closed; não demonstra qual dos limites o hardware usaria.

## Verificações e limites

- Inspeção de gramática fechada, resolução assinada de MW, largura MD/MF, fallback, sticky/clear, cópias sob guarda por CFG real, captura booleana antes de RHS, reservas e tratamento de buffers, serialização e reversão.
- O log fornecido `/tmp/m200-indexed-full-check.log` terminou com **216 testes OK em 99.428 s**. Resultado lido do log, não reexecutado pelo revisor. Testes adicionais que o implementador realizou depois não estão incluídos nessa contagem.
- Depois das correções, o revisor executou somente `test_timer_output_cannot_write_index_error_flag` e `test_unverified_excess_manual_allocation_is_refused_on_import`: **2 testes OK em 1.835 s**, incluindo os três subcasos de alocação. O repro XML exato anterior também foi confirmado como recusado. Não houve nova execução da suíte completa.
- O teste adicional `test_full_word_bank_works_for_direct_indexed_transfers` foi lido: usa WordMemory 8000, MD7998, transferência indexada e os caminhos de reversão/XML da função equivalent. O log fornecido `/tmp/m200-indexed-boundaries.log` registra **12 testes OK em 10.508 s**, incluindo esse caso; resultado do implementador, não reexecutado pelo revisor.
- Fora os dois achados corrigidos acima, não foi confirmado outro defeito de alias, ordem ou limites na etapa 1 durante esta revisão.
- A relação entre maior referência direta, word alto de MD/MF, Manual/ForcedCount e limites reais do PLC continua sendo a lacuna externa já documentada; SDK/VM/round trip não eliminam essa lacuna.

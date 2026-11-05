# Revisão independente: arrays fixos e fluxo de controle

Data: 2026-11-05. Revisor: subagente `goal_language_review`.
Repositório examinado: `/Users/tommy/Offline/projects/m200-cpp`.
Patch de entrada: `/tmp/m200-goal-language-review.patch` (arrays e fluxo).

## Veredito

**Patch original: NO-GO local**, por divergências semânticas em `goto` dentro de condicionais e arrays `extern`, além de validação permissiva de label antes de `JMP`.

**Estado corrigido inspecionado: GO de revisão para o recorte local das tarefas 1/2, sem achados bloqueantes restantes nos caminhos examinados.** As três causas abaixo foram corrigidas pelo agente principal e rechecadas nesta revisão. A rodada completa final do implementador concluiu **195/195 testes locais verdes**, conforme inspeção de `/tmp/m200-goal-final-check.log` nesta revisão complementar. A primeira suíte integrada (190 testes) havia falhado apenas no teste legado que ainda esperava rejeição de `while`; a expectativa foi corrigida antes da rodada final.

**Contrato completo de `docs/PARITY.md`: permanece incompleto/experimental.** Nem esta revisão, os oráculos C++, nem round trips próprios comprovam aceitação no editor, Ladder oficial ou comportamento do TM200CE40T. Permanecem alocação/reuso, indexação dinâmica, recursos seguintes do plano e ensaios externos. A rejeição explícita de uma construção ainda não implementada é adequada para este marco; não reduz a meta de equivalência.

## Fontes e método

Lidos: `AGENTS.md`, `docs/PARITY.md`, tarefas 1/2 e foco de revisão do plano `docs/superpowers/plans/2026-11-05-parity-language-blocks.md`, patch completo e `/tmp/m200-control-flow-research-goal.md`. Inspecionados frontend, lowerer, fluxo, VM/validação IL, reversão, exportador/importador XML, SDK nativo e testes novos/existentes pertinentes.

Usei os resultados integrais fornecidos (baseline 173; arrays 179/179; primeira integração de fluxo 190 com um teste legado incompatível), sem repetir a suíte inteira. Executei novos casos direcionados quando havia risco concreto. A pasta `/tmp/m200-language-review-repros/` guarda os fontes C++ e, nos onze casos de composição aprovados, C++ reverso e SMBP sintético examinados.

Não editei código do projeto ou Git, não deleguei trabalho, não usei CI nem hardware. As correções descritas foram feitas pelo agente principal durante a revisão.

## Achados corrigidos, por severidade

### P1 — `goto` que entra em `if` executava com guarda não calculada

Local original: `m200/frontend.py`, lowering de `IfStmt`/`LabelStmt`.

Repro mínimo:

```cpp
void scan(){
  plc::i16 n=0;
  goto inside;
  if(plc::input(0)){inside:n=plc::add_i16(n,1);}
  plc::output(0,n==1);
}
```

Esperado: saída 0 verdadeira, independentemente da entrada. O salto entra diretamente no corpo; não avalia a condição do `if`. O lowering original reutilizava uma guarda emitida antes do label, pulada pelo salto, e a VM retornava falso. O RED do implementador está em `/tmp/m200-flow-composition-red.log`; o GREEN está em `/tmp/m200-flow-composition-green.log`.

Correção examinada: `IfStmt` que contém labels usa CFG explícito em `branch_with_labels`, em vez de reaplicar uma guarda derivada da condição saltada. Rechecagem independente após a correção incluiu entrada em `else`, condicionais aninhadas, salto entre ramos e retorno a label no mesmo ramo: VM, nativo, reversão, recompilação e XML concordaram.

### P1 — redeclaração de array `extern` fabricava outro objeto e alterava saída

Local: `m200/frontend.py:574`, `array_declaration`.

Repro comprovado independentemente antes da correção:

```cpp
bool a[2]={true};
extern bool a[2];
void scan(){plc::output(0,a[0]);}
```

Arquivo: `/tmp/m200-language-review-repros/extern_after_definition.cpp`.

O frontend aceitava e validava o programa, mas a VM retornava `false`; o C++ nativo retornava `true`. A redeclaração alocava/zerava outra região, e a referência usava essa nova identidade.

Segundo repro: `extern bool a[2]; void scan(){plc::output(0,a[0]);}` era aceito com zeros inventados, enquanto o linker nativo corretamente recusava símbolo sem definição. Arquivo: `/tmp/m200-language-review-repros/extern_undefined.cpp`.

Correção examinada: recusa explícita de `storageClass=extern`, identificada como recurso não implementado; definição única permanece a forma disponível. Rechecagem independente confirmou erro `extern array declarations are not implemented` em ambos os repros e no equivalente i16. O implementador adicionou `test_extern_array_is_not_fabricated_or_reinitialized`.

### P2 — `validate` aceitava label antes de `JMP`, contrário à posição nativa documentada

Local: `m200/il.py:103`.

Repro independente:

```python
validate(Program([
    ["%L0:", "JMP %L1"],
    ["%L1:", "LD 1", "ST %M0"],
]))
```

Antes: validava sem erro. A evidência fornecida exige label antes de uma carga aceita ou `BLK`; a exceção de rung composto apenas de `JMP` pulava essa regra. A exportação gráfica já recusava `JMP` sem formato comprovado, mas isso não torna a aceitação pelo validador correta.

Correção examinada: validar o primeiro opcode após label antes da exceção de `JMP`. Rechecagem independente confirmou `label must precede a supported load or block`.

## Composições adicionais verificadas

Em cada um dos onze casos seguintes houve concordância entre VM original, execução C++ nativa, C++ reverso nativo, recompilação do C++ reverso e VM após round trip SMBP sintético:

| Fonte em `/tmp/m200-language-review-repros/` | Risco exercitado | Resultado |
|---|---|---|
| `array_scoped_shadow.cpp` | arrays com nomes repetidos e escopos distintos | PASS; saídas 0/1 verdadeiras |
| `array_conditional_fault.cpp` | inicializador com divisão por zero em ramo inativo | PASS; sem avaliação da falha |
| `array_partial_reservation.cpp` | leituras em inicializador parcial fora de `inner`, reservas de endereços | PASS; elementos anteriores/zerofill preservados |
| `goto_nested_inactive.cpp` | entrada por salto em condicionais aninhadas inativas | PASS; corpo e continuação corretos |
| `goto_else_same_scan.cpp` | salto de then para else no mesmo scan | PASS; resultado 3 |
| `goto_back_branch_recheck.cpp` | salto para trás dentro de ramo, múltiplas execuções | PASS; resultado 4 |
| `loop_effectful_guard.cpp` | corpo altera condição externa que ativou o laço | PASS; laço termina suas 3 iterações |
| `do_break_skip_fault.cpp` | break de do/while deve pular condição defeituosa | PASS; sem divisão por zero |
| `for_continue_inner_array.cpp` | continue condicionado por bool array local | PASS; incremento executado, soma 5 |
| `goto_initialization_order.cpp` | leitura/escrita encadeada entre elementos com repetição por goto | PASS; ordem e alias de elementos preservados |
| `goto_label_before_array.cpp` | salto para trás reexecuta declaração/inicialização parcial de array | PASS; soma 3, sem conservar o 99 de iteração anterior |

Outros repros direcionados de entrada em corpo de `while`, ramo `else` e laço sob condição externa falsa também concordaram entre VM e C++ nativo. Um candidato `goto_loop_continue.cpp` produzia um laço não terminante pela própria semântica C++ após a primeira entrada; foi descartado como bug e não integra a contagem de onze casos.

## Qualidade e limites da evidência

A escolha de manter labels e saltos na IL executável, reconstruir `goto` a partir dela e conferir a redundância de `<Label>` no XML atende ao requisito de não depender de metadados de fonte. A emissão `Jump/JMPC` tem evidência de formato no exemplar original fornecido; a recusa explícita do gráfico `JMP/JMPCN` evita inventar enums. Anchors de label têm cargas reais, e o limite de execução local acusa erro sem simular sucesso após truncar laço.

Os testes novos usam resultados manuais e C++ compilado, além de round trip; a composição adicional foi importante e encontrou o caso de `extern` que não estava na suíte. A primeira execução integrada não estava totalmente verde por expectativa de linguagem obsoleta. A rodada final corrigida foi inspecionada: 195 testes, todos verdes; essa evidência substitui a pendência inicial, sem transformar os resultados anteriores em 190/190.

A capacidade física declarada de arrays não elimina as reservas atuais do compilador; diagnósticos de memória já identificam temporários/words compartilhados. Isso continua uma lacuna de alocação da ferramenta para a meta total, não prova de que todo array dentro da capacidade bruta seja compilável. Também não houve prova de WCET, aceitação dos bytes gerados pelo editor nem conformidade física de chamadas repetidas de blocos no PLC.


## Revisão complementar da onda final

Patch adicional lido integralmente: `/tmp/m200-goal-language-review-final.patch`. Foram lidos diretamente os arquivos novos `tests/public/control_flow.py`, `tests/public/control-flow-manifest.json` e `tests/stress/control_flow.py`, além da alteração de `tests/public/fetch.py`, testes e relatórios. Sem repetir a suíte integral.

**Veredito complementar: GO local do recorte, sem novos achados bloqueantes.** A alteração de `operation()` conserva alvo e tipo em INC/DEC, reutiliza a política numérica explícita e preserva acumulador na VM/reversão. Aceitar espaço entre nome exato de função e `(` não une tokens separados.

Novos casos direcionados executados pelo revisor:

| Caso guardado em `/tmp/m200-language-review-repros/` | Cobertura | Resultado |
|---|---|---|
| `inc_dec_signed_edges.cpp` e SMBP correspondente | INC i16 a partir de -32768 em MW7999; INC i32 a partir de -2147483648; INC inativo em 32767 seguido de DEC ativo | VM, reverso nativo, recompilação e XML concordaram; saídas 0/1/2 verdadeiras |
| `inc_dec_shared_alias.cpp` e SMBP correspondente | INC MD7998 com carry para MW7999; DEC do word alto e releitura pelo dword sobreposto | Os quatro caminhos concordaram; saídas 0/1/2 verdadeiras |
| `function_space_guards.cpp` e SMBP correspondente | `SHR (` e `INT_TO_REAL (` com espaços; `SQRT (` inválido sob acumulador falso | Os quatro caminhos concordaram; sem avaliação do erro inativo |

Dez formas malformadas foram recusadas: INC em MF, MD7999/MW8000, endereço não canônico MW01, dois operandos, ausência do separador após INC, token `IN C`, função `S HR`, endereço `%MW 0` e lixo após fechamento. Quatro fronteiras ativas de overflow (INC máximo/DEC mínimo em i16 e i32) levantaram erro explícito. Essa política permanece uma limitação numérica documentada; os ensaios não comprovam flags/recuperação nativas do PLC.

### Qualidade dos ensaios adicionais

- Os dois originais públicos foram verificados independentemente por tamanho, SHA-256 e identidade de blob Git, usando o manifesto fixado. Os projetos inteiros de CPU TM221 continuam recusados; somente rungs originais isolados são executados com adaptadores visíveis, sem trocar identificação de CPU para simular aceitação.
- O oráculo do laço original usa `bit_length` sobre valores não negativos de 15 bits, coerente com as visitas ao corpo que desloca MW10 até zero. O oráculo do salto observa separadamente bobina original, alvo e adaptador pulado.
- Conferi as fórmulas do generativo: `for` soma 0..min(n,stop)-1 menos o índice pulado; `while` e `do/while` incrementam antes do corpo e excluem stop, com a primeira visita obrigatória do `do`. Totais cabem nos sete bits observados para n de 0 a 15. Há referência manual independente, C++ original/reverso, IL e XML sintético.
- Relatórios existentes registram 2 casos públicos/2048 scans e 12 casos generativos/3072 scans. Conferi que todos os hashes de implementação registrados em `PUBLIC-CONTROL-FLOW-RESULTS.json` e `CONTROL-FLOW-STRESS-RESULTS.json` correspondiam aos arquivos atuais no momento da revisão.
- Melhoria não bloqueante de rastreabilidade: o relatório público lista hashes de `m200/*.py`, enquanto o generativo inclui também SDK e runner. Registrar no público os hashes de SDK, runner, fetch e manifesto deixaria os bytes dos oráculos explicitamente vinculados ao resultado, conforme o critério de evidência do projeto.

A leitura de `/tmp/m200-goal-final-check.log` confirmou **195 testes em 67.025s, OK**. Não foi necessário executá-los novamente. Nada nesta onda altera o estado experimental ou fecha as pendências do editor oficial e PLC.

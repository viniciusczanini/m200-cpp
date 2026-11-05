# Auditoria local intensiva — m200-cpp, 2026-11-05

Escopo: revisão independente do HEAD inicial `1b123ee8dfe8bb0850906078467bdf8aae753827`, com testes executados exclusivamente no Mac. Nenhum módulo da ferramenta, índice ou HEAD foi alterado pelo auditor. Após autorização adicional, foi criado somente `tests/test_numeric_stress.py` no repositório para a extensão numérica. O responsável principal aplicou correções simultaneamente; por isso os resultados de execução também registram o estado do diretório de trabalho e devem ser lidos junto ao log, não apenas ao hash HEAD.

## Achados concretos

### 1. Macro injetada dentro do namespace do SDK altera comportamento sem ser compilada (prioridade alta)

Reprodução mínima, observada antes da correção do responsável principal:

```cpp
#define input(x) input(x); void output(int,bool); __attribute__((constructor)) inline void before_scan(){output(0,true);} bool ignored(x)
#include <plc.hpp>
#undef input
void scan(){}
```

`compile_source` aceitou e emitiu **zero rungs**. Em dois scans, a IL produziu `%Q0.0 = false,false`, enquanto `run_native` do fonte original produziu **true,true**. Não depende de `#ifdef PLC_NATIVE` no fonte do usuário: a mesma macro atua nas duas variantes do SDK.

Causa: a origem do `NamespaceDecl plc` foi considerada suficiente para confiar em todos os descendentes; declarações expandidas por macro do usuário dentro de `sdk/plc.hpp` não passaram pela allowlist. `check` detecta a divergência, mas o comando `compile` sozinho aceitava o fonte e gerava lógica incompleta. Fonte reproduzível: `baseline/sdk_macro_constructor_escape.cpp`. A correção simultânea do responsável já recusou a reprodução nos logs posteriores.

### 2. XML com valores escalares contendo elementos desconhecidos era aceito (prioridade média)

Três casos reais aceitos por `load_project` antes da correção:

- `SoftwareConfiguration/FastTask/Period` com texto `255` seguido de `<UnknownActive>true</UnknownActive>`.
- `TimerTM/Preset` com texto `20` seguido do mesmo elemento desconhecido.
- `InstructionLine` com uma instrução válida como texto inicial, seguida de `<UnknownInstruction>JMP %L9</UnknownInstruction>`.

O parser extraía o texto e ignorava os filhos. Isso viola a recusa explícita do formato desconhecido. Não foi alegado que o editor oficial executaria esses filhos; o problema comprovado é a aceitação silenciosa pelo subconjunto conservador. Reproduções: `baseline/fast_period_nested.smbp`, `baseline/timer_preset_nested.smbp`, `baseline/il_instruction_nested.smbp`. A correção simultânea já recusou os casos.

### 3. Profundidade XML causava exceção não tratada (prioridade média)

Um documento pequeno, com aproximadamente 1.300 elementos `<x>` aninhados sob `ProjectDescriptor`, causou `RecursionError` em `unique_tree`, propagada pelo CLI. O limite de 20 MB não limita profundidade. Arquivo: `baseline/deep_1300.smbp`. Depois da correção simultânea, o parser passou a recusar profundidade superior a 64 com `M200-E`.

### 4. DTD/entidades em XML UTF-16 escapam da rejeição textual (prioridade média)

`baseline/dtd_utf-16.smbp` contém DTD com entidade `x = TM200CE40T` usada em `Reference`. Foi aceito e a entidade foi expandida. O mesmo XML em UTF-8 foi recusado corretamente. Causa: busca por bytes ASCII `<!DOCTYPE`/`<!ENTITY` não encontra a codificação UTF-16 com bytes NUL intercalados. A regra documentada de rejeitar DTD deve ser aplicada após reconhecer a codificação, ou por parser que proíba DTD em qualquer codificação suportada. Não foi executada amplificação grande nem acesso externo.

### 5. Chaves de timer JSON distintas podem normalizar para o mesmo índice (prioridade média)

`Program.from_dict` converte as chaves com `int(k)` em uma compreensão. As chaves `"0"` e `"00"` são aceitas juntas e a última substitui a primeira silenciosamente. O arquivo `baseline/timer_index_alias.json` reproduz a aceitação; trocar `milliseconds` no segundo objeto demonstra a alteração silenciosa da configuração efetiva. Convém exigir chaves canônicas e unicidade depois da normalização.

### Observação de política

`baseline/unknown_json_field.json` demonstra que um campo de topo JSON desconhecido é ignorado. Isso não prova divergência de execução e pode representar uma política de extensão deliberada. Foi marcado pelo script como aceitação inesperada, mas tem prioridade menor que os achados anteriores. Decidir explicitamente entre extensibilidade e allowlist fechada, em vez de tratá-lo como equivalência comprovada.

## Testes reproduzíveis

`audit.py` usa semente `20020261105`, limite de CPU de 240 segundos e tamanho máximo de arquivo de 64 MiB. Os subprocessos do compilador e da execução têm os timeouts existentes da biblioteca. Nenhuma dependência é instalada.

```sh
python3 /tmp/m200-intensive-audit-20261105/audit.py \
  --repo /Users/tommy/Offline/projects/m200-cpp \
  --output /tmp/m200-intensive-audit-20261105/retest
```

Famílias: 16 programas booleanos com macros normais, scopes/sombreamento, helpers repetidos/aninhados, promoção booleana de XOR, igualdade, atribuição sequencial, captura de condição, leitura de imagem de saída e reservas brutas `%M0/%M499/%M500/%M1023`; 768 frames por programa; programa misto de classes com 10.000 frames; cada uma das seis classes do SDK; recusas de aritmética, chamada condicional/duplicada, temporário, índice dinâmico, inteiro não usado e `static` local; XML ambíguo/duplicado/atributos/profundidade/DTD; aliases JSON; preservação de edição manual, arquivo desconhecido, destino symlink e sidecar de configuração.

`il_properties.py` usa semente `20020261106`, compara uma **oracle Python independente**, o executor IL e o C++ reverso nativo, exercitando todos os operadores IL aceitos (`LD/LDN`, `AND/ANDN`, `OR/ORN`, `XOR/XORN`, `ST/S/R`), memória e saídas sequenciais, constantes e `%S4..%S7/%S13`. Também recompila um programa menor cobrindo todos esses operadores.

```sh
python3 /tmp/m200-intensive-audit-20261105/il_properties.py \
  --repo /Users/tommy/Offline/projects/m200-cpp \
  --output /tmp/m200-intensive-audit-20261105/il_retest
```

## Limitações reveladas pelos testes, sem tratar recusa conservadora como bug

- Um fonte booleano de 200 bits/234 rungs passou na comparação original/IL/C++ reverso; **recompilar** o reverso esgotou os 524 bits alocáveis porque os endereços originais reservam memória e a nova tradução aloca mais temporários. O reverso é válido para auditoria nativa, mas não existe garantia geral de recompilação dentro do orçamento original.
- `bool a{plc::input(0)}` foi recusado por `InitListExpr`; `auto a=plc::input(0)` foi aceito. Documentar as formas sintáticas aceitas de inicialização ajuda a evitar a impressão de C++ booleano geral.
- Helper variádico `bool f(bool a,...){return a;}` foi aceito e comparou corretamente neste caso. Se o contrato é somente parâmetros booleanos explícitos, vale recusar a propriedade AST `variadic`.
- O primeiro ensaio do programa misto usou `9999 ms` no timer de índice 7 e foi corretamente recusado por falta de representabilidade nesse índice. O script final usa `10000 ms`; esse foi um erro de preparação do ensaio, não um bug do compilador.

## Famílias ainda necessárias para uma biblioteca completa

1. **Modelo oficial e hardware:** template autêntico TM200CE40T, abrir/salvar/compilar no editor, reler o arquivo salvo, diferenças de versões, warnings e recursos reais; executar casos no simulador oficial e no CLP. Os testes locais não validam XML oficial, conectividade Ladder real nem temporização física.
2. **Temporização e ciclo de vida:** limites de todas as bases/presets/índices, quantização e fronteiras de scan, jitter, tempo zero, TOF/TP retrigger, enable/disable, STOP/RUN, warm/cold start, reinício, retenção e perda de alimentação. Um teste nativo usa o mesmo contrato local de tempo, não substitui a medição externa.
3. **Recursos de biblioteca ausentes na linha de base inicial:** inteiros/words/dwords com política explícita de overflow e signedness, comparações e aritmética, divisão por zero, shifts/conversões, contadores, blocos de memória/registradores, Modbus/serial/Ethernet, expansões, HSC e PTO/PWM, eventos e prioridades. Não aceitar esses recursos silenciosamente antes de implementá-los.
4. **Compilação:** matrizes de versões Clang/macOS/Linux, mais propriedades de equivalência, macros/includes/atributos, overloads/variádicas, formas válidas de inicialização, diagnósticos com paths Unicode/espaços e uso de recursos nas fronteiras. Comparação original/reversa compartilha o SDK; manter uma oracle independente para propriedades onde for viável.
5. **Parser e persistência:** todas as codificações XML permitidas, DTD/entidades proibidos, profundidade/largura/tamanho, scalars e cardinalidades completas, propriedades JSON desconhecidas/duplicadas e aliases, arquivo truncado; fault injection de falta de espaço/permissão no meio da substituição, rollback/recuperação e concorrência de leitura/escrita. Os testes executados provaram preservação nos cenários listados, não transação atômica para toda falha de I/O.

## Resultados de execução

Para uma linha de base imutável, foi extraído `git archive 1b123ee8dfe8bb0850906078467bdf8aae753827` em `head-1b123ee/` dentro desta pasta temporária. Isso não criou branch/worktree nem alterou o repositório. Os resultados definitivos do HEAD inicial estão em `stable-head/results.json`, `stable-head.log`, `stable-il/results.json` e `stable-il.log`.

- **25.744 frames válidos** de C++ original, IL e C++ reverso concordaram: 16 fontes booleanos ×768, programa misto stateful ×10.000, seis classes ×512 e três sondas sintáticas ×128.
- **12.000 frames** de IL gerada concordaram com oracle Python independente e C++ reverso nativo; recompilação adicional de todos os operadores IL passou **100 frames**.
- A fonte de macro SDK do achado 1 reproduziu a divergência em dois scans no snapshot imutável: `stable-head/sdk_macro_constructor_escape.mismatch.json`.
- O snapshot também confirmou os três XML escalares aceitos, o crash de profundidade XML, a aceitação de DTD UTF-16, a colisão de chaves JSON e a observação de campo JSON desconhecido.
- Nenhuma divergência ocorreu nos programas válidos aceitos do subconjunto documentado. Isso delimita a evidência; não comprova equivalência universal.
- O ensaio `stress2.log` foi interrompido por edição simultânea do SDK. Seus resultados parciais não são usados como evidência de regressão estável.

Sonda adicional de JSON: `deep-program.json`, com metadata de 1.300 níveis, causou `RecursionError` não tratado no CLI `inspect`; stderr em `deep-program-cli.stderr`. O tratamento de profundidade deve abranger também JSON, trace e manifesto.


## Extensão numérica integrada — teste autorizado adicional

Foi criado somente `/Users/tommy/Offline/projects/m200-cpp/tests/test_numeric_stress.py` no repositório, mediante autorização explícita do responsável principal. Não houve alteração dos módulos, índice ou HEAD pelo auditor.

**Execução final: 8 métodos, zero falhas, 36,771 s.** Comando reproduzível:

```sh
python3 -m unittest discover -s tests -p test_numeric_stress.py -v
```

Evidência: `numeric-stress-final.log`. A suíte cobre:

- 47 intrínsecos com resultados declarados, comparação nativa/IL/reversa e recompilação do reverso;
- 88 vetores inteiros adicionais, semente `0x200CE40`, com oracle própria baseada em inteiros Python e strings de bits;
- 16 casos de fronteira float/conversão: mantissa, subnormal, zero com sinal, arredondamento ties-to-even, INT32_MIN e maior REAL32 abaixo de INT32_MAX;
- todos os seis comparadores com literais REAL32 não exatamente representáveis como decimal;
- 10 operações transcendentes com valores não triviais, comparadas a uma referência separada com tolerância explícita, sem prometer igualdade de bits entre implementações libm;
- 2.048 scans de estado i16/i32/f32, guardas e escrita retida condicional, com histórico esperado calculado independentemente;
- 27 domínios inválidos recusados em execução, sem fabricar valor no destino;
- oito famílias de erro com operandos variáveis em branches aninhados e curto-circuito: devem ser ignoradas quando a condição é falsa. Falhas com operandos todos literais continuam sendo recusadas estaticamente pela política conservadora do compilador.

### Bug numérico encontrado e corrigido pelo responsável principal

`numeric.read` lia um literal REAL32 usando `float(value.code)`, produzindo um valor Python binary64 da representação de nove dígitos, em vez de quantizar novamente para binary32. Exemplo: o fonte válido `plc::real_to_dint(-2147483648.0f)` era recusado por overflow, pois a representação `-2.14748365e+09` era lida como `-2147483650`. A mesma causa afetava igualdade de `0.1f`.

A falha foi preservada no log inicial `numeric-stress.log` e nos fontes `numeric-repros/float_4.cpp`; o responsável corrigiu o leitor. Três regressões direcionadas passaram (`numeric-targeted-results.json`) e a suíte completa final de oito métodos passou. A oracle dos testes não importa nem chama `m200.numeric.evaluate` para obter os resultados esperados.

## Reteste final dos achados de importação/frontend

O script `retest_findings.py` executou as reproduções mínimas pelo CLI público do checkout atualizado. **Nove de nove casos foram recusados com código 1 e mensagem `M200-E`, sem traceback**: macro SDK, três scalars XML, profundidade XML, DTD UTF-16, alias de índice JSON, campo JSON desconhecido e profundidade JSON. Evidências: `findings-retest.log` e `findings-retest-results.json`; este último registra também hashes dos módulos verificados.

As limitações de orçamento para recompilar fontes reversos grandes, a validação oficial do projeto e os testes físicos permanecem fora da conclusão de equivalência. Nenhuma CI, instalação, ação remota, transmissão ao CLP ou teste com cargas foi executado.

## Integração e reteste do responsável principal

Os scripts foram preservados em `tests/stress/boolean_audit.py` e `tests/stress/il_properties.py`. `make stress` executa ambos em um diretório temporário novo e transforma achados inesperados em falha do comando. A execução integrada final passou com 37.716 scans; o total é 128 menor que a linha de base pois helper variádico passou a ser recusado. Todos os nove repros iniciais foram recusados por `M200-E` no reteste independente. A expansão numérica e seus consertos passaram em `make check` com 91 testes. Resultados e hashes estão em `STRESS-RESULTS.json`.

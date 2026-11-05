# Resultado local — 2026-11-05

Estado: protótipo experimental. O usuário autorizou desenvolver e testar localmente agora; Windows com software oficial e CLP será disponibilizado no futuro por SSH.

## Verificações executadas

- `make check`: **45 testes, zero falhas**.
- `uvx ruff check m200 tests m200c`: passou.
- `git diff --check`: passou.
- `make examples`: geração do exemplo e comparação do latch em 64 frames passou.
- Comparação do teste automatizado: C++ original, executor IL e C++ reconstruído concordaram em **200 frames pseudoaleatórios reproduzíveis**.
- Ciclo adicional do exemplo de clock: C++ → SMBP com fixture sintética → leitura da IL real → C++ → nova compilação; **64 frames** concordaram. A cópia `.configuration.smbp` permaneceu byte a byte igual ao projeto de entrada.

Esses resultados não significam aceitação no editor da Schneider, precisão física de tempo ou equivalência universal para C++/SMBP.

## Revisão independente

Uma revisão de código independente do commit inicial `83b1503` encontrou cinco problemas importantes. Todos receberam reprodução RED antes da correção e a suíte completa voltou a passar:

1. Declarações expandidas por macros escapavam do filtro de origem. Corrigido normalizando a localização de expansão antes de validar declarações. Testes: `test_macro_expanded_declarations_cannot_hide_executable_code` e `test_normal_macro_definitions_are_validated_as_cpp`.
2. Alguns contêineres de configuração e nomes reais `DiscretInput` não eram examinados. Corrigido com validação de campos e defaults inativos, recusando funções desconhecidas/ativas. Teste: `test_unknown_active_configuration_and_real_io_entry_names_fail_closed`.
3. Contêineres/campos XML duplicados podiam esconder instruções. Corrigido com cardinalidade por esquema do subconjunto, incluindo propriedades de timers e gráficos. Testes: `test_duplicate_xml_singletons_cannot_hide_program_data` e `test_unmodeled_xml_attributes_are_rejected`.
4. Um arquivo manual com nome de artefato conhecido podia ser removido sem constar no manifesto anterior. Corrigido exigindo propriedade pelo manifesto, além de conferir conteúdo. Teste: `test_rebuild_does_not_delete_a_file_absent_from_old_manifest`.
5. Descompilar sobre o próprio projeto podia apagar a entrada e contaminar a cópia de configuração. Corrigido recusando sobreposição de caminhos/aliases e saídas existentes, lendo a entrada antes da escrita e preparando ambos os resultados. Teste: `test_decompile_rejects_source_output_and_sidecar_aliases`.

Não houve uma segunda revisão independente; as correções foram verificadas pelos testes de regressão e pela suíte completa. Não ficaram achados menores relatados pelo revisor.

## Decisões e limites mantidos

- **Desenvolvimento antes do Windows:** autorizado pelo usuário. A geração experimental avança, mas a compatibilidade oficial permanece pendente. Custo: ainda não há um projeto comprovado no editor ou no CLP.
- **Subconjunto booleano:** aritmética inteira, loops e demais recursos ainda não implementados são recusados. Custo: programas que o hardware talvez suporte precisam esperar extensão do frontend.
- **Template exato:** usar um projeto autêntico TM200CE40T. A fixture sintética só testa o parser. Custo: o perfil/defaults reais ainda precisarão ser ajustados e validados quando houver editor.
- **Base XML de timer de 10 ms:** exportação é recusada porque sua enumeração não foi estabelecida por um exemplo inspecionado. Custo: alguns programas com mais de seis timers de resolução fina só têm IL/modelo local nesta versão.
- **XML ambíguo ou desconhecido:** rejeitado independentemente de o editor oficial aceitar, ignorar ou executar aquela forma. Custo: importação mais restrita que a oferta completa da Schneider.
- **Instâncias inteiramente não usadas:** permitidas; a regra de uma atualização incondicional vale para instâncias utilizadas. Custo: declarações não utilizadas ainda podem reservar recursos. A documentação foi alinhada ao comportamento.
- **Alocação conservadora:** esgotamento ou índice de timer inviável gera erro; não há promessa de alocação ótima. Custo: um programa pode precisar ser simplificado mesmo que uma futura otimização o fizesse caber.
- **Comparação nativa/IL:** ambos implementam um modelo local de tempo. Ela detecta divergências de tradução, mas não estabelece tempo real do CLP. Custo: precisão, fase, jitter, STOP/RUN, retenção, interface elétrica e operação com cargas aguardam testes físicos/oficiais.

A revisão deliberadamente não julgou firmware/nível funcional, conectividade real do Ladder, enumerações/defaults de todas as versões, comportamento físico ou recursos explicitamente fora do subconjunto. Esses limites não foram convertidos em alegações de compatibilidade.

## Ampliação de capacidades e estresse — 2026-11-05

Nova verificação final, após a revisão independente da expansão numérica:

- `make check`: **91 testes**, todos aprovados (46,141 s nesta execução).
- `make examples`: aprovou os exemplos booleanos e o novo `numeric_control.cpp`; comparação original C++/IL/C++ reverso em 64 frames por conferência.
- `make stress`: **37.716 scans válidos**, sem divergências nos programas exercitados, com sementes 20020261105 e 20020261106. Inclui 12.000 scans confrontados também com oracle Python independente e 100 scans de recompilação dos operadores booleanos reversos. Esta contagem substitui a de 37.844 do snapshot inicial: helper variádico agora é corretamente recusado, reduzindo 128 scans aceitos.
- A matriz numérica incluída em `make check` cobre os 47 intrínsecos, 151 vetores fixos/aleatórios/de fronteira, 10 casos transcendentes não triviais, 2.048 scans de histórico com referência independente, 27 erros de domínio e oito famílias de falha sob guarda.
- `uvx ruff check m200 tests m200c` e `git diff --check`: aprovados.
- Inventário: 250 registros documentais, 13 conflitos de fontes. Não equivale a 250 recursos implementados.

Relatório reproduzível e hashes das fontes: `STRESS-RESULTS.json`. A auditoria independente inicial e os repros estão descritos em `INTENSIVE-AUDIT.md`; os scripts foram incorporados em `tests/stress`. A validação oficial continua pendente.

Falhas encontradas e corrigidas com regressões RED/GREEN: macro alterando declarações dentro do SDK; filhos XML ocultos em escalares; profundidade XML/JSON; DTD em UTF-16; aliases e duplicatas de JSON; helpers variádicos; literais REAL32 lidos como binary64; unsigned descartado na comparação; TRUNC perdendo zero negativo; comparação numérica lida em ramo de curto-circuito inativo; negação literal repetida; metadados inválidos de símbolos/origem; e remoção de espaços dentro de tokens gráficos. A revisão independente listou quatro problemas importantes e dois menores; todos receberam correções e testes. O SDK nativo passou também a recusar leitura REAL não finita, alinhando seu domínio ao executor local.

Semântica física de overflow e flags aritméticos, blocos/periféricos restantes, enums não comprovados, retenção e modos de partida/STOP/RUN continuam abertos. Nem os testes de estresse nem o XML coerente estabelecem compatibilidade oficial ou comprovação de watchdog/tempo de scan.

## Projetos originais e Modbus — versão 0.2.0, 2026-11-05

Verificação final desta etapa: **173/173 testes aprovados**, 51,987 s; inclui 48 testes de protocolo/estado/transportes Modbus, configuração XML, integração C++/IL/SMBP, sockets TCP reais em 127.0.0.1 e reversão. `make examples` também aprovou a nova amostra `examples/modbus_read.cpp`, com a ausência de transporte modelada como erro explícito.

Dez arquivos públicos foram obtidos em commits fixados e verificados por tamanho, SHA256 e GitblobSHA1. `make public-check` passou 19 casos/16.128 scans com oráculos independentes, IL original isolada, C++ reverso nativo e IL recompilada; nenhum original foi modificado e nenhum projeto estrangeiro inteiro foi importado. `make stress` passou novamente 37.716 scans. São 53.844 scans públicos+estresse, além dos casos da suíte unitária.

Correções desta rodada com regressões: OPER inline e ações após bobina; timer com LD negativo e posições comprovadas; CPU estrangeira identificada no diagnóstico; buffers de comunicação reservados antes dos temporários; timeout Int32; criação de socket com erro controlado; índices nativos esparsos preservados; status antes do BLK; Type.NET permitido somente em seu contexto; alocação manual suficiente; e validação de candidato antes de substituir o arquivo anterior. Um teste end-to-end gerou e releu o projeto e recebeu os registradores 4660/65535 de um servidor TCP local através do programa IL compilado.

A revisão independente do núcleo e da integração XML encontrou as falhas de representação, socket, status antecipado, contexto Type e alocação, todas corrigidas e cobertas pelas regressões. `ruff` e `git diff --check` aprovados. Resultados e hashes atuais: `PUBLIC-MODBUS-RESULTS.json` e `PUBLIC-PROJECTS-RESULTS.json`. O antigo `STRESS-RESULTS.json` continua sendo o registro histórico da etapa anterior.

Limites permanecem explícitos em `../MODBUS.md` e `../capabilities/README.md`. A biblioteca não está completa; XML de certas variantes Modbus, demais recursos nativos e validação no Machine Expert Basic/TM200CE40T físico continuam pendentes. Não houve CI, publicação, conexão a dispositivo real nem tentativa de transmissão ao PLC.

## Continuação do objetivo: arrays e fluxo nativo

Objetivo de equivalência completo explicitamente ativado pelo usuário. Arrays
fixos bool/i16/i32/f32 com índice literal, inicialização parcial, persistência e
escrita condicional foram implementados. While/for/do, break/continue, labels e
goto são traduzidos para saltos que executam no mesmo scan. IL/VM/reversão
aceitam JMP/JMPC/JMPCN e INC/DEC; XML usa Jump/JMPC observado num original.

Verificação integrada em 2026-11-05: **195/195 testes em 67,025 s**, exemplos
incluindo `loops.cpp`, lint e diff aprovados. `make stress` passou 37.716 scans
anteriores mais **3.072 scans em 12 composições de laços**, com fórmula
independente, C++ original, IL, C++ reverso nativo, recompilação e XML sintético.
`make public-check` passou novamente 19 casos/16.128 scans. Dois novos originais
baixados e verificados por tamanho/SHA256/GitblobSHA1 forneceram saltos e laço
reais: `make public-flow-check` passou **2 casos/2.048 scans**. Total público e
estresse desta rodada: **58.964 scans**, além da suíte unitária. Nenhum CPU foi
reescrito e os projetos estrangeiros completos continuam recusados.

RED/GREEN corrigiu goto entrando em ramo sem avaliar sua condição, array extern
recriado indevidamente, label antes de opcode inválido e espaços legítimos em
funções IL de um original. A expectativa antiga de recusar qualquer while foi
substituída pelos novos testes de execução e erro explícito de limite local.
Revisão independente e composições adicionais: `LANGUAGE-REVIEW.md`.
Relatórios com hashes: `CONTROL-FLOW-STRESS-RESULTS.json` e
`PUBLIC-CONTROL-FLOW-RESULTS.json`. Resultados antigos permanecem históricos.

Ainda faltam indexação dinâmica, alocação/reuso sem reservas artificiais,
estruturas/operadores restantes, blocos/periféricos e os demais itens do
inventário. `COUNTER-RESEARCH.md` registra a contradição documental de E e
exemplares de configuração/gráfico, sem declarar o contador implementado.
Validação no editor e no hardware permanece pendente; o objetivo não foi
declarado completo.

## Continuação do objetivo: alocação e reuso

O lowerer passou a emitir registros privados virtuais e alocá-los somente após
montar o CFG completo. A análise considera vida entre scans, saltos para trás,
escritas condicionais e a ordem das instruções dentro de cada rung. Globais e
estado de instâncias conservam células únicas; acessos explícitos e buffers
inteiros de comunicação permanecem reservados. Todos os 1024 bits M e 8000
words compartilhados podem ser usados; 500/4000 são preferências de posição.
Aliases de 16/32 bits e símbolos de reuso também são contabilizados.

Verificação final desta etapa em 2026-11-05: **207/207 testes em 118,046 s**,
`make examples`, `make public-check`, `make public-flow-check` e `make stress`
com saída zero, lint e diff aprovados. Foram novamente **58.964 scans** públicos
e de estresse, além dos testes unitários. A saída de `examples/loops.cpp` foi
idêntica em bytes com PYTHONHASHSEED1 e2.

Os testes de pressão incluem 600 bits globais (com ida e volta), 4200 words
globais (C++ nativo/VM/XML), 1100 locais mortos, 300 atualizações sequenciais,
vida em laços/entre scans, aliases ímpares e buffer Modbus de125 words. O teste
antigo que recusava1100 locais foi atualizado: esses locais cabem por reuso;
1100 globais persistentes continuam recusados. RED/GREEN cobriu também o
relatório CLI com a capacidade antiga, interferência entre escrita e leitura
posterior no mesmo rung, símbolos MW/MD/MF sobrepostos e instrução sem modelo
de efeitos. Revisão e rechecagem independentes: `ALLOCATION-REVIEW.md`.

`MEMORY-ALLOCATION-RESULTS.json` registra comandos, resultados e hashes atuais.
Os relatórios de fluxo foram atualizados pela nova execução; relatórios antigos
de outras etapas permanecem históricos. Coloração gulosa e análise conservadora
não são prova de alocação ótima. A segunda tradução ainda pode exceder o
orçamento provisório de instruções ou memória, mesmo existindo uma solução
nativa menor. Essas lacunas, indexação dinâmica e demais recursos do inventário
continuam no objetivo ativo; editor e PLC permanecem pendentes.

## Continuação do objetivo: indexação nativa de words

`plc::WordMemory` e as seis operações read/write de MW/MD/MF indexadas por MW
foram implementadas em frontend, IL, VM, SDK, reversão e XML experimental. A
imagem inteira é reservada, incluindo limites e buffers; guardas preservam o
limite lógico quando os temporários ficam mais altos. `%S20` é sticky e somente
R/`clear_index_error()` pode limpá-lo. Índice inválido usa sentinel-32768 para
provocar o erro/fallback no acesso nativo; não se emite S/ST%S20. Snapshots/CFG
protegem ramos inativos, curto-circuito e a ordem de leitura do lado esquerdo.

Verificação final em 2026-11-05: **221/221 testes em 99,096s**, exemplos incluindo
`indexed_words.cpp`, lint/diff e todos os comandos locais com saída zero.
`make stress` executou novamente 37.716 scans antigos,3.072 de laços e
**10.240 scans em dez casos indexados** com oráculo independente de words,
C++ nativo, IL recompilada, segunda reversão e SMBP. Foram conferidos dados,
índice e flag da VM em cada frame. `make public-check` passou novamente
19casos/16.128scans e `make public-flow-check`2casos/2.048scans. Total público
e estresse desta rodada: **69.204scans**, sem somar rodadas repetidas.

Regressões RED/GREEN cobrem o literal de atribuição de array após a mudança de
ordem RHS/lvalue, flag à esquerda antes de RHS indexado, ST%S20 em saída de
timer e alocação XML omitida/vazia burlando a recusa de limite desconhecido.
Acesso indexado sob AND/OR bruto permanece explicitamente recusado, pois o
efeito de erro mesmo sem energia não está documentado; o frontend C++ evita
esse padrão. Revisão e rechecagem: `INDEXED-REVIEW.md`.

O perfil de8000words foi exercitado com transferência MD7998 indexada,
fallback e reversão, sem exigir temporário numérico adicional. Não se conclui
daí que todo programa que cabe nativamente já cabe no compilador. Operações
compostas, grupos/arrays C++ dinâmicos, bits indexados e overhead continuam
trabalho aberto. Casos de maior referência direta/ForcedCount/defaults e
fronteiras MD/MF precisam de comprovação externa; o teste local não a substitui.

`INDEXED-STRESS-RESULTS.json` e `INDEXED-LOCAL-RESULTS.json` registram os bytes
testados. `INDEXED-SEMANTICS.md`, `INDEXED-ORIGINALS.md` e os manifestos conservam
fontes primárias e as lacunas. Um SMBP público adicional foi obtido diretamente
da FAQ Schneider FA361549 e preservado sem alterar sua CPU TM221CE24R; comprova
sete formatos de blocos ATV, não aceitação no CE40T nem cobertura runtime deles.
Os instaladores verificados exigem cadastro; nenhum EXE/DLL foi baixado ou
executado. Ver `../capabilities/VENDOR-STATIC-RESEARCH.md`.

## Continuação do objetivo: arrays com índice calculado

Rodada local após a base6159c4c: **243/243 testes**, em132.263s; exemplos,
lint, formatação e diff passaram. Os três stress anteriores passaram novamente
(37.716 +3.072 +10.240 scans), assim como os programas públicos isolados
(16.128 +2.048 scans). O stress novo adicionou11.264 scans/11casos. Total da
rodada: **80.468 scans públicos e de stress**, sem somar reruns nem unitários.
Os quatro scripts de stress estão no alvo `make stress`; nesta rodada foram
executados individualmente para não repetir o novo script já concluído.

Arrays bool/i16/i32/f32 agora aceitam índices bool/i16/i32 calculados em
execução, com grupos contíguos e stride correto. Grupos de4200words e900bits
passaram; o booleano grande também foi revertido/recompilado após reduzir
cópias desnecessárias nas atribuições. Testes cobrem RHS/lvalue, reexecução de
declarações locais, inicialização parcial, membros anteriores, shadowing,
curto-circuito, índices extremos e proteção de aliases/buffers Modbus.

Bits indexados estão implementados em SDK/IL/VM/reversão, com BitMemory e
WordMemory para a API raw. **SMBP de bits indexados continua recusado**, pois
falta comprovar a correspondência entre nível funcional10.0 e token de projeto.
O teste preserva um destino existente quando a exportação é recusada. O XML
numérico passou ida/volta no perfil sintético; isso não comprova o editor.

A revisão independente não encontrou falhas confirmadas e executou casos
adicionais de aliases e ordem. O C++ original com `[]` inválido não foi
executado (comportamento indefinido); a política S20/fallback foi exercitada
na VM e no C++ reverso seguro. A auditoria antiga marcou
`repository_status_unchanged=false` porque arquivos de documentação/relatórios
mudaram em paralelo; não se afirma árvore imutável durante a bateria.

Resultados/hashes: `DYNAMIC-ARRAY-LOCAL-RESULTS.json` e
`DYNAMIC-ARRAY-STRESS-RESULTS.json`; contratos e limites em
`../capabilities/DYNAMIC-ARRAYS.md`. O inventário CLI e exemplos foram
atualizados. O objetivo integral continua ativo e incompleto; demais famílias,
perfil de bits, overhead e validação oficial/física continuam pendentes. Tudo
local, sem CI, publicação, conexão ou transmissão ao PLC.

## Continuação do objetivo: propriedades de temporizadores

Após50140dd, P/V/Q de TON/TOF/TP e escrita P foram integrados em C++/IL/VM,
SDK, XML sintético e reversão. Construtores explícitos conservam o índice,
base e preset, incluindo TM42/TM254. O modelo não retentivo/não dinâmico
captura P na ativação; escrever P durante a execução não muda esse preset
ativo. V/Q continuam avançando sob salto, enquanto a saída ligada ao bloco
só é escrita se ele executa. A fase física do tick continua sem comprovação.

Rodada final: **253/253 testes em80.816s**, `make examples`, `make stress`,
`make public-check`, `make public-flow-check`, lint/formatação/diff com saída0.
O stress novo tem15casos tipo/base e1atribuição real isolada,8192scans.
Stress total70.484; públicos18.176; **88.660 scans na rodada**, sem multiplicar
pelas etapas de comparação nem somar reruns ou unitários.

O caso público usa a atribuição real `%TM1.P := %MW20[%MW10]` e configuração
original TOF/TM1/base1s de I1. Seu hash foi conferido antes/depois; não houve
reescrita de CPU nem importação integral desse projeto M221. Todos os
XMLs aprovados continuam do perfil sintético local, sem aceite oficial.

A revisão encontrou um conflito do harness que incluía iostream com uma
variável válida chamada clock. Foi reproduzido e corrigido mantendo o teste
com o mesmo nome. A rechecagem passou10/10 e conferiu0ms/EOF vazio, completo
e truncado. Colisões preexistentes com nomes C getchar/putchar continuam
documentadas. A auditoria antiga observou árvore mudando por documentação e
relatórios concorrentes; os hashes atuais, e não o HEAD anterior isolado,
identificam o código da bateria.

Os relatórios `TIMER-PROPERTY-LOCAL-RESULTS.json` e
`TIMER-PROPERTY-STRESS-RESULTS.json` vinculam resultados aos bytes atuais.
`../capabilities/TIMER-PROPERTIES.md` descreve contratos e limites. Timers
retentivos/DynamicPreset=true, XML de base10ms, demais famílias e validação
oficial/física permanecem pendentes. Objetivo ativo/incompleto; tudo local,
sem CI ou transmissão ao PLC.

O objetivo integral continua ativo; Task2 do plano de indexação ainda está
pendente e não foi substituída pela API de words explícitos.

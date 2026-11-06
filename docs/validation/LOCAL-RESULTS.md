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

## Continuação do objetivo: modos retentivo e preset dinâmico

Após `12ab05b`, TON/TOF retentivos e Dynamic Preset em TON/TOF/TP estão
implementados em configuração/JSON, C++, SDK, IL/VM e reversão. O construtor
de cinco argumentos conserva bools, índice e base. TP retentivo e bools
malformados são recusados. Timers antigos continuam com flags false.

O modelo retém V inteiro na pausa e retoma a contagem; P dinâmico é aplicado
na próxima atualização da base. Redução de P abaixo de V conclui mantendo V,
conforme os diagramas. Fase/fração dos ticks e crescimento de P após concluir
continuam políticas locais sem prova física. O XML dos modos true é recusado
antes de substituir destino por falta do mapeamento de nível funcional.

Rodada final após pausa/retomada: **265 testes em 88,739 s**; exemplos, stress,
ensaios públicos e lint/formatação/diff passaram. Os processos anteriores
foram confirmados ausentes e os logs temporários não estavam disponíveis;
a rodada final usa logs e códigos de saída persistidos no projeto. Não se
somaram execuções anteriores à retomada nem reruns.

O stress novo tem 36 casos, incluindo todas as cinco bases, com 18.432 scans
e oráculo independente por eventos de tick. Stress total: 88.916 scans;
públicos: 18.176; **107.092 scans na rodada**, sem multiplicar pelas etapas de
comparação. O caso público retentivo usa somente a configuração real TM3 de
`06-correto.smbp`/TM200CE24R, com harness construído; não foi encontrada execução
de TM3 no original. Seus bytes/CPU não foram alterados e não se alegou
importação integral. O suporte anterior a XML sem flags continua testado.

A revisão independente não encontrou falhas e conferiu ainda igualdade P/V,
próximo tick nas cinco bases, retenção/reset e rejeições de XML malformado ou
duplicado. A CLI mantém `library.complete=false` e descreve o novo escopo.

Resultados e hashes: `TIMER-MODE-LOCAL-RESULTS.json` e
`TIMER-MODE-STRESS-RESULTS.json`; contrato: `../capabilities/TIMER-MODES.md`.
Todos os sete relatórios atuais de stress/rodada conferem com os hashes do
código. As demais famílias e a validação oficial/física permanecem abertas.
O objetivo integral continua ativo. Tudo local, sem CI, publicação ou PLC.

## Continuação do objetivo: lógica nativa e Ladder normalizado

Após `2facc4f`, STN/N, MPS/MRD/MPP e grupos AND(/OR( estão implementados em
IL/VM e reversão. Timer com entrada composta e ST/STN/S/R também é convertido;
IN direto é aceito quando seu acumulador posterior não é consumido. As outras
sequências permanecem recusadas até resolver esse efeito, sem inventá-lo.

O exportador traduz formas complexas para rungs série usando elementos Ladder
existentes, sem modificar o programa original. Snapshots preservam valores antes
das escritas; endereços/buffers e labels existentes ficam reservados. Guardas
reais protegem comparações sob curto-circuito, inclusive NaN por alias MD/MF.
Os modos/limites/gates anteriores permanecem, com overhead explícito da ferramenta.

Rodada final: **282 testes em 93,628 s**, exemplos e todos os alvos locais
passaram. O stress novo tem 10 casos/5.120 scans e oráculos separados. Stress
total: 94.036; públicos: 18.176; **112.212 scans na rodada**, sem somar reruns,
etapas de comparação ou os ensaios adicionais do revisor.

Três casos novos exercitam IL autêntico isolado de parênteses, stack e STN;
este último usa configuração TOF explícita original com harness construído.
Os gráficos dos timers 35/36 de outro original conferem com a nova validação;
seus defaults de tipo/base incompletos continuam sem runtime presumido.
O manifesto promove somente resultados observados e mantém os erros restantes.
Nenhuma CPU/arquivo original foi reescrita; nenhum projeto original inteiro
foi apresentado como importado.

A revisão reproduziu leitura adiantada em comparação inativa, erros internos
para instrução vazia/tab/bloco desconhecido e seleção incompleta de normalização.
Todos receberam RED/GREEN. A rechecagem passou 17 testes, 7.440 scans aleatórios
e laço em C++/recompilação/XML, sem achados abertos. O conflito documental
MPS 11/32, demais operadores, perfis e execução oficial continuam pendentes.

Relatórios: `NATIVE-LOGIC-LOCAL-RESULTS.json` e `NATIVE-LOGIC-STRESS-RESULTS.json`;
contrato: `../capabilities/NATIVE-LOGIC.md`. Os oito relatórios atuais conferem
com os hashes do código. Objetivo integral ativo/incompleto; testes locais,
sem CI, publicação, transferência ou atuação de PLC.

O objetivo integral continua ativo; Task2 do plano de indexação ainda está
pendente e não foi substituída pela API de words explícitos.

## Continuação do objetivo: bits de words, grupos e portas digitais

Após `d8b3e5a`, MW:X0..15 e grupos contíguos M/I0/Q0 têm APIs tipadas 16/32,
IL/VM, SDK, reversão e XML experimental. Escritas preservam vizinhos e aliases
MW/MD/MF; leituras menores preenchem os bits altos com zero. A cópia explícita
captura snapshot antes da escrita, inclusive com sobreposição. Q usa a imagem
de saída existente e enxerga escritas anteriores do mesmo scan. Regiões M
inteiras ficam reservadas, inclusive no limite de indexação e na normalização.

Rodada final local: **296 testes em 102,631 s**, exemplos, stress, ensaios públicos,
lint, formatação e diff passaram. O stress de bits tem 67 casos/17.152 scans,
incluindo todos os 16 bits, comprimentos 1..32, variação independente no byte
alto de 32 bits, aliases e dois trechos públicos com hashes conferidos. Um é
o rung1 inteiro de `flow-original-loop.smbp`; outro é somente o segmento
contíguo [2:8] do rung9 de D/`INDEXED-SOURCES.json`. A exclusão de MULTIFB/Timer
desse segundo caso é explícita. Nenhum original/CPU foi alterado ou importado
integralmente.

A pedido do usuário, foi acrescentada uma matriz explícita das 24 entradas e 16
saídas: 48 casos cobrem todas as 768 ligações entrada/saída/polaridade, com walking
ones/zeros. Outro caso confere retenção, condições, inversão, leitura após
escrita e encaminhamento packed no mesmo scan. São 49 casos/12.800 scans,
confrontados com referência independente, C++, IL, JSON, normalização,
reversão/recompilação e XML sintético. Rodou por `make digital-io-stress` depois
de adicionado durante `make stress`; versões futuras do alvo `stress` já o incluem.
Isso cobre a imagem lógica, sem validar eletrônica, filtros, fallback ou partida.

O stress total nesta rodada foi 123.988 scans e os ensaios públicos 18.176:
**142.164 scans**, sem somar reruns, frames dos testes unitários, etapas de
comparação ou ensaios extras do revisor. Os testes de Modbus e os demais
recursos existentes foram repetidos na suíte/rodada integral.

A revisão encontrou limite 513 em vez de 544 para M512:32, causando S20 indevido
em M543. O teste reproduziu a falha antes da correção e passou depois na VM,
SDK e recompilação. Rechecagem independente e 70 programas aleatórios não
deixaram achados importantes/críticos abertos. A matriz de portas recebeu
revisão própria e 32 frames adicionais, também sem falhas; estes não foram
adicionados ao total. Ver `BIT-OBJECT-REVIEW.md`.

Resultados e hashes: `BIT-OBJECT-LOCAL-RESULTS.json`, `BIT-OBJECT-STRESS-RESULTS.json`
e `DIGITAL-IO-STRESS-RESULTS.json`. As recusas de outros bancos, cópias nativas
sobrepostas/desiguais e perfis ainda não comprovados permanecem explícitas.
O catálogo não foi promovido a completo. Contatos de borda nativos têm pesquisa
adicional em `../capabilities/NATIVE-EDGES-RESEARCH.md`, incluindo um conflito
entre a restrição documental e RISING após AND em originais; continuam pendentes.
Objetivo integral ativo/incompleto, editor e PLC pendentes. Tudo local, sem CI,
publicação ou transferência/atuação no PLC.

## Continuação do objetivo: contatos de borda nativos

Após `292f5a2`, LDR/LDF, ANDR/ANDF, ORR/ORF e XORR/XORF têm suporte em
I0/M diretos, com quatro APIs bool, IL/VM, SDK, reversão e XML experimental.
Eventos são amostrados por endereço antes do CFG, independentemente de
contatos pulados ou repetidos. M alterado no scan aparece no seguinte;
pulsos internos entre amostragens não aparecem. Históricos locais começam
false; a fase de entradas/partida/retomada ainda exige prova externa.

O frontend reserva M explícito e emite snapshots de LDR/LDF. A normalização
preserva o endereço, a ordem e labels, materializando combinações complexas
com contatos e gates existentes. Timer com entrada de borda é normalizado.
Os tokens de gráfico RisingEdge/FallingEdge são observados nos originais,
sem alegar aceitação de um projeto inteiro ou validação oficial.

Rodada final: **306 testes em 104,272 s**; exemplos, públicos, lint/formatação
e diff passaram. Os dez scripts de stress foram executados localmente com
quatro workers, logs/statuses/resultados separados, todos com saída zero.
O stress novo tem **74 casos/20.736 scans**, todos os **24 endereços I0 e
1.024 M**, referência temporal independente e C++/IL/JSON/normalização/
reversão/recompilação/XML. A matriz digital de 768 ligações e os testes de
Modbus/recursos anteriores passaram novamente.

Três casos novos usam bytes autênticos isolados: rung2 inteiro de flow-loop,
trecho contíguo [1:3] LDR/ORF de flow-jump com sua atribuição IW explicitamente
excluída, e rung6 inteiro da fonte T de INDEXED-SOURCES com harness M/Q/MD
explícito. Hashes são conferidos antes da extração; nenhum CPU/arquivo
original foi alterado. O gráfico paralelo original de T6 não foi validado;
nenhum projeto estrangeiro inteiro foi importado.

Total final: **144.724 scans de stress +18.176 públicos =162.900**, sem somar
reruns, frames unitários ou etapas de comparação. Os 45.600 scans adicionais
do revisor também ficam fora desse total. A revisão não deixou achados de
correção abertos e conferiu programas aleatórios e com saltos. Antes dela,
colisão de helper homônimo foi reproduzida e corrigida em RED/GREEN. Um teste
antigo do alocador usava LDR como opcode desconhecido; passou a usar RISING0,
mantendo a rejeição de efeitos ainda não modelados após LDR ser implementado.

Resultados e hashes: `NATIVE-EDGE-LOCAL-RESULTS.json` e
`NATIVE-EDGE-STRESS-RESULTS.json`; revisão: `NATIVE-EDGE-REVIEW.md`.
As classes de borda no ponto da chamada continuam distintas desses contatos.
RISINGn/FALLINGn, modificadores de parênteses, ciclo de vida e demais recursos
permanecem lacunas, sem reduzir a meta de equivalência integral. Editor e PLC
físico pendentes; biblioteca incompleta e objetivo ativo. Tudo local, sem CI,
publicação ou transferência/atuação no PLC.


## Continuação do objetivo: bordas de expressão e capacidade no caminho inverso

Após `e7c40fd`, RISINGn/FALLINGn têm gramática fechada, IDs0..254 separados
por tipo, API bool `plc::rising/falling(id,value)`, VM/SDK, reversão e expansão
em Ladder básico. O histórico avança em cada execução, inclusive entrada
false; skip preserva o último valor avaliado. Condições, &&/||, aninhamento,
laços, grupos e entradas de Timer têm testes. Histórico inicial false e
repetição no mesmo scan são políticas locais ainda sem prova externa.

O backend reserva M persistente e captura a entrada antes de escrever saída
ou histórico. Não emite raw RisingEdgeBlock/FallingEdgeBlock nem presume o
mapeamento interno do nível funcional. O relatório de compilação diferencia
recursos do IR dos recursos do arquivo efetivamente gerado; overhead de
expansão é limitação da ferramenta, sem reduzir a meta integral.

O teste que observa todos os resultados das 255 funções de cada tipo revelou
estouro do budget na recompilação/reexportação. O teste foi mantido e passou
após preservar rungs já canônicos e fundir cópias privadas antes da alocação.
A fusão considera owners/aliases e vida no CFG, incluindo saltos para trás e
vida entre scans; mantém ordem de leituras com efeitos, labels e limites de
colunas. Os budgets de construção100.000 e emissão10.000 são da ferramenta,
sem demonstrar capacidade física ou tempo de scan. Contratos detalhados:
`../capabilities/EXPRESSION-EDGES.md` e `../capabilities/COPY-FUSION.md`.

Rodada final: **331 testes em 117,791 s**, exemplos, ensaios públicos, lint,
formatação e diff passaram. Os onze scripts da receita stress foram rodados
localmente, com quatro workers e logs/statuses separados; o alvo `make stress`
não foi invocado. O stress novo tem **12 casos/6.144 scans**, incluindo todas
as 510 identidades, oracle independente de chamadas e C++ do arquivo XML
realmente exportado recompilado e exportado novamente. Os originais autênticos
T10/15/20 são rungs inteiros isolados, com hash conferido e harness de Q/S6/MD
explícito; gráfico raw e projeto estrangeiro inteiro não são declarados aceitos.
Um erro no harness T20 foi corrigido para Q0.11 após ler o original; não houve
alteração de bytes de nenhum original.

A matriz das **24 entradas x16 saídas x2 polaridades =768 ligações** passou de
novo: 49 casos/12.800 scans, incluindo walking ones/zeros, retenção, condições,
inversão, leitura após escrita e transferência packed no mesmo ciclo. Os testes
de Modbus e demais recursos existentes passaram novamente. Isso comprova a
imagem lógica local; eletrônica, filtros, fallback e ciclo de vida físicos
continuam pendentes.

Total final: **150.868 scans de stress +18.176 públicos =169.044**, sem somar
reruns, frames unitários, etapas de comparação ou os 28.000 scans extras dos
revisores. A revisão de bordas encontrou LDN de comparação e whitespace na
exportação, ambos com regressões RED/GREEN corrigidas. A revisão da fusão não
relatou achados importantes/críticos; depois dela foi acrescentada uma regressão
de largura de colunas no IR do Lowerer, também RED/GREEN. Ver
`EXPRESSION-EDGE-REVIEW.md`.

Resultados e hashes atuais: `EXPRESSION-EDGE-LOCAL-RESULTS.json`,
`EXPRESSION-EDGE-STRESS-RESULTS.json` e os dez relatórios de stress/públicos
referenciados no primeiro. Os relatórios locais das etapas anteriores são
históricos; o código e cada relatório atual foram conferidos por hash. Editor,
perfil exato e PLC pendentes. Biblioteca incompleta e objetivo integral ativo;
contadores, demais flags/objetos/periféricos, tarefas e outras lacunas da tabela
continuam trabalho aberto. Tudo local, sem CI, publicação ou transmissão/atuação
no PLC.


## Continuação do objetivo: contadores comuns nativos %C

Após `0440b9f`, a API `Counter{id,preset}` oferece R/S/CU/CD por métodos,
update serializado R/S/CU/CD, P/V/E/D/F e escrita de P. Identidade/configuração
seguem no IR/JSON, VM/SDK, C++ reconstruído e Counter nativo no projeto.
Chamadas podem ser condicionais, repetidas e intercaladas com leituras no mesmo
scan. Estado do contador não é emulado com M/MW. O normalizador preserva a
ordem e usa rungs separados para ações e ligações de saída complexas.

**A semântica física de %C ainda não está fechada.** O modelo local segue a
tabela G122 para E no retorno down0->9999, em conflito com G120/G123 que o
situam na chegada a0. Consumo de bordas sob R/S, níveis retidos, repetição,
interação de direções, flags e ciclo de vida também continuam políticas locais
explicitadas em `../capabilities/COUNTERS.md`. O oracle testa essa hipótese;
concordância entre implementações não resolve a contradição do manual.

Configuração Counter e entradas independentes possuem layout nativo; o gráfico
completo de entradas do original C foi verificado diretamente. Os gráficos raw
B/M com fan-out/prefixos compartilhados ainda não são importáveis e continuam
trabalho aberto da meta integral. Os seus rungs IL completos são usados e
normalizados/exportados; isso não é alegado como importação desses gráficos.
S tem posição derivada do desenho oficial, com aceitação externa pendente.
As flags podem ser ligadas por contatos em rungs separados.

A conferência dos bytes corrigiu uma anotação de pesquisa: C/L têm
CountersMemoryAllocation/ForcedCount1, enquanto B/M têm o container vazio.
Não foram inventados enums Automatic/Manual para essa coleção. Os cinco
arquivos originais foram novamente conferidos por tamanho/SHA256/Git blob,
sem mudar CPU ou bytes. Fixtures locais guardam as configurações e o rung C
extraídos, para os testes unitários não dependerem da rede.

Rodada final: **348 testes em123,615 s**, exemplos, públicos, lint, formatação,
capabilities e diff passaram. Os doze scripts da receita stress foram rodados
como comandos locais independentes, com quatro workers e logs/statuses
separados. O novo stress tem **45 casos/23.040 scans**: oito IDs, cinco presets,
prioridades, limites/rollover, flags, condições/loops e todos os255 contadores
juntos, cada valor contribuindo para o resultado observado. Também verifica
C++ reconstruído do XML efetivamente exportado, recompilado e exportado de novo.

São usados os rungs inteiros B2, C0 e M12, cada um com harness explícito e
configuração de contadores derivada do original. De L são usados o rung18
inteiro e o trecho contíguo[5:7] de rung15, atribuição a P e S; as partes ELSE,
numéricas e Timer desse rung15 estão explicitamente excluídas. Esse caso combina
preset em execução, CD e ANDF M0 com amostragem entre scans. Não se importou
nenhum projeto estrangeiro inteiro nem se validou o seu gráfico raw completo.

A revisão independente encontrou texto desconhecido em Counters aceito/apagado;
o teste reproduziu a falha antes da correção e passou depois, conservando o
arquivo de destino. Outro teste protege campos desconhecidos no template antes
de substituí-lo. O revisor não relatou outra divergência reproduzível; seus
300 scans extras ficam fora do total. Ver `COUNTER-REVIEW.md`.

Total final: **173.908 scans de stress +18.176 públicos =192.084**, sem somar
reruns, frames unitários, etapas de comparação ou extras do revisor. A matriz
digital de768 ligações/12.800 scans e os testes de Modbus e demais recursos
passaram novamente. Isso cobre a imagem lógica e os modelos locais, sem prova
de eletrônica ou execução em PLC.

Resultados e hashes: `COUNTER-LOCAL-RESULTS.json`, `COUNTER-STRESS-RESULTS.json`
e os doze relatórios atuais de stress/públicos referenciados pelo primeiro.
Os relatórios locais das etapas anteriores são históricos. Editor, perfil
exato e PLC físico pendentes; biblioteca incompleta e objetivo integral ativo.
FC/HSC, pulsos/movimento, flags e objetos restantes, tarefas, expansões e demais
lacunas continuam trabalho aberto. Tudo local, sem CI, publicação ou atuação
em PLC.


## Continuação do objetivo: importação de gráficos Counter ramificados

Após `ae5f840`, os gráficos originais B2 e M12 antes recusados passam pela
reconciliação de portas com o IL; C0 permanece aceito. O importador lê o rung
completo num envelope sintético declarado, conserva a configuração/identidade
e reconstrói C++ do programa real. O exportador continua regenerando rungs
básicos, sem alegar preservação exata da aparência nem aceitar o CPU estrangeiro.

O verificador une portas de fios e interpreta contatos/bobinas e os pinos do
Counter. Condições são comparadas por BDD reduzido e ordenado, sem depender de
amostragem. Captura o contato compartilhado antes de seu primeiro destino,
avança gerações de propriedades Counter entre ações e acompanha memória após
ST/S/R, inclusive aliases. Isso distingue snapshot de releitura após reset ou
escrita. Células sobrepostas, portas sem par, componentes sem fonte/destino,
recursos ausentes e texto/atributos desconhecidos falham explicitamente.

Os status BOOL de comunicação participam como leituras puras e precisam de
configuração, mesmo quando a expressão absorve sua leitura. A revisão detectou
uma regressão nesse ponto: READ_VAR.DONE era aceito no baseline, mas a nova
checagem inicialmente o recusava. A falha foi reproduzida antes da correção e
passou depois, incluindo as três famílias/quatro campos BOOL, exportação com
READ_VAR + Counter e recurso ausente absorvido. Não se simulou sucesso de I/O.
Ver `COUNTER-GRAPH-REVIEW.md`.

A exportação agora informa CountersMemoryAllocation/ForcedCount=maxID+1 para
contadores usados/configurados, incluindo identidade esparsa254 que requer
extent255 no modelo. Não foi inventado enum Allocation. A variante ForcedCount
sem enum é observada em C/L; isso não é certificação de firmware/editor.

Rodada final: **367 testes em125,698 s**, exemplos, públicos, lint, formatação,
capabilities e diff passaram. Os treze scripts da receita stress foram
executados como comandos locais: o novo stress acompanhou a suíte e os outros
doze usaram quatro workers. Os dois primeiros resultados foram mantidos após
saída zero e conferência de hashes sem mudança de código, sem rerun desnecessário.

O novo stress tem **35 casos/9.728 scans**:32 gráficos gerados de256 scans e os
três gráficos/IL originais de512 scans cada. Combina OR paralelo, ramificações,
fan-out1..8, ST/S/R, feedback de Q, propriedades Counter, linhas/colunas e IDs
esparsos, com harness explícito de inicialização/readback. Percorre importação
do gráfico real, IL/JSON/normalização, SDK, C++ reconstruído/recompilado e nova
exportação a partir do C++ do XML efetivamente emitido.

As mutações de predicados usaram tabelas completas de oito variáveis:
**37.888 avaliações**, com17 alterações equivalentes aceitas e131 diferentes
recusadas. Também foram recusadas96 mutações estruturais inválidas. Essas
avaliações/decisões não são scans e não entram no total abaixo. Os18.420 ensaios
booleanos extras do revisor também ficam fora da contagem.

Total final: **183.636 scans de stress +18.176 públicos =201.812**, sem somar
reruns, frames unitários ou etapas de comparação. A matriz digital das768
ligações/12.800 scans, os255 contadores observados em conjunto e todos os
ensaios anteriores de Modbus, bordas, temporizadores e memória passaram de novo.
Os originais foram conferidos por hash/tamanho/Git blob e permaneceram intactos.

Resultados/hashes atuais: `COUNTER-GRAPH-LOCAL-RESULTS.json`,
`COUNTER-GRAPH-STRESS-RESULTS.json` e os treze relatórios de stress/públicos
referenciados pelo primeiro; relatórios locais anteriores são históricos.
Contrato: `../capabilities/COUNTER-GRAPHS.md`. A prova é do domínio booleano
ordenado declarado; não resolve os flags físicos de %C nem seu conflito sobre E.
Comparações/indexação/efeitos numéricos raw, outras estruturas, perfil exato,
schema/editor e hardware permanecem pendentes. Biblioteca incompleta e objetivo
integral ativo. Tudo local, sem CI, publicação ou atuação em PLC.


## Flags inteiros e matriz digital ampliada — 2026-11-06

Etapa após 86af2a3. Contrato em `../capabilities/INTEGER-FLAGS.md`; revisão
independente em `INTEGER-FLAG-REVIEW.md`. Implementados S17/último bit ejetado
em SHL/SHR/ROL/ROR e S18/overflow inteiro sticky, com leitura/reset explícito,
snapshots e ordem preservados em C++, IL, SDK, JSON, normalização, reversão e
XML. Operações literais com overflow são emitidas para produzir seus flags.
SDK calcula em largura maior e copia bits, sem overflow assinado de C++.

O exemplo oficial G55 soma 23241+21853, guarda -20442 e usa S18 para selecionar
32767. Os demais resultados modulares de overflow são política local pendente
de prova física. S17 recebe0/1 conforme o bit ejetado; sucesso/cópia/comparação
não limpam S18. R é a única escrita admitida para esses flags. DIV0 e SQRT
inteiro negativo marcam S18 e interrompem o modelo, mantendo explícita a lacuna
de recuperação de resultados indeterminados. Float/SW17 ainda não implementado.

A revisão não encontrou achados acionáveis. Seus192 frames, 17.952 operações
UBSan e 24.576 vetores de oracle de shifts são evidência extra e ficam fora dos
totais de stress. Os negativos antigos de overflow-abort foram substituídos por
positivos de resultado/flag; DIV0/SQRT negativo, floats inválidos e conversões
fora da faixa conservaram os testes de recusa/erro.

Rodada final: **386 testes em 129,014 s**, exemplos, públicos, fetch/verificação
dos originais, lint, formatação, capabilities e diff passaram. Os 14 scripts da
receita stress foram executados como comandos locais independentes, com quatro
workers externos; o novo stress usou quatro processos de casos (pico de sete
workers de stress). `make stress` não foi invocado como comando único.

Novo stress: **218 casos/62.464 scans**. São 192 combinações de família/largura/
distância de shift, 13 famílias ALU, oito composições com laços/curto-circuito e
cinco exemplos/trechos nativos. Valores MIN/MAX, walking bits e amostras seeded
observam toda a largura por tabelas independentes, além de carry/erro antes e
depois de clears. Percorre C++ original/IL/JSON/normalização/SDK/reversão e C++
gerado do XML efetivamente exportado, recompilação e nova exportação.

Os trechos originais T10/T15/T20 e flow-loop 3 permanecem inteiros, com harness
explícito para inicialização, entradas, leitura de flags e resultados; hashes
são conferidos. G55 é exemplo publicado do manual, não um SMBP baixado. Nenhum
projeto estrangeiro completo foi declarado compatível ou teve CPU reescrita.

A matriz digital passou: **24 entradas ×16 saídas ×2 polaridades =768 bindings**,
49 casos / 12.800 scans, com imagem Q, escritas condicionais sucessivas, retenção
entre scans, inversão, reset e cópias agrupadas. Foi ampliada para executar
também C++ do XML efetivamente emitido e outro XML recompilado. Não é ensaio
elétrico nem cobertura dos modos especiais PWM/PTO/HSC/acesso imediato.

Total: **246.100 scans de stress +18.176 públicos =264.276**, cada frame-base
contado uma vez. Exclui reruns, frames unitários, etapas comparadas, provas BDD,
mutações e probes de revisão. Os demais ensaios de Modbus, temporizadores,
contadores, memória, bordas e controle de fluxo passaram novamente.

Resultados/hashes atuais: `INTEGER-FLAG-LOCAL-RESULTS.json`,
`INTEGER-FLAG-STRESS-RESULTS.json` e os 14 relatórios de stress/públicos
referenciados. Relatórios locais anteriores são históricos. Biblioteca completa
continua false; meta integral ativa. Perfil/firmware/schema, editor Schneider,
PLC e comportamento elétrico/temporal permanecem pendentes. Tudo local, sem CI,
push, transmissão ao PLC ou acionamento de cargas.


## Conversões BCD e de palavras — 2026-11-06

Etapa após bd5bcf3. Foram acrescentados seis intrínsecos nativos à biblioteca:
BTI/ITB word/dword (`bcd_to_int`, `bcd_to_dint`, `int_to_bcd`, `dint_to_bcd`),
CONCATW (`concat_words`) e DWORD (`int_to_dint`). A matriz pública contém agora
53 intrínsecos com respostas declaradas e conferência de cobertura exata.
Contrato/fontes em `../capabilities/CONVERSIONS.md` e `CONVERSION-SOURCES.json`.

BCD usa quatro/oito dígitos; portadores negativos com nibble alto 8/9 são válidos
sem overflow causado pelo sinal do portador. S17 e S18 anteriores são preservados
no sucesso. BCD inválido assinala S18 e interrompe o modelo antes de escrever o
destino, sem fabricar resultado. A recuperação de valores indeterminados segue
pendente. CONCATW recebe low primeiro/high depois, corroborado oficialmente.
DWORD usa extensão de sinal no modelo local; o manual não resolve os negativos,
e essa política continua exigindo teste no editor/PLC.

A revisão independente encontrou dois P2, reproduzidos e corrigidos por testes
RED→GREEN: helpers globais com nomes dos intrínsecos eram capturados como APIs;
propriedades de bloco podiam ser emitidas diretamente em DWORD/CONCATW, fora da
tabela de operandos do manual. O despacho exige plc:: e o lowering materializa
MW para essas fontes; o importador recusa a forma raw indevida. Um teste com
ReadVar/configuração serial explícita percorre SDK/VM/JSON/normalização/XML e
C++ do XML até novo XML sem tráfego. BTI/ITB com propriedades válidas permanecem
aceitos. A prova de alias foi fortalecida com fontes invertidas: resultado 65538,
enquanto uma escrita prematura daria 131074. Ver `CONVERSION-REVIEW.md`.

Rodada final: **402 testes em 182,478 s**, exemplos, públicos, originais, lint,
formatação, capabilities e diff passaram. Os 15 scripts da receita stress foram
executados como comandos independentes com quatro workers externos, além dos
quatro processos internos de integer_flags. O novo stress foi repetido após
separar a observação integral dos resultados word da observação de flags;
somente a rodada final entra nas contagens. `make stress` não foi invocado como
comando único. Nenhuma implementação mudou durante a rodada final.

Novo stress: **10 casos / 24.096 scans**. Dois casos percorrem os 10.000 valores
válidos de BTI/ITB word e observam diretamente todos os 16 bits. Os outros oito
usam tabelas independentes de largura completa, valores extremos/walking bits,
operandos trocados, widening, guardas e flags antes/depois de clears. O caminho
inclui IL/JSON/normalização, SDK, reversão/recompilação e C++ do XML efetivamente
emitido até outro XML. O rung BTI de G59 é exemplo publicado com harness,
não um projeto BCD original baixado. O corpus existente só continha DWORD
composto; nenhum suporte novo a expressões nativas compostas foi alegado.

Um harness separado do SDK, compilado com UBSan e recuperação desativada,
percorreu **65.536 vetores de widening/concat, 10.000 BCD word e 100.000.000 BCD
dword válidos**. Seu oracle incrementa dígitos packed com correção decimal,
independente da divisão/módulo usados no codec. Um valor volatile impede
propagação de constantes. O harness verifica resultados e preservação de flags;
seus 100.075.536 vetores não são scans e ficam fora do total abaixo.

Os unitários também esgotam os 65.536 portadores BTI word (exatamente 10.000
válidos), 10.000 ITB word e 65.536 valores de widening no avaliador, além de
amostras de 32 bits, cada posição de nibble inválido e limites de entrada. Esses vetores
unitários e os reruns focados igualmente não entram nos scans finais.

Total: **270.196 scans de stress +18.176 públicos =288.372**, cada frame-base
contado uma vez. Modbus, temporizadores, contadores, memória, bordas, controle
de fluxo e a matriz das 24 entradas/16 saídas digitais passaram novamente:
49 casos / 12.800 scans e 768 bindings de I/O/polaridade, sem ensaio elétrico.

Resultados/hashes atuais: `CONVERSION-LOCAL-RESULTS.json`,
`CONVERSION-STRESS-RESULTS.json` e os 15 relatórios de stress/públicos
referenciados. Relatórios locais anteriores são históricos. O índice de fontes
registra os hashes dos PDFs; as páginas web foram conferidas por busca/leitura,
mas o download direto devolveu 403/redirect inacessível, sem inventar cache ou
hash de HTML. Não houve reescrita de CPU ou modificação dos originais.

Biblioteca completa permanece false e meta integral ativa. Outros bancos,
expressões compostas, flags/recuperação completos, recursos de hardware,
configuração/perfil/schema exatos, editor e PLC ainda faltam. Tudo local, sem
CI, push, upload ou atuação em cargas.

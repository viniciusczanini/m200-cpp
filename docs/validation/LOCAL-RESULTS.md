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

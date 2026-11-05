# m200-cpp — protótipo local

A meta final é **equivalência funcional com a programação oficial do
TM200CE40T**: todo algoritmo aceito nesse perfil deve ter uma forma suportada
de expressão em C++ e gerar um projeto equivalente. As restrições atuais do
protótipo são trabalho pendente, não o escopo final da biblioteca. O contrato
completo está em [docs/PARITY.md](docs/PARITY.md).

Ferramenta experimental para escrever lógica do **Schneider TM200CE40T** em C++ restrito, gerar IL e um projeto `.smbp` a partir de um template, e reconstruir C++ a partir das instruções reais do arquivo.

**Ainda não validado no EcoStruxure Machine Expert Basic nem no CLP.** Os testes locais não comprovam que o editor abre o arquivo, nem o comportamento elétrico ou temporal no equipamento. O usuário disponibilizará Windows/software/CLP no futuro via SSH. Nenhuma instalação de Windows ou comunicação com o CLP é necessária para usar o protótipo local.

## Começar

Requisitos: Python 3.9+ e `clang++` com C++17. No Mac testado: Apple Clang 21. O projeto usa apenas a biblioteca padrão do Python. Pode definir `M200_CLANG` para selecionar outro executável.

```sh
cd /Users/tommy/Offline/projects/m200-cpp
make check
./m200c compile examples/blink.cpp -o output/blink
./m200c check examples/blink.cpp --trace examples/trace.json
```

Um clock local fica assim:

```cpp
#include <plc.hpp>

plc::Clock pisca{500};  // meio período mínimo: 500 ms

void scan() {
    bool ligado = pisca.update(true);
    plc::output(0, ligado);
}
```

`scan()` executa uma vez por ciclo. `Clock` aloca dois timers e seu estado; não bloqueia a tarefa. Começa desligado; `update(false)` zera os timers e a fase. Cada meio período inclui a resolução do timer e a latência do scan — não é uma promessa de 500 ms exatos. O modelo local começa no instante zero; essa precisão ainda precisa ser confrontada com o simulador oficial e com o CLP.

Também há `plc::clock_ms(10|100|1000|60000)`, que lê as bases globais `%S4..%S7`. Elas têm fase global no controlador, não fase reiniciável por instância; o modelo local assume fase zero apenas para reprodução dos testes.

## O que já funciona localmente

- Variáveis `bool`, inicialização, atribuição sequencial, `if/else`, `!`, `&&`, `||`, XOR booleano, `==` e `!=`.
- Funções auxiliares booleanas com um único `return` puro, sem recursão ou efeitos colaterais.
- Estado global entre scans e captura das entradas usadas. Saídas têm imagem lógica e escrita consolidada no final do ciclo. No primeiro scan de RUN, saídas e globais comuns usadas pelo programa são reinicializadas conforme o contrato.
- `plc::input(0..23)`, `plc::output(0..15, bool)` e `plc::output_state(0..15)`, com índices literais.
- `plc::Ton`, `plc::Tof`, `plc::Pulse`, `plc::Clock`, `plc::RisingEdge` e `plc::FallingEdge`. As instâncias são globais. Por enquanto há uma ocorrência estática de `update` por instância no código; habilitação é parâmetro explícito. Laços e saltos podem visitar essa ocorrência zero ou várias vezes no mesmo scan; o estado atualiza em cada visita. Chamadas em ramos que o frontend ainda traduz por predicação são recusadas. Uma instância inteiramente não utilizada é permitida, embora sua declaração possa reservar recursos.
- Alocação automática de bits e timers; os temporários também entram no orçamento. O alocador pode usar os 1.024 bits M e reutiliza células privadas quando a análise do fluxo comprova que os valores não coexistem. Globais e estado de instâncias mantêm células únicas; endereços explícitos ficam reservados. As posições a partir de 500 são preferência, sem limitar o banco à metade superior. Retenção e transições físicas continuam dependendo do perfil e da validação externa.
- Tipos `plc::i16`, `plc::i32` e `plc::f32`, 47 operações numéricas explícitas, comparações e leitura/escrita de words/dwords/REAL. `%MW`, `%MD` e `%MF` compartilham os mesmos 8.000 words, agora todos disponíveis ao alocador, descontados endereços explícitos e buffers inteiros de comunicação. MD/MF ocupam duas células; reuso leva em conta a sobreposição física entre tipos. As posições a partir de 4.000 são preferência, não reserva exclusiva.
- Executor IL com validação estrita, conversor IL/SMBP → C++ e comparação com a execução C++ nativa.
- Projeto XML baseado em template, rungs Ladder de contatos em série, bobinas, timers e blocos numéricos Operation/Comparison, verificação local de coerência IL/gráfico e arquivo de vínculo fonte/rung.

O protótipo **recusa** aritmética C++ com promoções implícitas (use as operações explícitas `plc::*`), unsigned, arrays multidimensionais, ponteiros, referências arbitrárias, classes da aplicação, exceções, threads, funções externas, headers com declarações fora do SDK e nós AST desconhecidos. Contadores nativos, retenção configurável de memória entre reinícios, expansões, tarefas de evento, acesso imediato e PTO/PWM ainda não estão implementados. Modbus tem agora um subconjunto descrito abaixo; não representa a cobertura completa de comunicação do PLC. Não existe tentativa de compilar C++ geral e ignorar as partes difíceis.

Arrays de capacidade fixa de `bool`, `plc::i16`, `plc::i32` e `plc::f32` aceitam leitura/escrita com índice literal ou calculado em execução (`bool`, `i16` ou `i32`). Arrays com índice calculado usam grupos contíguos; os elementos de32bits têm stride2 words. Arrays globais persistem entre scans e recebem inicialização no primeiro RUN; locais são inicializados quando a declaração executa, inclusive dentro de um laço. Inicializadores parciais e `{}` zeram os elementos restantes. Arrays locais sem inicialização são recusados. O caminho reverso recupera os operandos/endereço reais, sem precisar preservar a sintaxe original de array. `examples/dynamic_arrays.cpp` percorre arrays numéricos com `for`.

Literais fora da faixa falham na compilação. Para índice calculado fora da faixa, o modelo experimental usa `%S20` e o primeiro elemento como fallback, após validar o índice sem overflow. Isso é uma política da ferramenta: `[]` fora da faixa tem comportamento indefinido no C++ desktop. Os testes não executam o C++ original nesse domínio. A ordem RHS antes do lvalue e o curto-circuito são preservados por snapshots e desvios reais.

Arrays booleanos dinâmicos e a API raw `read_m_indexed`/`write_m_indexed` estão implementados em C++/IL/VM/reversão. A API raw declara imagens globais `plc::BitMemory bits{count}` e `plc::WordMemory words{count}`, usando o conteúdo do MW como offset em bits. **A exportação/importação SMBP com bits indexados permanece bloqueada:** o manual exige nível funcional10.0, mas ainda não há mapeamento comprovado desse nível para o token de projeto nem validação do perfil CE40T. `examples/dynamic_bits.cpp` serve para testes locais, sem alegar projeto oficial aceito.

A API nativa indexada de words já aceita índices calculados em execução:

```cpp
plc::WordMemory image{64}; // reserva MW0..63 como imagem explícita da aplicação
// Dentro de scan():
plc::write_word(0, 3);
plc::write_word_indexed(16, 0, 42); // endereço 16 + conteúdo de MW0 = MW19
plc::i16 value = plc::read_word_indexed(16, 0);
```

O segundo argumento é o **endereço literal do MW de índice**, não o offset em si. Existem variantes `read/write_dword_indexed` e `read/write_real_indexed`; o offset é medido em words, inclusive para objetos de32bits, que ocupam duas células. O índice original não é alterado por erro. `%S20`, lido por `plc::system(20)`, persiste até `plc::clear_index_error()`; S/ST nesse bit são recusados. Em erro, a API usa o endereço base. Guardas preservam o limite lógico de `WordMemory` mesmo que os temporários ocupem endereços mais altos. A imagem inteira fica reservada, além de buffers de comunicação. `examples/indexed_words.cpp` percorre uma tabela com `for`.

O modelo local usa maior referência direta para a indexação nativa e verifica ambas as células de MD/MF. Relação com sobrealocação Manual, default XML e símbolos isolados permanece sem prova externa: esses perfis são recusados na importação indexada. A emissão Operation/Comparison é experimental, baseada na sintaxe documentada; não foi encontrado original gráfico indexado nesta pesquisa. Perfil/word-offset32/fronteiras/flags precisam do editor e PLC. Grupos contíguos preservam os elementos vivos durante escritas parciais e não invadem imagens explícitas/buffers; a alocação conservadora e o overhead ainda podem recusar um programa que caiba numa implementação nativa menor. Esta etapa não conclui a cobertura integral.

AND/OR nativo com comparação indexada também é recusado enquanto a ordem de resolução/erro do contato não estiver comprovada. O C++ com `&&/||` continua suportado: o compilador captura o lado esquerdo e emite snapshot/desvio antes de acessar o endereço, preservando o curto-circuito definido pela linguagem.

`while`, `for`, `do/while`, `break`, `continue`, labels e `goto` usam saltos nativos e executam no mesmo scan. Em `for`, use tipos `plc::*` e incremento explícito, por exemplo `i=plc::add_i16(i,1)`; operadores C++ de incremento/promoção ainda não foram ampliados. O caminho inverso reconstrói labels e `goto` a partir da IL real. São contabilizados os 64 labels nativos, incluindo os gerados pelo compilador. A VM tem limite local de execução, configurável por `Machine(..., instruction_limit=...)`: excedê-lo gera erro, sem encerrar o laço com sucesso nem simular o watchdog físico. O XML emitido usa a forma `Jump/JMPC` observada em original; gráficos diretos de `JMP/JMPCN` permanecem sem comprovação. O exemplo `examples/loops.cpp` exercita essa linguagem.

`read_m`, `write_m` e `system` são primitivas de auditoria usadas no C++ reconstruído. `system` aceita somente as quatro bases de clock e o primeiro scan `%S13`. O significado da região retida e de estados iniciais de projetos externos precisa ser confrontado com sua configuração; não há simulação de falta de energia/retomada física.

`Ton`, `Tof` e `Pulse` também expõem `preset()` (%TM.P), `value()` (%TM.V),
`done()` (%TM.Q) e `set_preset(i16)`. O construtor explícito
`plc::Ton t{42,100,3}` fixa TM42, base100ms e preset3ticks; a reversão conserva
esses três parâmetros. A escrita P usa o objeto nativo, sem variável sombra.
V/Q são somente leitura. Com `IsDynamicPreset=false`, o novo P só afeta a
próxima ativação, mesmo sendo lido imediatamente. Saltar o bloco deixa seu
estado interno progredir, mas não reescreve a saída ligada ao bloco. A fase
real dos ticks e o ciclo de vida precisam de validação externa. A base10ms continua
bloqueada no XML por falta de serialização comprovada. Exemplo:
`examples/timer_properties.cpp`; contratos: `docs/capabilities/TIMER-PROPERTIES.md`.

O construtor de 5 argumentos `Ton/Tof/Pulse{index,base,preset,retentive,dynamic_preset}`
aceita flags bool literais. TON/TOF retentivos pausam e retomam V antes da
conclusão; TP retentivo é recusado. Dynamic Preset permite alterar P enquanto
roda, considerando-o na próxima atualização da base. Reduzir P abaixo de V
conclui mantendo V. Com as duas opções, P menor que V enquanto pausado zera V.
São modos implementados em C++/IL/configuração/VM/SDK/reversão, com os flags
preservados no JSON. **SMBP com qualquer opção true continua bloqueado** até
comprovar o mapeamento de nível funcional 3.3/12.0. Fase/fração dos ticks e
fronteiras após conclusão permanecem políticas locais pendentes de ensaio.
Exemplo `examples/timer_modes.cpp`; contrato `docs/capabilities/TIMER-MODES.md`.

Bits individuais de MW são acessados com `read_word_bit(word,bit)` e
`write_word_bit(word,bit,bool)`, preservando os outros bits e os aliases MD/MF.
As APIs `read_m/input/output_bits_i16/i32` e `write_m/output_bits_i16/i32`
transferem grupos contíguos com início múltiplo de8, comprimento1–32 limitado
ao portador/banco e bit inicial no LSB. Leituras preenchem os bits altos com
zero; escritas preservam vizinhos. `copy_m_bits(dest,source,count)` captura
o grupo antes de escrever e admite sobreposição. Leituras de Q enxergam as
escritas anteriores do mesmo scan. Exemplo `examples/bit_objects.cpp`;
escopo e restrições: `docs/capabilities/BIT-OBJECTS.md`.

Os contatos nativos LDR/LDF, ANDR/ANDF, ORR/ORF e XORR/XORF estão disponíveis
na IL e reversão. Em C++, `input_rising/falling(index)` e `m_rising/falling(index)`
retornam a borda amostrada no começo do ciclo. Leituras repetidas não consomem
o evento e saltos não acumulam bordas antigas. Uma escrita em M no programa
aparece na detecção do próximo ciclo; um pulso que sobe e desce dentro do ciclo
não aparece. As classes RisingEdge/FallingEdge continuam detectores no ponto
da chamada. Fase das entradas, partida/retomada e aceitação oficial aguardam
validação externa. Exemplo `examples/native_edges.cpp`; contrato
`docs/capabilities/NATIVE-EDGE-CONTACTS.md`.

## Números e inventário completo de pesquisa

```cpp
#include <plc.hpp>
plc::i16 count = 0;
void scan() {
    count = plc::add_i16(count, 1);
    if (count >= 50) { count = 0; }
    plc::f32 fraction = plc::div_f32(plc::int_to_real(count), 50.0f);
    plc::write_word(0, count);
    plc::write_real(2, fraction);
    plc::output(0, fraction >= 0.5f);
}
```

Use `plc::add_i16(a,b)`, `add_i32` ou `add_f32` para escolher a operação e sua largura. Os operadores C++ `+ - * /` para valores de aplicação são recusados. As operações aceitas incluem aritmética, REM, lógica word, shifts/rotações, raiz, funções REAL e conversões explícitas. A lista consultável está em `./m200c capabilities`; há um exemplo em `examples/numeric_control.cpp`. As comparações `== != < <= > >=` exigem tipos compatíveis. Literais REAL usam o sufixo `f`; inicializadores numéricos usam `plc::i16/i32/f32`.

O compilador recusa literais fora da faixa, endereços impossíveis, shifts inválidos e operações obviamente inválidas com argumentos literais. Para erros que dependem de valores em execução, como overflow ou divisão por zero, a simulação local interrompe com erro e o SDK nativo recusa o mesmo domínio. Isso **não implementa ainda** os flags físicos `%S17/%S18/%SW17`, a recuperação de erros aritméticos ou uma garantia de scan/watchdog. Não se deve interpretar o modelo local de erro como prova de que o PLC irá parar ou proteger saídas. `DWORD`, `CONCATW`, EXPT e conversões DEG/RAD continuam recusados até resolver a semântica/evidência necessária.

As expressões respeitam `if/else` e curto-circuito `&&/||`. O caminho inverso preserva endereços e operações. O C++ de auditoria pode compilar nativamente mesmo quando sua **recompilação para PLC** excede o orçamento de instruções ou a memória. A segunda tradução ainda pode introduzir overhead; a análise conservadora de vida e a coloração não provam que inexiste uma implementação nativa menor. Essa otimização continua no objetivo. Células reutilizadas têm símbolos `compiler_reused_*`; eles não representam várias variáveis persistentes independentes. O relatório registra contagens virtuais/físicas e reservas em `metadata.allocation`.

O inventário reúne **250 registros documentais** (161 de linguagem/blocos e 89 de hardware/configuração), incluindo 13 conflitos entre fontes, com páginas, limites e hashes dos documentos. Ele inclui recursos nativos, opcionais, ausentes e com suporte ainda desconhecido: não significa 250 recursos implementados. Os estados de pesquisa começam em `missing/pending` até receber evidência específica de implementação por fase; a seção `library` da CLI lista o subconjunto local atual. A biblioteca **ainda não está completa**. O trabalho restante está registrado em [docs/capabilities/README.md](docs/capabilities/README.md).

```sh
./m200c capabilities
./m200c capabilities HW.HSC
./m200c capabilities --all
make stress
make public-fetch   # download explícito dos originais fixados
make public-check   # teste local dos originais, sem download implícito
```

`make stress` cria relatórios e fontes de reprodução em um diretório temporário novo fora do repositório. Executa apenas testes locais e falha diante de divergências inesperadas. `make check` inclui a matriz de 47 intrínsecos numéricos e suas referências independentes.

## Modbus no TM200CE40T

```cpp
#include <plc.hpp>
plc::ReadVar remote{plc::Link::Ethernet, 1, 100,
                    plc::Object::HoldingWords, 0, 2, 100};
void scan() {
    bool done = remote.update(plc::input(0), false);
    plc::output(0, done);
    plc::output(1, remote.busy());
    plc::output(2, remote.error());
    if (done) { plc::output(3, plc::read_word(100) > 0); }
}
```

O exemplo lê dois registradores remotos desde o endereço zero para `%MW100..101`. O índice Ethernet `1` deve estar configurado no template do **TM200CE40T**. Os construtores `ReadVar`, `WriteVar` e `WriteReadVar` produzem blocos nativos de comunicação; getters expõem Done/Busy/Aborted/Error e os códigos de erro. O buffer inteiro é validado e reservado antes de alocar temporários. Índices explícitos preservam a identidade dos blocos na conversão de volta.

A implementação local inclui os function codes 1/2/3/4/5/6/15/16/23, packing de bits, MBAP, erros, timeout, aborto e exclusão por porta. A simulação usa somente um transporte fornecido explicitamente. Sem transporte, uma tentativa retorna erro de canal não configurado; não existe sucesso simulado automático.

A exportação `.smbp` cobre os perfis de READ_VAR/WRITE_VAR com enums e configuração comprovados em arquivos originais. Exige SL1 RS485/RTU/master explícita ou remoto Ethernet existente. Variantes de XML ainda desconhecidas — incluindo WRITE_READ_VAR, bits/single-coil, certos parâmetros de porta e a ligação gráfica ABORT — são recusadas na exportação. O suporte de protocolo/IL dessas operações não equivale a suporte de XML completo. Editor oficial, porta serial física e PLC continuam pendentes.

Detalhes e limites: [docs/MODBUS.md](docs/MODBUS.md). Ensaios públicos: [docs/validation/PUBLIC-PROJECTS.md](docs/validation/PUBLIC-PROJECTS.md).

## Gerar o projeto que será testado no editor

O caminho inverso também entende STN/N, MPS/MRD/MPP, grupos AND(/OR( com `)`,
timers com entrada composta e saídas ST/STN/S/R, e `IN %TMn` terminal ou antes
de outra carga. Valores salvos são snapshots, preservando a ordem das escritas.
Na exportação, a lógica complexa é traduzida para rungs simples usando os
elementos Ladder já conhecidos; o programa de entrada permanece intacto.
Comparações em curto-circuito usam saltos para evitar leituras indevidas.
O conflito documental de profundidade MPS 11/32, efeitos de IN observados por
ações posteriores e demais modificadores ainda têm lacunas explícitas.
Detalhes e ensaios: `docs/capabilities/NATIVE-LOGIC.md`. Isso amplia a cobertura
local; a aceitação dos arquivos pelo editor oficial continua pendente.

No Machine Expert Basic, criar e salvar um projeto **TM200CE40T** e trazer o arquivo para o Mac. Não basta trocar a referência de um projeto M221 ou de outro M200.

```sh
./m200c compile examples/blink.cpp \
  --template /caminho/template-real-tm200ce40t.smbp \
  -o output/blink-para-windows
```

O compilador mantém a configuração de hardware do template e substitui o programa e suas alocações. Templates com objetos/tarefas ativos desconhecidos são recusados. O arquivo original não é alterado. A saída contém:

- `program.smbp`, quando um template foi fornecido;
- `program.il` e `program.m200.json`, com as instruções reais;
- `program.audit.cpp`, reconstruído da IL, sem recuperar uma cópia do fonte original;
- `source-map.json`, com nomes de memória e a relação entre origem C++ e rungs;
- `report.json`, com recursos, hashes, versões e validações ainda pendentes.

`tests/fixtures/synthetic.smbp` é exclusivamente uma fixture de parser. Ela permite exercitar a serialização aqui, mas **não é um perfil oficial nem um projeto pronto para carregar no CLP**. Não há um template autêntico do TM200CE40T incluído.

O perfil de leitura é conservador: até um template real vazio pode exigir ajuste de defaults quando tivermos o editor. Configurações desconhecidas, XML ambíguo com campos duplicados e atributos de execução não reconhecidos são recusados.

Uma restrição adicional do backend atual: a enumeração XML da base de timer de **10 ms** ainda não foi estabelecida por um exemplo inspecionado. A IL/modelo local pode usar essa base, mas a exportação `.smbp` a recusa. As outras bases também continuam sem validação no editor. Timers de 1 ms só podem ocupar `%TM0..%TM5`; um `Clock` consome dois timers. Configurações não representáveis ou recursos esgotados geram erro.

## Converter de volta e conferir

```sh
./m200c decompile output/blink-para-windows/program.smbp -o output/conferir.cpp
./m200c inspect output/blink-para-windows/program.smbp
./m200c simulate output/blink/program.m200.json --trace examples/trace.json
```

O conversor lê a IL e os timers efetivamente presentes no arquivo. O resultado é C++ válido para auditoria, com endereços explícitos e ordem de execução preservada. Nomes e estrutura exatos do C++ original não são recuperáveis em geral. Uma cópia do projeto acompanha a saída com o sufixo `.configuration.smbp`, preservando as informações que não pertencem ao código.

Arquivos externos só são aceitos dentro do subconjunto reconhecido: instruções booleanas, operações/comparações numéricas reconhecidas, blocos de timer específicos, seções em ordem e gráficos simples coerentes. Paralelos, grafcet, saltos, tarefas adicionais, bases/modos desconhecidos e divergências entre IL e gráfico geram erro. Um arquivo arbitrário do editor pode ser recusado; ainda não há descompilador geral de SMBP.

A descompilação recusa caminhos existentes ou que coincidam com o projeto de entrada, inclusive aliases por symlink e o caminho da cópia de configuração. Escolha um nome novo para cada conferência.

`check` compara a execução nativa do C++ original, a IL e o C++ reconstruído para a mesma sequência de entradas/tempo. Isso ajuda a detectar erros de ordem e conversão. A conferência de volta e o executor próprio compartilham partes do modelo e não substituem o simulador oficial. O comando `certify` sempre recusa declarar compatibilidade enquanto a validação oficial estiver pendente.

As saídas são preparadas antes de substituir artefatos de uma compilação anterior. Arquivos gerados que tenham sido editados, ou arquivos desconhecidos no diretório, impedem a sobrescrita. Escolha outro diretório para preservar uma edição manual.

## Próximo passo com Windows

O roteiro está em [docs/validation/WINDOWS.md](docs/validation/WINDOWS.md). SSH permitirá transferir arquivos, consultar versões e colher evidências; a abertura, compilação e inspeção do editor poderão exigir sessão gráfica interativa. Isso ainda precisa ser confirmado na máquina que será disponibilizada.

A ferramenta nova da Apple pesquisada foi **Container machines**, um ambiente Linux persistente. Ela pode ajudar em testes Linux, mas não fornece o Windows do editor Schneider. O compilador já executa nativamente no Mac; nenhuma VM é dependência deste protótipo.

Fontes técnicas e limites da pesquisa: [docs/FORMAT.md](docs/FORMAT.md). Todos os testes são locais; não há CI ou publicação remota configurada.

Resultados, revisão e decisões: [docs/validation/LOCAL-RESULTS.md](docs/validation/LOCAL-RESULTS.md).

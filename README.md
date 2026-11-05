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
- `plc::Ton`, `plc::Tof`, `plc::Pulse`, `plc::Clock`, `plc::RisingEdge` e `plc::FallingEdge`. As instâncias são globais. Cada instância utilizada deve receber uma atualização incondicional por scan; habilitação é parâmetro explícito. Chamadas duplicadas ou condicionais são recusadas. Uma instância inteiramente não utilizada é permitida, embora sua declaração possa reservar recursos.
- Alocação automática de bits e timers; os temporários também entram no orçamento. O alocador comum usa `%M500..1023`, evitando retenção automática acidental da faixa baixa. O uso explícito de endereços pelo código de auditoria reserva esses endereços e pode reduzir o espaço disponível.
- Tipos `plc::i16`, `plc::i32` e `plc::f32`, 47 operações numéricas explícitas, comparações e leitura/escrita de words/dwords/REAL. `%MW`, `%MD` e `%MF` compartilham os mesmos 8.000 words; temporários numéricos usam a faixa a partir de 4.000 e reservam os endereços usados explicitamente.
- Executor IL com validação estrita, conversor IL/SMBP → C++ e comparação com a execução C++ nativa.
- Projeto XML baseado em template, rungs Ladder de contatos em série, bobinas, timers e blocos numéricos Operation/Comparison, verificação local de coerência IL/gráfico e arquivo de vínculo fonte/rung.

O protótipo **recusa** aritmética C++ com promoções implícitas (use as operações explícitas `plc::*`), unsigned, arrays multidimensionais ou com índice dinâmico, ponteiros, referências arbitrárias, classes da aplicação, loops, exceções, threads, funções externas, headers com declarações fora do SDK e nós AST desconhecidos. Contadores nativos, retenção declarada, expansões, tarefas de evento, acesso imediato e PTO/PWM ainda não estão implementados. Modbus tem agora um subconjunto descrito abaixo; não representa a cobertura completa de comunicação do PLC. Não existe tentativa de compilar C++ geral e ignorar as partes difíceis.

Arrays de capacidade fixa de `bool`, `plc::i16`, `plc::i32` e `plc::f32` aceitam leitura/escrita com índice literal. Arrays globais persistem entre scans e recebem inicialização no primeiro RUN; locais são inicializados quando a declaração executa. Inicializadores parciais e `{}` zeram os elementos restantes. Arrays locais sem inicialização são recusados. O caminho reverso recupera os operandos/endereço reais, sem precisar preservar a sintaxe original de array. Indexação dinâmica e outras formas continuam no objetivo de equivalência.

`read_m`, `write_m` e `system` são primitivas de auditoria usadas no C++ reconstruído. `system` aceita somente as quatro bases de clock e o primeiro scan `%S13`. O significado da região retida e de estados iniciais de projetos externos precisa ser confrontado com sua configuração; não há simulação de falta de energia/retomada física.

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

As expressões respeitam `if/else` e curto-circuito `&&/||`. O caminho inverso preserva endereços e operações. O C++ de auditoria pode compilar nativamente mesmo quando sua **recompilação para PLC** excede a memória, porque essa segunda tradução requer temporários adicionais; isso é uma limitação explícita.

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

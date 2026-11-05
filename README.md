# m200-cpp — protótipo local

Ferramenta experimental para escrever lógica digital do **Schneider TM200CE40T** em C++ restrito, gerar IL e um projeto `.smbp` a partir de um template, e reconstruir C++ a partir das instruções reais do arquivo.

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
- `plc::Ton`, `plc::Tof`, `plc::Pulse`, `plc::Clock`, `plc::RisingEdge` e `plc::FallingEdge`. As instâncias são globais. Cada instância deve receber uma atualização incondicional por scan; habilitação é parâmetro explícito. Chamadas duplicadas ou condicionais são recusadas.
- Alocação automática de bits e timers; os temporários também entram no orçamento. O alocador comum usa `%M500..1023`, evitando retenção automática acidental da faixa baixa. O uso explícito de endereços pelo código de auditoria reserva esses endereços e pode reduzir o espaço disponível.
- Executor IL com validação estrita, conversor IL/SMBP → C++ e comparação com a execução C++ nativa.
- Projeto XML baseado em template, rungs Ladder de contatos em série, bobinas e timers, verificação local de coerência IL/gráfico e arquivo de vínculo fonte/rung.

O protótipo **recusa** inteiros da aplicação e aritmética, arrays, ponteiros, referências arbitrárias, classes da aplicação, loops, exceções, threads, funções externas, headers com declarações fora do SDK e nós AST desconhecidos. Recursos como Modbus, contadores nativos, retenção declarada, expansões, tarefas de evento, acesso imediato e PTO/PWM ainda não estão implementados. Não existe tentativa de compilar C++ geral e ignorar as partes difíceis.

`read_m`, `write_m` e `system` são primitivas de auditoria usadas no C++ reconstruído. `system` aceita somente as quatro bases de clock e o primeiro scan `%S13`. O significado da região retida e de estados iniciais de projetos externos precisa ser confrontado com sua configuração; não há simulação de falta de energia/retomada física.

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

Uma restrição adicional do backend atual: a enumeração XML da base de timer de **10 ms** ainda não foi estabelecida por um exemplo inspecionado. A IL/modelo local pode usar essa base, mas a exportação `.smbp` a recusa. As outras bases também continuam sem validação no editor. Timers de 1 ms só podem ocupar `%TM0..%TM5`; um `Clock` consome dois timers. Configurações não representáveis ou recursos esgotados geram erro.

## Converter de volta e conferir

```sh
./m200c decompile output/blink-para-windows/program.smbp -o output/conferir.cpp
./m200c inspect output/blink-para-windows/program.smbp
./m200c simulate output/blink/program.m200.json --trace examples/trace.json
```

O conversor lê a IL e os timers efetivamente presentes no arquivo. O resultado é C++ válido para auditoria, com endereços explícitos e ordem de execução preservada. Nomes e estrutura exatos do C++ original não são recuperáveis em geral. Uma cópia do projeto acompanha a saída com o sufixo `.configuration.smbp`, preservando as informações que não pertencem ao código.

Arquivos externos só são aceitos dentro do subconjunto reconhecido: instruções booleanas, blocos de timer específicos, seções em ordem e gráficos simples coerentes. Paralelos, grafcet, saltos, tarefas adicionais, bases/modos desconhecidos e divergências entre IL e gráfico geram erro. Um arquivo arbitrário do editor pode ser recusado; ainda não há descompilador geral de SMBP.

`check` compara a execução nativa do C++ original, a IL e o C++ reconstruído para a mesma sequência de entradas/tempo. Isso ajuda a detectar erros de ordem e conversão. A conferência de volta e o executor próprio compartilham partes do modelo e não substituem o simulador oficial. O comando `certify` sempre recusa declarar compatibilidade enquanto a validação oficial estiver pendente.

As saídas são preparadas antes de substituir artefatos de uma compilação anterior. Arquivos gerados que tenham sido editados, ou arquivos desconhecidos no diretório, impedem a sobrescrita. Escolha outro diretório para preservar uma edição manual.

## Próximo passo com Windows

O roteiro está em [docs/validation/WINDOWS.md](docs/validation/WINDOWS.md). SSH permitirá transferir arquivos, consultar versões e colher evidências; a abertura, compilação e inspeção do editor poderão exigir sessão gráfica interativa. Isso ainda precisa ser confirmado na máquina que será disponibilizada.

A ferramenta nova da Apple pesquisada foi **Container machines**, um ambiente Linux persistente. Ela pode ajudar em testes Linux, mas não fornece o Windows do editor Schneider. O compilador já executa nativamente no Mac; nenhuma VM é dependência deste protótipo.

Fontes técnicas e limites da pesquisa: [docs/FORMAT.md](docs/FORMAT.md). Todos os testes são locais; não há CI ou publicação remota configurada.

# Memória indexada e arrays dinâmicos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, TDD e revisão independente.

**Goal:** expressar em C++ acessos indexados em execução e arrays percorridos por laços, preservando aliases e erros de índice sem depender do curto-circuito de contatos nativos.

**Architecture:** implementar operandos nativos MW/MD/MF indexados por MW, `%S20` sticky e limpeza por R. A API `plc::WordMemory{count}` declara a imagem explícita de words da aplicação; `read_*_indexed(base,index_word)` e `write_*_indexed(base,index_word,value)` usam o conteúdo do MW de índice. O frontend reserva a imagem e emite validação de limite quando seus temporários ampliam o maior endereço nativo. Índice inválido vira offset -32768 para provocar o erro/fallback nativo, sem instrução não comprovada de setar S20. Arrays dinâmicos recebem grupos contíguos no alocador e índices privados estáveis; o caminho reverso recupera endereços/indexação da IL real.

**Tech Stack:** Python stdlib, Clang C++17, SDK nativo, IR/VM/SMBP atuais.

**Spec:** `docs/PARITY.md`; pesquisa `docs/capabilities/CONTROL-FLOW-RESEARCH.md` e novos relatórios de indexação.

## Global Constraints

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- Índice é offset físico em words para MW/MD/MF; cada objeto MD/MF usa duas words. Casos de fronteira e a interpretação física precisam de ensaio externo.
- `%S20` é sticky; usuário limpa com R, sem presumir S/ST permitidos.
- WordMemory reserva toda a imagem0..count-1; configurações/importações com limites de indexação documentalmente ambíguos devem ser identificadas/recusadas, não aceitas por palpite.
- Array C++ fora da faixa não tem semântica definida pela linguagem. Literais inválidos falham na compilação; política runtime experimental usa S20/fallback ao primeiro elemento e não é apresentada como garantia de C++ desktop.

## Review Focus

- Uma leitura indexada em ramo inativo não deve alterar S20. Usar CFG real para acessos com efeito, sem depender de AND/OR com acumulador já decidido.
- RHS de atribuição C++17 precede cálculo do lvalue; índice precisa ser estável mesmo quando valor/destino aliasam o MW que o contém.
- Região explícita e grupo inteiro devem ficar protegidos do reuso, não só base/índice; operações devem preservar as duas halves de MD/MF.
- Maior referência direta, símbolos e ForcedCount não são contratos idênticos comprovados; conservar a lacuna e não inventar limite físico verificado.
- Reversão deve preservar perfil/endereço e retirar dados do programa real, inclusive sequência de leituras/erros, sem depender do C++ original em metadados.

## Task 1: operandos nativos e API de imagem explícita

**Files:** criar módulo focado de referências indexadas e `tests/test_indexed.py`; modificar numeric/model/IL/reverse/project/frontend/lower/SDK.

**Interfaces:** `WordMemory(int count)` global única; `read_word_indexed(int base,int index_word) -> i16`, variantes dword/real e writes correspondentes; `clear_index_error()` e `system(20)`. Índices da API são endereços literais de MW, cujos valores variam em execução.

- [x] Escrever e observar RED com acessos válidos, negativos, overflow, fallback-base, sticky/clear, aliases, índice inalterado e fronteiras de16/32bits; comparar expectativas independentes e C++ nativo.
- [x] Implementar gramática fechada, resolução da VM, SDK e bloqueios de escrita inválida em S20. Suportar somente contextos de operando documentados ou fazer snapshot para temporário direto.
- [x] Implementar declaração/reserva e lowering que restaura limite lógico apesar dos temporários, com anchor de leitura no último word. Capturar valores antes de efeitos posteriores e proteger ramos/curto-circuito por CFG real.
- [x] Recuperar C++ da IL real, serializar Operation/Comparison sem enums novos, preservar perfil e recusar importação com limite ainda ambíguo.
- [x] Executar suíte completa, exemplos, stress e ensaios públicos; revisão, correções RED/GREEN, resultados e commit.

## Task 2: arrays com índice calculado

**Files:** frontend/lower/allocation, SDK se necessário, testes de arrays/pressão e exemplos.

**Interfaces:** manter arrays C++ existentes; adicionar grupos contíguos para os que têm acesso dinâmico, alias de membro→grupo no passe de vida e offset de stride1/2. Array booleano precisa de indexação bit e gate de perfil coerente.

- [ ] Escrever/observar RED de leitura/escrita em laços, locais/globais, ordem RHS/lvalue, inicialização parcial, grupos sob pressão, curto-circuito e índices inválidos.
- [ ] Implementar layout/grupos e uso/def conservadores por grupo, garantindo contiguidade sem alocar fora do banco.
- [ ] Implementar índices i16/i32 válidos, conversão explícita de offset e fallback runtime; não multiplicar com overflow nem repetir avaliação do índice.
- [ ] Testar equivalência C++/IL/reversão/XML, stress reproduzível e composição com comunicação/aliases. Registrar toda restrição pendente, sem reduzir o objetivo integral.

### Decisões para implementar Task 2

- Detectar previamente quais arrays têm índice não literal; conservar o layout de escalares atual para os demais. `Storage.array(kind,count,symbol,persistent=False)` deve produzir os operandos de cada elemento e registrar um grupo/intervalo contíguo de `count*stride` células. `Lowerer.array` publica símbolos dos membros. Preservar semântica dos testes existentes de arrays constantes e não converter todos os arrays em grupos por conveniência.
- O mapa membro→grupo inclui offset físico. Reescrita usa base física do grupo+offset para cada token; análise de efeitos mapeia todos os membros para a identidade do grupo. Leitura dinâmica usa todo o grupo; escrita de membro/indexada é parcial e não mata a vida do grupo inteiro. Possíveis escritas interferem com todos os valores vivos, inclusive dentro do rung. Índice MW continua uma leitura distinta, mesmo em destino indexado. Não ignorar membros por eles não serem chaves de `registers`.
- Ajustar o limite inferior da busca de alocação: o segundo range também precisa terminar em `capacity-span+1`. Um span de4200 words não pode começar3999 e escapar do banco. A preferência4000/500 não é uma obrigação. Globais continuam únicos; locais usam análise conservadora, sem prometer coloração ótima.
- Índice i16/i32 é avaliado uma vez. Capturar RHS antes de calcular lvalue (C++17). Validar0..count-1 antes de estreitar i32/multiplicar stride; o produto válido máximo cabe em i16. Inicializar offset com -32768 e calcular offset válido somente no ramo ativo. Não gerar overflow de i16 para depois detectar um índice inválido.
- Acesso numérico forma `%MW/%MD/%MFbase[%MWoffset]`; o grupo inteiro é inicializado por declarações existentes, portanto seu último elemento tem referência direta. A imagem `WordMemory` de uma API raw não limita o armazenamento privado de um array: a guarda do array é relativa ao grupo e o erro usa sentinel nativo. Não reutilizar a validação raw baseada em base literal/count da imagem para o grupo virtual.
- Leitura indexada com efeitos é capturada no momento da expressão. Em ramo inativo, usar CFG real e valor privado neutro para impedir S20/leituras de floats antigos. Não depender de AND/OR nativo. LHS booleano de operadores já é capturado antes do RHS na Task1.
- Bool exige `%Mbase[%MWoffset]`, resolução distinta de bit/word, prefixo `%M` no parser e `read_m_indexed`/`write_m_indexed` no SDK/reversão. Usar uma imagem `BitMemory` para reconstrução raw e preservar suas reservas. Guardar também o word do índice; não confundir índice em words com região de bits. ST indexado escreve false quando acumuladorfalse; para atribuição condicional, saltar o acesso completo em vez de assumir que S/R sem energia não resolve o endereço.
- Endereçamento de bit requer FL10.0 documentado; estabelecer política explícita de exportação por perfil e registrar que token `FunctLevelManN_N` ainda não foi comprovado como mapeamento lógico pelo editor. Nenhuma validação física ou enum gráfico novo é inferida.
- A revisão deve incluir grupo junto a words de largura1/2, arrays locais reexecutados no loop, inicializador que lê elemento anterior, RHS cujo read indexado altera S20 antes do lvalue, membro que contém índice, negativo/i32extremo, aliases/reservas/buffer Modbus e orçamento contíguo no fim do banco.

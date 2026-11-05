# TM200CE40T: contratos e lacunas de indexação nativa

Pesquisa documental em 2026-11-05. Repositório lido: `/Users/tommy/Offline/projects/m200-cpp`. Foram lidos `AGENTS.md`, `docs/PARITY.md` e `docs/capabilities/CONTROL-FLOW-RESEARCH.md`. Não houve alteração de código, Git, configuração remota ou PLC. Não foram usados editor Windows, simulador oficial ou hardware. Este relatório não declara conformance oficial.

## Fontes e identificação

As páginas abaixo são as impressas no rodapé e coincidem com as páginas dos PDFs locais. As páginas oficiais de download foram verificadas nesta pesquisa; confirmam as revisões locais.

| ID | Fonte primária | Revisão / arquivo local / SHA-256 |
|---|---|---|
| G | [EIO0000003289, Generic Functions Library Guide](https://www.se.com/us/en/download/document/EIO0000003289/) | .04, 09/2025. `research/downloads/manuals/EIO0000003289.pdf`; `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595` |
| O | [EIO0000003281, Operating Guide](https://www.se.com/us/en/download/document/EIO0000003281/) | .04, 09/2025. `research/downloads/manuals/EIO0000003281.pdf`; `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5` |
| P | [EIO0000002019, M100/M200 Programming Guide](https://www.se.com/id/en/download/document/EIO0000002019/) | .06, página oficial publicada em 28/07/2026. `research/downloads/manuals/EIO0000002019.pdf`; `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df` |

P p10 declara atualização para EcoStruxure Machine Expert Basic V1.3 e relaciona G/O como documentos associados. Isso liga G/O ao M200. O sozinho lista M221 entre dispositivos suportados e não basta para provar o perfil CE40T. A versão instalada do editor, o firmware e o nível funcional real do CE40T não foram identificados.

Textos auxiliares: `research/downloads/manuals/EIO0000003289.txt`, `research/downloads/manuals/EIO0000003281.txt` e `/tmp/m200-indexed-P.txt`, este último extraído do P local por `pdftotext -layout`. Conferência visual das tabelas G pp39/41/49 e P p323 realizada em PNGs de `/tmp/m200-indexed-pdfs`. Também foram renderizadas G pp34-35.

## Resultado por contrato

| Questão | O que a fonte comprova | O que continua em aberto |
|---|---|---|
| `%S20` | Inicial 0; controlador seta 1 por overflow; programa deve testar e limpar 0. P define controle `S→U` e aplicação no simulador. | Tentativa de escrita de 1 pelo programa, se rejeitada/ignorada/aceita; conflitos no mesmo ciclo; escrita indireta em string de bits. |
| Overflow | Soma base+índice negativa ou acima do maior word diretamente referenciado; objeto recebe índice efetivo 0. | Relação com Manual/ForcedCount, símbolos sem uso, limite MD/MF no word alto, memória `%M`; alteração ou preservação do MW que contém índice não é explicitada. |
| MD/MF | Alias em words: `%MDi`/`%MFi` usa `%MWi` e `%MW(i+1)`, inclusive i ímpar; regra geral de indexação soma conteúdo do índice ao endereço direto. | Não foi localizado exemplo numérico MD/MF indexado que elimine toda ambiguidade da unidade. Não há prova de multiplicação nativa por 2. |
| `%M` indexado | Sintaxe e leitura/escrita documentadas, com FL>=10.0 nos operadores Boolean normais. | Aceitação concreta no firmware/editor CE40T e política exata de overflow para a zona de bits. Indexado em contato de borda não é listado. |
| Alias e ordem | Atribuição carrega Op2 em Op1; MW/MD/MF indexados podem estar em ambas as posições. | Snapshot dos índices, ordem de resolução dos endereços e leitura/escrita das duas halves de MD/MF. |
| Comparação | Tabela detalhada só lista indexados em Op2; resultado Boolean e relações são definidos. | Aceitação de indexado em Op1, avaliação de todos os operandos, curto-circuito, flags de NaN e efeitos de reordenação. |

## 1. `%S20`: limpeza e escrita

G p34 descreve as condições de overflow; G p35 exige monitoramento e reconhecimento pelo programa, depois de corrigir o índice. P p323 define `%S20` com estado inicial 0, controle `S→U, SIM`; P p326 explica a legenda: o sistema coloca 1 e o usuário coloca 0; SIM indica aplicação no simulador.

Consequências documentais:

- `%S20` não deve ser apagado pelo runtime a cada acesso válido nem no começo de cada scan. O reconhecimento é explícito pelo programa; um segundo acesso válido não é um reconhecimento.
- É correto expor leitura e limpeza. `R %S20` sob condição verdadeira é a forma IL natural de limpeza: G p41 documenta R com `%S`, e O p133 define R como colocar 0 quando o resultado Boolean for 1. Não foi executado um ensaio desse mnemonic no perfil CE40T.
- A classificação `S→U` não equivale a um bit Boolean de escrita irrestrita. Não sustenta implementar `S %S20` como contrato nativo comprovado. A tabela genérica de G p41 lista S com `%S`, mas P atribui a este bit uma direção específica; o comportamento de uma escrita indevida de 1 não está descrito nesses trechos.
- Não foi localizado contrato específico para ST/STN, escrita por `%S16:L` ou por tabela de animação que tente pôr `%S20=1`. Uma API pública que só permite limpar evita alegar essa liberdade sem evidência.

No overflow, G p34 diz que o objeto recebe um índice de valor 0. Pela própria definição de indexação, isso corresponde ao objeto base, não ao endereço global zero. Exemplo derivado, não exemplo publicado: uma leitura `%MW100[%MW2]` inválida deve usar `%MW100` com índice efetivo 0. O texto não afirma que `%MW2` seja sobrescrito com 0; não implementar essa mutação como se estivesse comprovada.

## 2. Maior referência direta, símbolos e Manual/ForcedCount

G p34 usa explicitamente o limite do maior word referenciado diretamente pela aplicação. O pp47-48 descreve outra coisa, a alocação:

- Automática: reserva do objeto 0 até o maior endereço usado no programa **ou associado a símbolo**. Exemplo publicado: usar `%MW20` aloca 21 objetos, 0..20.
- Manual: reserva a quantidade informada no campo No. of Objects, inclusive para permitir futuras alterações online dentro dessa reserva.
- P p19 exige que a memória esteja alocada para que o programa enderece os objetos.

Não há nesses trechos uma regra que substitua a condição de G p34 por `endereço < ManualCount`, nem uma frase ligando o runtime de `%S20` ao campo XML `ForcedCount`. O manual usa a interface No. of Objects; a identificação `Manual/ForcedCount` é evidência de serialização do projeto, não contrato semântico adicional do PLC.

Também não está escrito que um símbolo sem referência executável aumente o limite de `%S20`: O o garante para **alocação automática**, enquanto G fala em referência direta. Assim, `max(referência direta, símbolo)` é uma hipótese/política local razoável, mas deve ser identificada como tal. Reservar 8000 words não comprova tornar todos eles acessíveis por um índice sem outras referências.

A expressão de G é anterior ao detalhe do word alto MD/MF e usa “word” mesmo na seção que agora inclui `%M`. Permanecem perguntas específicas:

1. Uma referência direta `%MD100` eleva o limite de MW até 100 ou 101? O armazenamento exige os dois words, mas o limite de indexação não é descrito separadamente.
2. A avaliação de `%MDn[idx]` exige validar também o word alto `n+idx+1` ou apenas o endereço inicial em relação à quantidade MD permitida?
3. Para `%M`, o limite corresponde ao maior bit usado, à quantidade M alocada ou à capacidade fixa?
4. Uma referência em rung morto, símbolo, comentário ou tabela de animação conta? As fontes não discriminam todas essas categorias.

Capacidade física não resolve essas perguntas: P p24 informa 8000 MW para TM200C, 7999 inícios MD/MF e 1024 M; P p24 também define índice de instância 0..n-1. Logo, MW máximo7999 e início MD/MF máximo7998 são limites físicos, mas não substituem o limite efetivamente configurado/reconhecido pelo aplicativo.

Ensaios discriminantes ainda necessários, sem alterar mais de uma variável por vez:

- Programa com maior referência direta MW20 e acesso indexado a MW50, comparado com mesmo programa em Manual=100.
- Automático com símbolo em MW99 sem leitura/escrita executável, comparado sem o símbolo.
- Idem com referência executável MW99 em rung que não é executado.
- Bases MD/MF próximas do fim e índice que cabe no início mas faz o word alto cruzar a reserva.

## 3. Unidade do índice MD/MF versus stride de array/tabela

G p30 é inequívoco sobre alias: `%MDi` e `%MFi` ocupam os words i e i+1; o word i contém a metade baixa, i+1 a alta. A tabela inclui endereços ímpares e demonstra sobreposição. Portanto `%MD1` não é um elemento independente posterior a `%MD0`.

G p34 define indexação por adição do conteúdo de `%MWj` ao endereço direto. O único exemplo aritmético publicado nessa seção é MW: base108 com índice12 acessa MW120. A tabela aplica indexação também a MD/MF/KD/KF, mas não publica um exemplo MD/MF com um índice não zero.

Leitura literal da regra geral: `%MD100[idx=1]` aponta a `%MD101`, não `%MD102`. Essa é a evidência textual mais forte para offset em words, coerente com G p30; continua sendo aplicação da regra geral, sem exemplo MD/MF específico ou ensaio diferencial. Não foi encontrado suporte no perfil Basic para uma multiplicação nativa implícita por 2.

G p85, por outro lado, fornece um exemplo explícito de **tabela**: `%MD30:4` percorre `%MD30`, `%MD32`, `%MD34`, `%MD36`. Assim:

- Stride2 para elementos contíguos de um array C++ DINT/REAL é coerente com o armazenamento físico e está confirmado para o operando tabela.
- Se o compilador converter índice lógico de um array em offset físico `2*i`, isso é transformação do compilador. Não confundir com alegação de que o colchete nativo já multiplica `i` por 2.
- API “nativeindexed” deve nomear a unidade e conservar o offset físico. A sua unidade pode ser confirmada definitivamente com o ensaio abaixo.

Ensaio mínimo: configurar valores distintos em `%MD100`, `%MD101` e `%MD102` é impossível sem sobreposição de words; em vez disso, inicializar MW100..103 com padrões distintos e ler `%MD100[idx=1]` para um destino separado. Se índice=1 significa um word, sai o par MW101/MW102; se significar elemento, sai MW102/MW103. Repetir com MF e com índice=-1. As fontes permitem concluir que índice negativo só é overflow quando **base+índice** fica negativo; não documentam proibição geral de índice negativo.

Não importar a fórmula de Control Expert/Unity Pro: são produtos/perfis diferentes e existem documentos daquela família com escala2. Essa pesquisa não os usou para definir TM200/Basic.

## 4. `%M` indexado e versão

Há evidência direta e redundante:

- G pp33-34 inclui objeto bit e `%Mi[%MWj]`, com escrita permitida.
- G p39: LD/LDN aceitam `%Mi[%MWj]`, FL>=10.0.
- G p41: ST/STN/S/R aceitam `%Mi[%MWj]`, FL>=10.0.
- G pp42-43: AND/ANDN e OR/ORN aceitam `%Mi[%MWj]`, FL>=10.0.
- O p55 descreve FL10.0 como introduzindo memory bits indexados.

As linhas LDR/LDF, ANDR/ANDF e ORR/ORF nas tabelas são separadas e só listam `%I,%M`; o indexado fica na célula dos operadores normais. A conferência visual confirma isso para G p39. Assim, não estender automaticamente a indexação a contatos de borda por analogia com LD/AND/OR.

FL é o nível funcional do projeto, não o número de versão do editor. Ainda é necessário provar que o editor/firmware CE40T disponível aceita FL>=10 e esses operandos, compilando projeto mínimo no perfil correto. A presença em G, ligado por P, é evidência oficial de capacidade de linguagem; não é resultado de compilação/hardware.

## 5. Avaliação, alias e múltiplas metades

G pp50-53 define atribuição como carregar Op2 em Op1 e lista MW/MD/MF indexados como origem e destino. Exemplo oficial G p53: destino MW indexado recebe fonte KW indexada. Não há ali texto sobre capturar índices de origem/destino antes da operação, ordem de cálculo de endereços, leitura atômica de 32 bits, nem transferência de regiões sobrepostas.

Para o compilador, capturar endereços e valores antes de modificar um destino é uma política determinística prudente; ainda precisa ser comparada com o nativo quando alias for observável. Não tratar a sintaxe `[Op1:=Op2]` como prova da ordem interna ou atomicidade da máquina.

Caso mínimo que detecta uma implementação que reavalia índice no meio de um objeto MD:

1. MW0=0; MW10=2; MW11=300; MW12=400; MW13=500; demais words de destino com sentinelas.
2. Executar `[%MD0[%MW0]:=%MD10[%MW0]]`.
3. Snapshot do índice e valor antes da escrita produziria MW0=2, MW1=300.
4. Um modelo que escreva a metade baixa em MW0 e releia o índice antes da metade alta pode passar a ler/escrever outros endereços. Esse resultado seria observavelmente diferente; a fonte não publica qual micro-ordem o nativo usa.

Antes disso, isolar a outra incerteza: usar um índice inválido, registrar o MW índice depois e observar se o controlador o preserva. Se o MW for alterado no fallback, a ordem de resolução de dois operandos indexados passa a ser observável mesmo numa atribuição simples.

O p123 exige blocos Operation em série; G p50 diz que instrução numérica com acumulador falso não executa e não muda o operando. Isso fornece ordem/guarda no nível de instruções e rungs, mas não resolve a micro-ordem dentro de uma operação. Temporários do compilador devem evitar os MW usados como índices/fontes/destinos, inclusive as duas metades sobrepostas MD/MF.

## 6. Comparação indexada, ordem e curto-circuito

G p49 detalha os operandos:

| Tipo | Op1 listado | Indexados em Op2 |
|---|---|---|
| Word | Referências diretas MW/KW/IW/QW/SW/BLK | MW/KW |
| Double | MD/KD diretos | MD/KD |
| Float | MF/KF diretos | MF/KF |

A página renderizada confirma que é uma diferença real entre colunas, não defeito de extração. Há suporte documental direto para indexado em Op2. Não há suporte explícito ali para Op1 indexado. Isso **não prova** que o parser do editor o rejeita; aceitação deve ser ensaiada, sem inventar simetria.

A inversão algébrica `a<b` -> `b>a`, `a<=b` -> `b>=a`, preservando `=`/`<>`, pode colocar o indexado em Op2 quando o outro operando é permitido em Op1. Porém:

- Ordem de avaliação/flags não é especificada. Um lowering não pode mover uma leitura para outro rung/ramo e supor que `%S20` fica idêntico.
- Para float, inverter a relação é diferente de negar seu resultado: `!(a<b)` -> `a>=b` não é uma equivalência segura na presença de NaN. G pp27-28 documenta a existência de NaN e flags de operações inválidas, mas G p49 não define a tabela de comparação/flags para NaN. Não alegar esse detalhe de conformance sem ensaio.
- Se os dois lados forem indexados, usar temporário elimina a falta documental em Op1, mas precisa preservar a ordem escolhida para leitura e o comportamento de `%S20`.
- O p122 exige operandos do mesmo tipo e, para comparação com múltiplos operandos, FL>=6, até5 operandos/3 níveis de parênteses; isso não especifica short circuit.

G p49 define comparação após LD/AND/OR e seu resultado. O p130 define AND/OR como operação entre acumulador e operando. Nenhum dos trechos garante que uma comparação indexada deixa de ser avaliada quando o resultado Boolean já está decidido. A regra de G p50 que pula a instrução **numérica de ação** em acumulador falso não deve ser aplicada automaticamente aos testes de comparação.

Ensaios necessários: limpar S20; `LD 0`, depois `AND [direto < indexado-inválido]`; observar S20. Repetir `LD 1` com OR. Testar também contato `%M[idx]` em FL10. Esses casos distinguem avaliação do operando de short circuit e são relevantes tanto no caminho C++→IL quanto no modelo local IL→C++.

Uma opção de compilador para o contrato C++ é emitir desvios reais de fluxo para ramos/operandos não avaliados por `&&`/`||`, em vez de depender de um possível shortcut interno de AND/OR. Isso é uma estratégia de lowering, não um achado de comportamento nativo.

## Limite do que foi fechado

Foram fechados documentalmente: direção e limpeza de `%S20`; fórmula geral base+índice; fallback com índice efetivo zero; alias MW/MD/MF; stride2 das tabelas; `%M` indexado com FL>=10 e seus contextos normais; assimetria da tabela de comparação.

Não foram fechados: efeito de escrita de1 em `%S20`; mutação do MW índice no fallback; Manual/ForcedCount/símbolo versus limite de overflow; último word de MD/MF; unidade MD/MF por exemplo numérico dedicado; snapshots e atomicidade em alias; curto-circuito nativo; aceitação Op1 indexado; flags/comparação NaN; versão/firmware/FL efetivamente aceitos pelo CE40T disponível. São lacunas de evidência, não impossibilidades do PLC.

## Preservação no projeto

Os seis originais relevantes estão em `research/downloads/indexed-sources`, sem modificar bytes/CPU. Identidade e URLs fixadas estão em `docs/capabilities/INDEXED-SOURCES.json`; o diretório de downloads não entra no Git. Os caminhos /tmp acima registram o local original da pesquisa. Não se atribui aprovação runtime aos rungs com timer dinâmico ainda não implementado.

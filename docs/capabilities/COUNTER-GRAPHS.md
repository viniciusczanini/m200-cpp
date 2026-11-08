# Reconciliação de gráficos Counter com ramificações

Etapa após ae5f840; meta integral em `../PARITY.md`. Os gráficos B2 e M12,
fixados em `COUNTER-SOURCES.json`, eram recusados antes da normalização, embora
o IL completo já fosse suportado. A etapa verifica o gráfico nativo recebido
contra esse IL, mantendo a geração existente de rungs básicos.

## Desenho

LadderEntity é interpretado como portas Left/Right/Up/Down de cada célula.
Line/VerticalLine conectam suas portas; contatos transferem potência da esquerda
para a direita sob uma condição; bobinas recebem a potência. Counter ocupa2x4
células, com R/S/CU/CD à esquerda nas linhas relativas0/1/2/3 e E/D/F à direita
em0/1/2. ChosenConnection Left ou Left,Right do Counter é observado em originais;
não é usado como máscara dos seus pinos. Fios vizinhos precisam ser recíprocos;
coordenadas/ocupação/conexões/descritores desconhecidos falham explicitamente.

A conectividade fornece as condições de cada entrada e bobina. Um BDD reduzido
com tabela única prova equivalência booleana com as expressões do IL; não é um
teste por amostragem. Operadores e stacks/grupos do IL existente são avaliados
simbolicamente. As ações nativas de entrada precisam seguir a ordem dos pinos
presentes R/S/CU/CD, uma ocorrência por pino, como os gráficos reversíveis
observados. Outras formas IL continuam normalizáveis, mas sua associação a um
gráfico raw não é inferida.

Somente contatos puros do subconjunto atual e bobinas ST/S/R são reconciliados
nesta etapa. Comparações/indexação/ações numéricas no bloco raw permanecem uma
lacuna de verificação, por efeitos/erros/ordem; continuam expressáveis e
exportáveis por normalização. Isso não reduz a meta final. Contatos de borda
I/M usam os mesmos eventos amostrados do modelo existente.
Status BOOL de comunicação também são contatos puros neste bloco; Counter,
Timer e comunicação precisam estar configurados, inclusive quando uma condição
absorve sua leitura. O contexto completo do projeto participa dessa checagem.

## Ordem e memória

Um contato compartilhado é capturado antes do primeiro destino que depende
dele: primeiro os pinos de Counter na ordem nativa, depois bobinas por linha.
A reconciliação considera estados de bits após cada bobina: ST substitui, S
faz OR com o valor anterior, R conserva somente quando a condição é falsa.
Isso evita aceitar uma releitura de memória depois de uma escrita no lugar de
um snapshot feito antes. Endereços/aliases de bits são normalizados.

Cada processamento do Counter avança a geração simbólica de suas propriedades;
uma leitura posterior não é considerada igual a uma anterior por coincidência
de endereço. O BDD não supõe a semântica física das flags. Campos do Counter em
outros objetos, sem ações nesse bloco, permanecem na geração inicial. As saídas
diretas E/D/F usam a geração após todas as entradas. A política física de %C e
seu conflito sobre E continuam pendentes conforme `COUNTERS.md`.

## Limites e configuração

O verificador fecha formatos conhecidos, rejeita células sobrepostas, fios sem
par, componentes que não ligam fonte a destino e condições/ações divergentes.
Reordenação dos elementos XML não muda a prova. Limites explícitos de tamanho
e BDD são budgets da ferramenta, sem afirmar impossibilidade no PLC.

A exportação passa a informar CountersMemoryAllocation/ForcedCount=maxID+1
quando houver contadores; sem enum Allocation inventado. ForcedCount sem enum
é observado em C/L, e255 é o limite de instâncias do modelo. Isso evita depender
de alocação omitida para uma identidade esparsa, sem certificar o perfil exato.

Importar um rung isolado e comprová-lo localmente não é aceitar o projeto
estrangeiro inteiro nem reescrever seu CPU. Editor/perfil TM200CE40T, schema e
hardware continuam pendentes. BDD/roundtrip e o modelo em validação não provam
compatibilidade oficial ou encerram a biblioteca integral.

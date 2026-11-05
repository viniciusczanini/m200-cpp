# Equivalência funcional com o perfil Schneider do TM200CE40T

Requisito reforçado pelo usuário em 2026-11-05: qualquer algoritmo que possa
ser programado e aceito no software oficial para o seu TM200CE40T deve poder
ser expresso em C++ e na biblioteca deste projeto, gerando um projeto equivalente.

Este é o critério final de cobertura. O subconjunto implementado hoje é um
marco de desenvolvimento, não uma redução autorizada dessa meta.

## Contrato

Para cada programa nativo válido no perfil identificado de modelo, firmware,
nível funcional, versão do editor e configuração de hardware, deve existir uma
forma suportada de escrevê-lo em C++ com a biblioteca. O compilador deve gerar
um projeto que o editor aceite e que preserve o comportamento observável.

Isso exige cobrir instruções, tipos, endereços, configuração e execução em
conjunto. Ter uma função declarada no cabeçalho, um PDU Modbus implementado ou
um exemplo passando não conclui a cobertura de um recurso.

O usuário não exige C++ de desktop completo. Uma linguagem de origem limitada
é aceitável desde que permita expressar todos os algoritmos disponíveis no
perfil oficial do controlador. Heap, sistema operacional ou bibliotecas de
desktop não são necessários para esse contrato; arrays, fluxo de controle ou
blocos que correspondam a recursos nativos não podem ser excluídos da meta.

## Equivalência que precisa ser preservada

- Ordem das operações dentro do scan, leituras antes/depois de escritas e
  aliases entre endereços e tipos, inclusive buffers de comunicação.
- Largura, sinal, representação, conversões, flags e tratamento de erros
  numéricos. Algoritmos nativos que consultam e tratam flags também precisam
  ser representáveis; a política de interromper a simulação atual não substitui
  essa funcionalidade na biblioteca final.
- Laços, saltos, condições, subrotinas, funções, blocos do usuário e sequências
  de estados/Grafcet que o perfil oficial permita. Um laço dentro de um scan
  não pode ser dividido entre scans silenciosamente.
- Todas as tarefas admitidas, seus eventos, prioridades, preempção e regras de
  acesso à memória. O único `scan()` mestre atual é uma limitação provisória.
- Imagem de I/O e acesso imediato quando solicitado pelo programa, retenção,
  partida, reset, STOP/RUN, retomada e fallback conforme a configuração.
- Blocos, objetos de sistema e propriedades dinâmicas: temporizadores,
  contadores, registradores, tabelas, strings, RTC, PID, HSC, pulsos, movimento
  e demais recursos efetivamente admitidos pelo alvo.
- Comunicação e seus estados/erros, incluindo Modbus, configuração de canais,
  mapeamentos, propriedades alteráveis em execução e concorrência por porta.
- Configuração de periféricos e expansões compatíveis com o perfil. O suporte
  a uma opção não significa afirmar que ela está fisicamente conectada.

Recursos de outros modelos não entram automaticamente no contrato. O alvo
continua sendo TM200CE40T, com opções e níveis funcionais identificados.

## Capacidade e diagnósticos

As reservas fixas atuais de temporários (%M500..1023 e words a partir de 4000)
não podem ser tratadas como o limite definitivo do controlador. A implementação
final precisa de alocação/reuso e emissão suficientes para representar os
programas nativos que cabem no perfil, contabilizando a memória do compilador.
Formas de acesso direto a recursos nativos podem complementar a API de alto
nível; não devem exigir que o usuário escreva Ladder ou IL manualmente.

Os diagnósticos precisam distinguir:

1. Recurso incompatível com o perfil real do controlador.
2. Programa que excede um limite real do perfil, com o limite identificado.
3. Construção C++ fora da linguagem de origem, indicando a forma suportada de
   expressar o mesmo recurso nativo quando ela existir.
4. Lacuna do compilador, biblioteca, descompilador ou exportador. Um recurso
   aceito oficialmente que ainda não foi implementado é trabalho pendente,
   não um algoritmo impossível para o PLC.
5. Comportamento ou compatibilidade ainda sem comprovação externa.

O contrato não presume que seja possível provar estaticamente a terminação ou
o pior tempo de execução de todo algoritmo. Preservar as regras nativas de
execução/watchdog e registrar o que não foi demonstrado é obrigatório; não
substituir uma incerteza por uma garantia de tempo.

## Projeto e caminho inverso

O produto continua sendo um projeto aberto pelo software oficial, com a
visualização e os símbolos coerentes, e a transferência feita por esse software.
O pedido original de visualização em Ladder permanece uma exigência de backend.
Os casos nativos sem reversibilidade direta para Ladder precisam de solução
explícita e validada; não podem ser omitidos nem considerados cobertos por um
arquivo contendo apenas texto IL para montagem manual.

A conversão de volta deve recuperar do programa real um C++ equivalente,
preservando endereços/identidades e configuração necessários à semântica. Não é
necessário recuperar a sintaxe ou os nomes exatos do C++ original. Guardar uma
cópia do fonte em metadados ou conservar uma lógica opaca sem traduzi-la não
comprova esse caminho inverso.

## Critério de conclusão

- Identificar o perfil oficial exato e levantar todos os recursos, modos,
  operandos, configurações e restrições efetivamente disponíveis nele.
- Para cada um, disponibilizar sua expressão em C++, representação interna,
  geração nativa, configuração, visualização e conversão de volta.
- Exercitar composição entre recursos, limites, erros e ciclo de vida, com
  referências independentes e programas oficiais/reais. Uma lista de exemplos
  isolados não substitui essa cobertura.
- Abrir, compilar, visualizar, salvar e reabrir os artefatos exatos no editor;
  confrontar execução com a simulação oficial e com o hardware onde necessário.
- Vincular os resultados aos bytes e versões testados. Uma bateria finita de
  testes é evidência, não uma prova matemática de correção para todo programa.
- Manter as lacunas visíveis até fechá-las. A biblioteca não pode ser declarada
  completa enquanto houver algoritmos/recursos nativos do perfil sem expressão
  equivalente suportada.

O estado atual, com as baterias locais e os ensaios registrados em
`validation/LOCAL-RESULTS.md`, é experimental e parcial. O inventário e as pendências estão em `capabilities/README.md`.
Ausência atual de Windows/PLC impede a aceitação externa, mas não elimina o
trabalho local de linguagem, blocos, alocação e backend que ainda falta.

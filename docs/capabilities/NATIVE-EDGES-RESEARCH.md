# Contatos de borda nativos — pesquisa para próxima etapa

2026-11-05; pesquisa, sem implementação nova de contatos nesta etapa.
Meta integral: `../PARITY.md`. O suporte a classes RisingEdge/FallingEdge já
existente não demonstra por si só a semântica de contatos LDR/LDF.

Atualização: a etapa seguinte implementa os oito contatos I0/M segundo
`NATIVE-EDGE-CONTACTS.md`. Esta pesquisa preserva as evidências e conflitos;
RISINGn/FALLINGn e validação externa continuam pendentes.

Fonte primária lida: [EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/),
pp37–45 e 47–48. Mesmo PDF preservado em `INDEXED-SOURCES.json`, SHA256
`d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`.
Página40 foi renderizada e inspecionada, além do texto extraído.

## Contratos e cuidado de ciclo

- LDR/LDF, ANDR/ANDF, ORR/ORF e XORR/XORF usam apenas I/M. Não transferir
  automaticamente o suporte de LD/MW:X para esses operadores.
- p37 descreve borda de entrada entre scan anterior e atual e resultado
  disponível durante o scan inteiro. p40 explicita que bordas de M são
  detectadas entre scans da tarefa mestre. Portanto, pular ou repetir um
  contato não deve consumir/recriar a borda como um detector local de chamada.
- p38 diz que mudanças de M são indicadas no próximo ciclo mestre. Seu texto
  posterior generaliza o atraso a LDR/LDF, enquanto p37 trata entradas pelo
  par de scans. A implementação deve explicitar as imagens amostradas de I e M,
  sem presumir que ambas usem o valor lido no ponto da instrução. A fase de I
  e a partida ainda exigem confronto com o simulador/hardware.
- RISINGn/FALLINGn, p47, operam sobre o acumulador da expressão precedente,
  no mesmo ciclo; exigem nível funcional6.0. Não são contatos de endereço.
  Identidade n, execução repetida, salto e reset/partida precisam de testes
  próprios e de um gate XML enquanto faltar mapeamento de nível funcional.
- p48 limita cada tipo de função a 32 instâncias antes de FL10.1 e 255 a partir
  dele. A mesma página proíbe RISING/FALLING imediatamente após AND/ANDN/OR/ORN;
  os rungs públicos T10/15/20 abaixo apresentam justamente AND seguido de
  RISING. É um conflito entre a regra documental e bytes observados, sem
  validação do editor. Conservar as duas evidências, sem inferir uma exceção.

O desenho futuro precisa amostrar os objetos no ciclo, independentemente de
se a instrução foi executada; conservar eventos em consultas repetidas;
testar escrita de M antes/depois do contato e usar a mesma política em SDK,
VM e C++ reconstruído. Não usar a classe local atual como substituição opaca.

## Originais já preservados, bytes conferidos

`tests/public/control-flow-manifest.json` fixa CPU, tamanho e hash:

- `flow-original-loop.smbp`, rung2 tem LDR M0 e rung7 tem ANDR M0. São bons
  candidatos a ensaio isolado com escrita de M e comparação em scans sucessivos.
- `flow-original-jump.smbp`, rung1 tem LDR I0.2 / ORF I0.2. O gráfico usa
  ElementType `RisingEdge` e `FallingEdge`, ambos Descriptor I0.2. O restante
  contém IW0.0, ainda fora do backend; não alegar que o rung inteiro foi aceito.

O inventário `INDEXED-SOURCES.json`, fonte T, conserva o original
`hitmansniper90__portfolio__6815b2794dfa.smbp`/TM221CE40T, SHA256
`3f30b1cabd03220c518afa4c0f5b800ca29f1d905e126ad421bffc8a2d5be3d7`.
Rung6 contém LDR I0.0, gráfico `RisingEdge`/Descriptor I0.0/Column0;
rung10 tem LD S6 / AND Q0.0 / RISING0 / incremento MD10, com
`RisingEdgeBlock`/Descriptor0/Column2. Rungs15/20 repetem a forma com
RISING1/2. Esses tokens são observados, sem comprovar perfil M200, enum de
queda do bloco, limites de instâncias ou aceitação oficial.

Próxima etapa requer RED/GREEN de ciclo/identidade/ordem, gramática fechada,
normalização que preserve esses estados e gráficos reais isolados. Esta
pesquisa não promove registros do catálogo nem altera `library.complete=false`.

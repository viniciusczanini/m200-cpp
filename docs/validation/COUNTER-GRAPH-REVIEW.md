# Revisão independente de gráficos Counter — 2026-11-05

Diff após ae5f840; revisor com contexto novo e sem editar o repositório.
Contrato em `../capabilities/COUNTER-GRAPHS.md`: portas/uniões, BDD iterativo,
ordem de pinos e bobinas, snapshots e estado de bits, recursos e alocação.

O revisor confirmou um achado P2: `READ_VAR.DONE` e os demais status BOOL de
comunicação eram suportados antes, mas o novo State.key encaminhava-os para
model.address, que os recusava. A regressão foi reproduzida em um programa
READ_VAR + Counter e comparada com o checker de ae5f840, substituído somente
no processo de teste: o baseline exportava/reimportava, a mudança falhava na
recarga do próprio arquivo.

O implementador reproduziu a falha antes da correção em testes novos e passou
a tratar status_reference/BOOL_FIELDS, com recurso COMM no contexto do projeto.
Foram testados os quatro campos BOOL das três famílias, exportação/reimportação
READ_VAR + Counter e recusa de configuração ausente mesmo quando a condição
absorve o status.19 testes focados passaram após a correção. Não foi necessário
ampliar o modelo de transporte nem simular sucesso de comunicação.

A revisão não confirmou outro achado. Foram executados17 testes novos existentes
naquele momento,17 regressões de contadores e18.420 operações aleatórias do BDD.
Essas operações extras não entram em contagens de ciclos ou provas do stress
versionado. O revisor também examinou ciclos/feedback alcançáveis e recursos
absorvidos, sem outra divergência confirmada.

Antes da revisão, testes do implementador haviam fechado: texto/atributos
inesperados no gráfico, recurso Counter ausente absorvido pela álgebra,
ForcedCount esparso e budget de operações simplificadas. Os testes de memória
incluem reset de bobina após snapshot, releitura após escrita e aliases; as
propriedades Counter usam gerações diferentes entre ações.

A prova é booleana e ordenada no modelo declarado; não resolve a semântica
física de flags Counter, schema completo, efeitos numéricos/indexados no raw,
perfil/firmware, editor ou hardware. A meta integral continua aberta. Tudo
local, sem CI, publicação, reescrita de CPU estrangeira ou atuação de PLC.

# Contadores comuns %C — contrato experimental

Meta integral em `../PARITY.md`; pesquisa e originais fixados em
`COUNTER-RESEARCH.md` e `COUNTER-SOURCES.json`. Esta etapa acrescenta o recurso
nativo, sem promover cobertura/certificação integral. Não confundir %C com
FC/HSC ou contadores IEC saturados: o domínio documentado é circular0..9999.

API proposta: `plc::Counter{id,preset}` (id0..254, preset0..9999), métodos
`reset(bool)`, `set(bool)`, `count_up(bool)`, `count_down(bool)`,
`update(reset,set,up,down)` e getters `preset/value/done/empty/full`;
`set_preset(i16)` escreve P. update equivale à sequência de quatro instruções
específicas R/S/CU/CD, nessa ordem, e retorna D. IDs preservados, múltiplos
pontos/chamadas e condicionais/laços permitidos. Os argumentos são snapshots;
pular uma chamada preserva estado. Não acumular operações para o fim do scan.
V/E/D/F são somente leitura na API atual; edição por animação é outra operação.

O IL aceita instruções específicas R/S/CU/CD %Ci e BLK/OUT_BLK/END_BLK com
entradas R/S/CU/CD sem operando e saídas curtas E/D/F qualificadas pelo bloco.
P/V são i16 em expressões/operações; E/D/F são bits. Configuração e identidade
pertencem ao IR, JSON, C++ reconstruído e projeto gerado. Não reutilizar seu
estado como memória temporária nem alocar words para simular um recurso nativo.

## Política local explícita, pendente de prova externa

O manual não resolve todas as interações; G120/G122/G123 conflitam sobre E.
O modelo experimental segue a tabela de operações G122: E marca0->9999 por
CD e limpa na próxima contagem down; F marca9999->0 por CU e limpa na próxima
contagem up. A outra direção conserva o flag anterior. Isso é uma hipótese
local testável, não uma resolução do conflito do M200.

Cada instrução atualiza seu pino e processa a instância; níveis R/S ficam
armazenados. R tem prioridade e força V/E/D/F a0; S, com Rfalse, força V=P e
Dtrue, conservando E/F. CU/CD detectam subida no último nível executado do
respectivo pino; histórico avança inclusive sob R/S. Apenas a instrução
CU/CD atual pode produzir sua contagem; não reexecutar bordas antigas de outro
pino. Direções no mesmo scan seguem a ordem das instruções; update serializa
CU antes de CD. Essas decisões sobre pinos, bordas mascaradas, interações,
repetição e ordem continuam políticas locais a confrontar com editor/PLC.

P inicia no valor configurado, V/E/D/F em0. Escrever P não altera V/flags
imediatamente; R/S ou uma entrada de contagem true processam D. Preset inválido
recusa o ensaio local antes da mutação; não se afirma que o firmware o recuse
da mesma forma. Partida quente, STOP/RUN, edição de animação e flags graváveis
permanecem fora do modelo comprovado, sem reduzir o objetivo final.

## Projeto

Counter/Address/Index/Preset/Comment/Symbol são tokens observados em originais.
Não inventar Type/Mode/Single nem enums de alocação. Layout nativo usa as linhas
R/S/CU/CD0/1/2/3 e E/D/F0/1/2 do desenho oficial; R/CU/CD e D possuem amostras
XML reais. Qualquer layout ainda sem evidência deve permanecer explicitamente
pendente; roundtrip sintético não comprova aceitação do editor. CPU estrangeira
não é reescrita nem importada como se fosse TM200CE40T.

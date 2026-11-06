# Bordas de expressão RISINGn/FALLINGn

Etapa após `e7c40fd`, 2026-11-05. Meta integral: `../PARITY.md`. Evidência
primária e conflito de posicionamento: `NATIVE-EDGES-RESEARCH.md`, guia
genérico EIO0000003289.04 pp47–48 e fonte pública T10/15/20.

## Contrato e política local

RISINGn/FALLINGn transformam o acumulador booleano e atualizam o histórico
daquela instrução, mesmo quando o acumulador é false. São distintos dos
contatos I/M amostrados por ciclo. O modelo local usa o valor da última
execução do ponto: pular preserva histórico; repetir no mesmo scan executa
novamente. Histórico inicial false, como as classes de borda existentes.
Execuções repetidas, partida/retomada e fase ainda precisam de prova externa.

Índices canônicos0..254, espaços de RISING e FALLING separados. Cada identidade
aparece em um único ponto estático do programa; um salto pode reexecutá-lo.
IDs duplicados, operandos e sufixos inválidos são recusados. Não são primeira
instrução do rung nem substituem uma carga no início da expressão.

API bool: `plc::rising(index,bool)` e `plc::falling(index,bool)`. Índice literal,
único por tipo e ponto estático. Chamadas podem ser condicionais, aninhadas
e repetidas em laços. O argumento é avaliado antes da atualização, somente
quando a chamada é atingida, inclusive sob &&/||. Dentro de helpers que o
frontend define como expressões puras, essas chamadas de estado são recusadas;
o resultado pode ser passado como argumento bool a um helper.

No IL a função executa no ponto em que aparece; não depende de acumulador true
para atualizar estado. Stack e grupos preservam seus valores externos. O uso
em entradas de Timer é normalizado mantendo essa ordem. O conflito documental
que proíbe funções imediatamente após AND/OR, embora originais façam isso,
permanece explícito: o modelo local aceita a expressão e o backend elimina
esse posicionamento por sua expansão.

## Backend e limites

VM e SDK mantêm histórico por identidade. Frontend emite a operação nativa e
guardas CFG para chamadas inativas; reversão recupera API/identidade a partir
do IL real. Normalização expande cada função em snapshot de entrada, gates e
um M privado persistente, inicializado pela política local de primeiro scan.
Estado não pode compartilhar temporários nem endereços/buffers explícitos.

O exportador usa a expansão em Ladder básico. Não emite raw RisingEdgeBlock/
FallingEdgeBlock nem afirma um mapeamento de nível funcional: há exigência
documentada6.0 e32/255 por tipo conforme10.1, mas o token interno continua sem
prova. A expansão evita exigir esses opcodes no arquivo gerado, com overhead
de M/instruções/labels. Falta de espaço dessa expansão é limitação da ferramenta,
não prova de impossibilidade do algoritmo nativo. Emissão nativa e equivalência
sem esse overhead continuam no objetivo final, onde necessárias.

Editor, perfil exato, ciclo de vida e hardware continuam pendentes. O modelo
local e XML sintético não concluem cobertura integral nem compatibilidade oficial.

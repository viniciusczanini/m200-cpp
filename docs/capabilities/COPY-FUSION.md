# Fusão conservadora de cópias

Implementada durante a etapa de bordas de expressão após `e7c40fd`, para
preservar capacidade ao recompilar C++ recuperado do arquivo gerado. O caso
que observa resultados das 255 funções de cada tipo revelou overhead real:
o IR original cabia, mas o caminho inverso e sua reexportação excediam o budget.

O pass opera antes de alocar registros privados. Conta referências por owner,
incluindo views MW/MD/MF e bits de words, e usa a análise CFG existente com
saltos para trás e vida entre scans. Funde apenas cópias de escalares privados
com uso único ou prova de que o valor não vive após o consumidor; membros de
arrays e estado persistente ficam excluídos. Não cruza labels nem altera IDs
de funções de estado.

Loads encaminhados continuam avaliados uma vez antes dos efeitos seguintes.
Fusão numérica exige a mesma guarda e tipo; NOT/AND só pode mudar a ordem de
leituras comprovadamente puras. Comparações, indexação e leituras que alteram
S20 não podem ser suprimidas por um curto-circuito novo. Series ficam dentro
das 10 colunas de contatos, ou 9 antes de Operation; encaminhar uma comparação
de duas colunas não pode criar um rung que o backend não represente.

Somente registros eliminados sem referências remanescentes são removidos;
símbolos, aliases e source-map são ajustados juntos. Literais podem aparecer
diretamente em operações binárias, conforme G53–54; funções que exigem objeto
mantêm seu snapshot. O budget de construção é 100.000 instruções intermediárias;
o budget experimental de emissão permanece 10.000 e é conferido após otimizar.
Esses números são limites da ferramenta e não uma certificação da capacidade
de firmware, tempo de scan ou watchdog do PLC.

Testes incluem 6.000 cópias que devem caber após fusão, aliases de dword por
bits de word, valores usados depois da cópia, redefinição com auto-operando,
loops/labels, S20 antes/depois de um contato indexado e limite gráfico. O
stress de capacidade percorre IL/C++/XML, lê o arquivo exportado e recompila
seu C++ novamente. A equivalência integral e a validação externa permanecem
no objetivo; esse pass não demonstra alocação ou geração ótimas para todo programa.

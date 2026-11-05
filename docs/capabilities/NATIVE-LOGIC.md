# Lógica nativa e normalização para Ladder

Base `2facc4f`, pesquisa de 2026-11-05. Meta integral em `../PARITY.md`.
Fontes primárias: [Generic Functions EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/), pp. 41/46/82/119, e [Operating Guide EIO0000003281.04](https://www.se.com/us/en/download/document/EIO0000003281/), pp. 131–135 e tabela de análise pp. 48–50. Mesmos PDFs/hashes já fixados no projeto.

## Contratos

- STN escreve o inverso do acumulador sem alterar o acumulador. N inverte o
  acumulador sem operando. MPS salva seu valor, MRD relê o topo sem removê-lo,
  MPP relê e remove o topo. Cada push tem pop no mesmo rung.
- AND( / OR( salvam o acumulador externo, carregam o primeiro operando e
  combinam o resultado na instrução `)`. Até 32 níveis de parênteses; ações,
  blocos, saltos e instruções de stack são proibidos dentro deles.
- O guia genérico informa stack de 32 valores; o Operating lista erro acima
  de 11 MPS aninhados. É um conflito documental. O modelo local aceita 32 e a
  exportação elimina MPS, sem alegar que o perfil físico execute 32 pushes.
- Timer estruturado admite lógica de entrada e saída Q com ST/STN/S/R. A
  chamada direta `IN %TMn` é implementada onde o acumulador posterior não é
  observado: no fim do rung ou antes de outro LD/LDN. Efeito de IN sobre o
  acumulador em outras sequências permanece sem prova e é recusado.
- Short-circuit e erros de contato/comparação indexados AND/OR continuam
  recusados onde já eram ambíguos. Modificadores de parênteses N/R/F e contatos
  de borda nativos ainda exigem contrato próprio; não são interpretados por
  analogia.

## Arquitetura e evidência

O parser fecha a gramática e valida equilíbrio/profundidade, configurações,
destinos e pontos de salto. VM e C++ reverso usam estados separados para
stack e parênteses, preservando snapshots antes de escritas.

`ladder_lowering.normalize(program)` traduz formas que não cabem nos rungs
gráficos atuais para rungs simples e blocos Timer canônicos. Reserva todos os
endereços originais e buffers de comunicação; temporários são alocados pelo
passe de vida. Não inventa enums de gráfico. Identidades de labels, timers e
configurações são conservadas; o IR original não é modificado. Metadados
registram que houve normalização, sem usar uma cópia do C++ para executá-la.

O exportador normaliza antes de serializar e verifica o IL efetivamente gerado.
Limites/overhead e gates de perfil anteriores permanecem. Indexação bit não é
normalizada para XML enquanto o perfil/limite estiverem sem prova.

Originais pinados contêm STN e MPS/MPP em `flow-original-loop.smbp` e timers
com entrada composta/SetCoil/ResetCoil em `06-correto.smbp`, rungs 35/36.
Ensaios isolados preservam bytes e CPU; não equivalem a importar projetos
inteiros, validar o editor ou executar no PLC.

## Verificação e limites

Os testes de `tests/test_native_logic.py` incluem limites/malformed, snapshots,
saltos, NaN por alias MD/MF sob curto-circuito, whitespace e gráficos originais
com descritores alterados para exigir recusa. A revisão independente encontrou
casos de leitura adiantada e diagnósticos internos; foram reproduzidos em RED e
corrigidos. Ela conferiu também 7.440 scans diferenciais e equivalência em laço.

O stress reproduzível tem 10 casos/5.120 scans com oráculos separados, reserva
de símbolos/aliases, estado entre scans e laço. Três casos usam IL autêntico
isolado: parênteses, stack e STN com configuração TOF explícita. Os gráficos de
35/36 são verificados, mas seus defaults de timer incompletos não são inventados
para alegar execução do programa original. O manifesto público promove só os
resultados comprovados e mantém as recusas restantes.

A normalização reserva labels existentes e usa saltos reais para materializar
comparações somente quando necessárias. A falta de label livre, memória privada
ou orçamento de instruções é diagnosticada como overhead da ferramenta; não
prova que o algoritmo não caiba no PLC. A base física, o limite MPS conflitante,
outros operadores e a validação oficial continuam pendentes. Resultados e hashes:
`../validation/NATIVE-LOGIC-LOCAL-RESULTS.json` e `../validation/NATIVE-LOGIC-STRESS-RESULTS.json`.

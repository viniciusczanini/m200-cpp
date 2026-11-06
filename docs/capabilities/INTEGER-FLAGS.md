# Integer flags: original implementation notes

This historical note predates the integrated G02 destination/constant/status
implementation. Its open-work section describes that earlier checkpoint.
The current English [numeric guide](../NUMERIC.md) and
[integration evidence](../validation/NATAL-INTEGRATION-PROGRESS.md) supersede
those older abort/recovery statements. In particular, destination DIV/REM/SQRT
and explicit copies now retain unknown masks; primitive SDK value propagation
and native lifecycle qualification remain pending.

Etapa após 86af2a3; meta integral em `../PARITY.md` permanece. Fontes:
[G EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/),
pp. 54–57 e [P EIO0000002019.06](https://www.se.com/ph/en/download/document/EIO0000002019/),
pp. 322–323. PDFs/textos fixados em research/downloads/manuals.

SHA256 G: `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`;
P: `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`.

P define S17 pelo último bit e S18 como overflow/erro, testado e limpo pelo
programa. G55 mostra 23241+21853 armazenando -20442 e S18=1, seguido de saturação
explícita a 32767. G57 atribui S17 ao último bit ejetado de SHL/SHR/ROL/ROR.
A frase genérica G55 sobre gerenciar/resetar ambos não muda a definição de
último bit do guia específico P322: um bit ejetado zero limpa S17.

## Contrato local

- `plc::system(17/18)` lê flags. `clear_shift_carry()` e
  `clear_arithmetic_error()` emitem R S17/R S18. Também se preservam leituras
  e R no IL/reversão/projeto. ST/STN/S desses flags não são admitidos pela API.
- S18 começa false, torna-se true em overflow inteiro e permanece até R;
  operações válidas, cópias, comparações e scans seguintes não o limpam.
- S17 começa false, muda em todo shift/rotate: esquerda/ROL usa o bit original
  width-n; direita/ROR usa n-1. Inclui n=width. Outras operações o conservam.
- ADD/SUB/MUL e ABS i32 calculam em precisão maior, guardam os bits baixos da
  largura e assinalam S18 se o resultado matemático estiver fora da faixa.
  DIV mínimo/-1 usa o mesmo retorno modular; REM correspondente retorna 0 e
  assinala o overflow do quociente. O exemplo G55 comprova o caso ADD word;
  demais bits exatos de resultados não significativos são uma política local
  modular a confrontar com editor/PLC, não uma prova independente de firmware.
- Literais de tipo continuam limitados; um literal i16=32768 é inválido.
  Operações literais com overflow inteiro passam a ser emitidas, preservando
  seu efeito nos flags em execução. Não constant-foldar um efeito observável.
- Guardas/&&/|| e laços preservam o ponto de avaliação: chamada pulada não muda
  flags. Leitura usada como argumento precede a operação; snapshots de flags
  precisam sobreviver a operações seguintes e a limpezas.

## Escopo ainda aberto

Divisão inteira por zero e SQRT inteiro negativo marcam S18 antes de interromper
o ensaio local; seus resultados são descritos como incorretos sem bits definidos.
Não se atribui um zero arbitrário para fazer testes passarem. A recuperação
local que descarta/reescreve esses resultados ainda precisa de representação de
valor indeterminado e validação independente do SDK. A geração nativa e a meta
integral não são reduzidas por essa lacuna do modelo.

Float32 não finito, SW17 e recuperação de erros de ponto flutuante, BCD/ASCII,
flags de outras instruções e ciclo de vida completo continuam trabalho aberto.
Não confundir esta etapa de inteiros/shift com cobertura de todos os erros
aritméticos. Reset/partida e comportamento físico exigem os artefatos exatos
no editor e no TM200CE40T; tudo permanece experimental, sem atuação automática.

## Verificação local

`tests/test_integer_flags.py` cobre modelo/API/SDK, snapshots, clears guardados,
overflow literal, curto-circuito, laços, convivência com S20 e reset em gráfico
Counter. `tests/stress/integer_flags.py` usa matemática modular e listas/tabelas
independentes para 192 combinações de shift/largura/distância, 13 famílias ALU,
oito composições de controle e cinco exemplos/trechos nativos com harness.
As tabelas de referência observam todos os bits do resultado, incluindo i32.
Cada caso percorre também C++ gerado do XML efetivamente exportado, recompilação
e nova exportação. As contagens e resultados da execução integral são registradas
separadamente em `../validation/INTEGER-FLAG-LOCAL-RESULTS.json`.

A matriz digital de 24 entradas ×16 saídas ×2 polaridades preserva seus 768
bindings e passa pelo mesmo caminho inverso do projeto efetivamente emitido.
O teste adicional de imagem Q verifica todas as saídas, escritas condicionais
sucessivas, preservação entre scans, inversão, reset e cópia em grupos.
Essa matriz é lógica; tensão, corrente, cabeamento, cargas, entradas rápidas,
pulsos e demais modos especiais permanecem sem ensaio elétrico.

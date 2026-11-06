# Conversões BCD, CONCATW e DWORD

Etapa após bd5bcf3, mantendo a meta integral em `../PARITY.md`.
Fontes primárias: [G EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/),
pp. 58–60; [P EIO0000002019.06](https://www.se.com/ph/en/download/document/EIO0000002019/),
pp. 322–323; [FAQ297976](https://www.se.com/sk/sk/faqs/FA297976/) e
[mapeamento oficial Twido](https://product-help.schneider-electric.com/Machine%20Expert/V1.1/en/TwiEmSup/TwiEmSup/Twido_Functions/Twido_Functions.htm).
G SHA256 `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`;
P SHA256 `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`.

## Contrato e decisões

- `bcd_to_int(i16)` / `bcd_to_dint(i32)` emitem BTI: decodificam quatro/oito
  dígitos 0..9 dos bits do portador. O sinal do portador não é sinal decimal.
  Assim, o portador i16 -26215 (0x9999) é BCD válido e retorna 9999.
- `int_to_bcd(i16)` / `dint_to_bcd(i32)` emitem ITB: aceitam valores decimais
  0..9999 / 0..99999999, retornando os bits BCD em portador assinado da mesma
  largura. O bit alto do BCD não causa overflow inteiro por si só.
- BTI com nibble A..F e ITB fora da faixa marcam S18 e interrompem o modelo
  local antes de escrever o destino. Resultados inválidos não têm bits definidos
  nas fontes; recuperação local de valor indeterminado continua lacuna. Literais
  conhecidos nesse domínio falham na compilação como limitação atual da ferramenta.
- `concat_words(i16 low,i16 high)` emite CONCATW, preservando exatamente os bits
  dos dois operandos, inclusive negativos. Primeiro argumento baixo, segundo alto,
  conforme as duas fontes oficiais complementares. Retorno i32 com sinal.
- `int_to_dint(i16)` emite DWORD. O modelo local estende sinal e preserva o
  valor numérico. G estabelece a instrução, mas não especifica extensão para
  negativos: esta é uma hipótese de emulação a testar no editor/PLC, não prova
  fornecida pelo FAQ de CONCATW. Não substituir DWORD por CONCATW sem evidência.
- Conversões válidas conservam S17 e S18; não apagam erro anterior. Guardas,
  argumentos, snapshots e laços mantêm ordem. Não há promoção C++ implícita.
- Operandos/destinos MW/MD, snapshots calculados/indexados e propriedades já
  suportadas percorrem os caminhos atuais. Bancos KW/KD, I/O/SW e expressões IL
  compostas ainda dependem de suas implementações; esta etapa não os simula.

Alternativas consideradas: expandir BCD/concat em operações word ou emitir as
instruções nativas. Escolha do implementador: emissão nativa com avaliadores
independentes no SDK/VM, reduzindo overhead e preservando o recurso no projeto.
Tratar sinal BCD como erro ou inverter CONCATW contradiz as fontes e foi rejeitado.
Não se aguarda confirmação de usuário, que já autorizou implementar tudo localmente.

## Evidência e validação

Testes devem esgotar os 65.536 portadores BTI word e todos os 10.000 ITB word;
validar oito dígitos nas posições extremas, todos os nibbles inválidos por
posição e limites negativos/99999999+1. CONCATW deve observar todos os bits,
ambas as posições, aliases MW/MD e argumentos capturados antes de escritas.
Widening deve cobrir todos os valores i16 e preservar flags.

O caminho C++ → IL → XML → C++ efetivamente exportado → nova compilação/XML
é obrigatório no stress. Exemplos de manual são rotulados como tal. O corpus
atual contém apenas DWORD composto; não chamar um harness BCD de projeto
original baixado. Aceitação no editor, nível funcional/perfil exato, flags e
semântica física continuam pendentes, sem CI/push/upload/acionamento automático.

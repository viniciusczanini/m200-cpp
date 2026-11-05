# Propriedades e estado de timers: contrato da etapa

Este documento registra a etapa `12ab05b`, anterior aos modos. A continuação
`TIMER-MODES.md` implementa os caminhos locais retentivo/preset dinâmico;
o gate de XML e a validação externa desses modos continuam pendentes.

Pesquisa em2026-11-05. Fonte primária: [Generic Functions EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/), pp107–118; PDF local SHA256 `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`. A página oficial continua oferecendo revisão04 de01/09/2025. O [Programming Guide M100/M200](https://www.se.com/id/en/download/document/EIO0000002019/) revisão06 associa esse guia ao M200. Perfil, editor e PLC disponíveis continuam pendentes.

## Contrato documental e escolhas locais

- P é preset0..9999, pode ser lido/testado/modificado pelo programa; V é word
  crescente em unidades da base, pode ser lido/testado, mas não escrito pelo
  programa; Q é saída de leitura.
- Base1ms somente TM0..5; outras bases10ms,100ms,1s,1min. TM0..254 é a
  capacidade documentada do alvo, conforme inventário existente.
- Com Dynamic Preset=false (padrão), P escrito só afeta a próxima ativação.
  Com true, afeta a execução corrente, requer FL12.0; esta opção continua
  pendente de perfil/configuração/execução, não é simulada como false.
- Retentive=true requer FL3.3 e continua pendente. Esta etapa é não retentiva.
- Saltar o bloco não congela seu tempo/V/Q. A saída ligada ao bloco não é
  reescrita se ele não executa; ler Q fora dele deve observar o estado interno.
- TON começa com INtrue, satura V no preset ativo e mantém Q até INfalse;
  INfalse zera V. TOF põe Qtrue e V0 com INtrue; começa na borda de descida,
  satura V e limpa Q ao terminar; nova subida zera V. TP começa na subida
  se não estava rodando, ignora novas subidas durante o pulso e limpa Q ao
  terminar; quando terminou e INfalse, V zera.
- O relógio local usa floor(elapsed_ms/base_ms), ancorado na ativação. Fase do
  tick nativo, atualização entre instruções, jitter, STOP/RUN, retenção e
  reinícios continuam exigindo evidência externa. Não se afirma precisão física.
- P fora da faixa em execução interrompe a simulação com diagnóstico; as
  fontes usadas não definem suficientemente o efeito físico desse erro. Não
  inventar clamp, wrap, flag ou sucesso. Literais inválidos são recusados.

## API e preservação

`Ton/Tof/Pulse{milliseconds}` permanece. O construtor explícito
`{native_index,base_ms,preset}` conserva identidade/base/preset na reversão.
Métodos `preset()`, `value()`, `done()` leem P/V/Q; `set_preset(i16)` escreve P.
Instâncias/índices colidentes falham. Construção automática segue a ordem de
declaração e não renumera um explícito posterior em colisão.

Escritas emitidas em P são operações nativas, sem variável sombra privada.
Leituras/escritas numéricas podem compor a gramática fechada existente; V/Q
não são destinos. A VM e o SDK mantêm estado separado da RAM compartilhada.
Reversão usa referências reais e construtores explícitos, sem copiar fonte.

## Originais já preservados

`INDEXED-SOURCES.json` fixa I1/I2 com `%TM1.P := %MW20[%MW10]`; são IL
executável em projetos M221, sem gráfico indexado correspondente. O arquivo
`research/downloads/public-projects/flow-original-loop.smbp` contém leitura
executável `%TM0.Q`. Essa evidência dá sintaxe real; não comprova comportamento
temporal nem aceitação CE40T. Testes isolados não são importação integral.

## Implementação e validação local

Os métodos, construtores e operandos acima estão implementados em frontend,
IL/VM, SDK e reversão; a geração numérica/contatos usa os enums gráficos já
existentes. P não ocupa RAM MW privada, e configurações acessadas somente por
propriedades são preservadas sem inventar um update. Endereços inválidos,
instâncias ausentes, destinos V/Q e literais P fora da faixa são recusados.

`tests/test_timer_properties.py` confronta timelines escritas à mão para cada
tipo, P antes/durante ativação, TM254/TM42 esparsos, salto sobre o bloco,
inatividade, fonte indexada e composição com Clock. A revisão independente
reproduziu aritmética/leituras P/V/Q e confirmou preservação da configuração.

O teste com variável global `clock` expôs poluição de nomes do antigo harness
que incluía iostream. O harness usa agora I/O C mínimo sem esse header, e o
teste mantém o nome original. A revisão revalidou frames de0ms e EOF completo,
vazio e truncado. Colisões de nomes globais com as funções C `getchar`/`putchar`
continuam uma limitação preexistente desse executor de referência; não se
declara que todo identificador C++ tenha sido validado.

`tests/stress/timer_properties.py` tem seed fixa,15casos de tipo/base e um
caso público isolado:8192scans. O oráculo separado guarda eventos de ativação
e fim; compara P/V/Q e saída ligada ao bloco com código original/reverso,
IL/VM, recompilação e XML sintético. O caso I1 conserva a atribuição real e a
configuração original TOF/TM1/base1s, com hashes conferidos antes/depois;
o restante do projeto M221 não é apresentado como importado.

Base10ms continua com recusa XML exercitada; demais bases passam o XML
sintético local. IsRetentive=true/IsDynamicPreset=true, mapeamento de nível
funcional, fase física do tick, STOP/RUN/reinícios, editor/simulador oficial
e PLC permanecem pendentes. Resultados atuais:
`../validation/TIMER-PROPERTY-STRESS-RESULTS.json` e
`../validation/TIMER-PROPERTY-LOCAL-RESULTS.json`.

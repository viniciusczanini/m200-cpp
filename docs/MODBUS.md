# Modbus — TM200CE40T profile

## Integration candidate: dynamic properties and requests

The integrated candidate adds `block.property(plc::CommProperty::Id)` and
`block.set_property(plc::CommProperty::Id, value)` alongside the existing
constructor/update/status APIs. See the complete
[source example](../examples/modbus_properties.cpp). These are native property
words and actual operation blocks, preserved through project import and reverse.

| Block | Available property enums |
|---|---|
| All three families | `Link`, `Id`, `Timeout`, `ObjType` |
| READ_VAR / WRITE_VAR | `FirstObj`, `Quantity`, `IndexData` |
| WRITE_READ_VAR | `FirstWriteObj`, `WriteQuantity`, `IndexDataOut`, `FirstReadObj`, `ReadQuantity`, `IndexDataIn` |

Property words preserve unsigned 16-bit patterns using the SDK's signed i16
carrier. **The native Link property codes differ from the constructor enum:**
1 selects SL1 and 3 selects ETH1 in the currently supported embedded profile.
Do not cast `plc::Link` to obtain a property code. A variable link requires both
supported channels and an Ethernet remote to be explicitly configured in the
template; the exporter does not create peers or ports implicitly.

Writes to buffer/count/object properties conservatively require
`plc::WordMemory memory{8000};`. This reserves the dynamic native word image and
prevents compiler scratch from aliasing possible buffers. It is a compiler
restriction, not a claim that every PLC program needs all 8000 cells.

Execute snapshots the complete configuration and outgoing data for the active
request. Property writes during Busy configure a later request rather than
redirecting the active response. Abort prevents a late response from mutating
the canceled request's buffer; it cannot undo a remote write already processed.
Channel ownership, response validation, timeouts and errors have local models.
The default missing transport still reports failure rather than invented success.

Scripted/loopback VM protocol tests and SDK execution are separate evidence.
The PLC_NATIVE SDK now has an independent scan-driven PDU codec/state machine
in `sdk/plc_modbus_async.hpp`, with explicit raw transport callbacks described
below. Both original snapshot/abort cases passed on VM and SDK, and six new
methods exercised 43 distinct SDK stimuli across all nine admitted function
codes. See the [independent SDK report](validation/G11-SDK-ASYNC-RESULTS.md).
Native transactions, physical interoperability and expanded property/graph
acceptance remain separate final editor/simulator stages. See the
[integration results](validation/NATAL-INTEGRATION-PROGRESS.md).

## Baseline native profiles and protocol reference

O alvo do compilador continua sendo exclusivamente TM200CE40T. Projetos originais de M221, CE24R e CE40R servem como evidência de instruções e serialização, sem trocar a CPU deles para produzir templates aparentemente compatíveis.

A biblioteca cobre os blocos nativos READ_VAR, WRITE_VAR e WRITE_READ_VAR em perfis estáticos delimitados, com modelo/protocolo local e produtos gerados já salvos e reabertos no editor oficial. A [matriz de conclusão](capabilities/COMPLETION-MATRIX.json) registra os perfis implementados e as lacunas restantes; transações nativas e comunicação física são etapas distintas.

## API C++

`ReadVar(Link, Id, Timeout100ms, Object, FirstObj, Quantity, IndexData)` e `WriteVar(...)` configuram leitura/escrita. `WriteReadVar(Link, Id, Timeout100ms, FirstWrite, WriteQuantity, IndexOut, FirstRead, ReadQuantity, IndexIn)` representa FC23. Todos os parâmetros de configuração são literais ou enums do SDK.

`Link::Serial1` seleciona a RS485 embarcada; `Link::Ethernet` seleciona ETH1. Em SL1, Id identifica o escravo (1..247; broadcast0 somente para escrita). Em ETH1, Id é um índice de remoto configurado (1..16), **não o UnitId do MBAP**. Os parâmetros do transporte TCP de teste são explícitos e separados. A interpretação dos campos UnitId do perfil nativo requer conferência/captura oficial; não foram adicionados campos de porta remota sem prova de serialização.

`Object` oferece HoldingWords, DiscreteInputs, Coils, InputWords, SingleCoil e SingleRegister. Os tipos válidos dependem do bloco. A matriz de protocolo local é:

| Bloco | Código | Limite por requisição |
|---|---:|---:|
| ReadVar holding/input words | 3/4 | 1..125 words |
| ReadVar coils/discrete inputs | 1/2 | 1..2000 bits |
| WriteVar words/coils | 16/15 | 1..123 words / 1..1968 bits |
| WriteVar single coil/register | 5/6 | um objeto; Quantity é ignorada |
| WriteReadVar | 23 | 1..121 words de escrita e 1..125 de leitura |

O intervalo remoto completo deve caber em 0..65535. Os buffers locais completos devem caber nos 8000 words compartilhados entre MW/MD/MF. Bits são empacotados do bit0 para cima. Os registradores são transmitidos como words de 16 bits; não há inferência da ordem de words de tipos de 32 bits em um dispositivo de outro fabricante. Timeout é expresso em 100 ms; zero desabilita o timeout do bloco. O teto 2147483647 é de representação System.Int32/SDK, não uma comprovação de um limite físico de timeout do controlador.

Cada instância utilizada recebe `update(execute, abort)` uma vez, incondicionalmente, por scan. O retorno é Done. Getters `done()`, `busy()`, `aborted()`, `error()`, `comm_error()` e `oper_error()` podem ser lidos antes ou depois da atualização; a posição no scan é preservada. Execute precisa de uma transição falsa→verdadeira; TRUE no primeiro ciclo de RUN não cria uma borda. Abort não desfaz uma escrita já processada pelo dispositivo remoto.

O caminho inverso usa um construtor adicional com índice nativo como primeiro parâmetro para preservar objetos esparsos, como `%READ_VAR7`. Não se pode misturar índices automáticos e explícitos do mesmo tipo num programa; índices duplicados ou fora de 0..31 são recusados.

## Geração de projeto

O template deve ser autêntico do seu TM200CE40T e configurar o canal. O compilador não inventa endereços de equipamentos nem ativa uma porta de forma implícita. A SL1 requer o perfil explícito RS485/RTU/master. ETH1 requer um RemoteServer correspondente. A validação de funcionalidade suporta o formato de nível `FunctLevelManN_N`, com 16 instâncias por tipo antes de 10.1 e 32 a partir de 10.1. Nomes legados de nível ainda podem ser recusados.

O XML admitido inclui READ de holding/input words e coils/discrete inputs, WRITE de holding words/coils e single coil/register, além de WRITE_READ_VAR com buffers MW assimétricos. Os perfis adicionais observados usam Man21 e SL1 master estática. READ I, WRITE Q e WRITE_READ MW admitem Execute/Abort com contatos M normais e as formas full-pin de status comprovadas; status parciais, reordenados ou intercalados permanecem rungs separados, na ordem original. Para serial foram observados 9600/19200 baud, ParityEven/ParityNone, DataBits8, StopBits1 e RS485/RTU. Outros canais, propriedades e formas gráficas precisam de seus próprios perfis. O candidato de integração adiciona a API de propriedades dinâmicas descrita acima; os resultados históricos deste parágrafo continuam limitados aos perfis estáticos observados. Os [produtos bare gerados](validation/MODBUS-BARE-ABORT-GENERATED-PROJECT-RESULTS.md) e [full-pin](validation/MODBUS-FULL-PIN-GENERATED-PROJECT-RESULTS.md) passaram save/fresh reopen com No error; isso não registra uma transação nativa bem-sucedida.

A configuração .NET é validada por tipo, posição e cardinalidade. Objetos desconhecidos não são instanciados nem ignorados. Alocações manuais precisam cobrir as referências e buffers; também são conferidos limites de bits/timers. Um candidato é relido antes de substituir o destino, preservando o arquivo anterior se a validação falhar. Isso não é uma validação do software oficial.

Proveniência detalhada: [MODBUS-FORMAT-RESEARCH.md](capabilities/MODBUS-FORMAT-RESEARCH.md).

## Execução e testes locais

`Machine(program, communication_transport=...)` recebe explicitamente MemoryTransport ou LoopbackTCPTransport. O segundo aceita apenas 127.0.0.1, sem DNS, e só abre um socket quando o programa inicia uma troca. O padrão não abre conexão: uma tentativa sem transporte resulta em erro 255/15. O SDK C++ nativo segue esse caso padrão. O transporte bruto explícito e o hook legado são descritos abaixo.

O engine verifica respostas e MBAP, limita filas/recepção, ignora respostas fora da troca vigente e não tenta novamente automaticamente. Uma troca ocupa o link; simultaneidade de Abort e Execute, recusa por link ocupado e limpeza de códigos numéricos com Execute FALSE são políticas conservadoras do modelo local onde a evidência do PLC não é suficiente. Não representam uma promessa sobre o escalonamento físico. O modelo não contém transporte serial RTU/ASCII/CRC físico; no programa exportado esse transporte pertence ao runtime oficial do PLC.

Os testes incluem sockets reais locais, fragmentação, IDs errados, exceções Modbus, timeout, aborto, esgotamento de sockets, buffers extremos e ida/volta de índices. Um teste completo compila C++, gera/reimporta SMBP e recebe words de um servidor Modbus TCP em loopback através do executor IL.

Referências primárias: [Schneider Generic Functions Library, edição 04](https://www.se.com/us/en/download/document/EIO0000003289/), pp 171–186 e 204–205; [Basic Operating Guide, edição 04](https://www.se.com/us/en/download/document/EIO0000003281/), pp 47–48 sobre alocação; [Modbus Application Protocol V1.1b3](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf); [Modbus TCP Implementation Guide V1.0b](https://www.modbus.org/file/secure/messagingimplementationguide.pdf).


## PLC_NATIVE raw asynchronous PDU transport

Install `plc::detail::modbus_transport = {context, start, poll, cancel};` explicitly.
`start(void*, const CommunicationConfig&, const unsigned char* pdu, unsigned size,
unsigned long long now_ms)` returns `ModbusStartResult{accepted, token,
comm_error, oper_error}`. An accepted token, including zero, belongs to that
request. The SDK retains its config and outgoing PDU/data snapshot until terminal
completion/cancel; the transport must not modify their storage.

`poll(void*, ModbusToken, now_ms, unsigned char* response, unsigned capacity)`
returns `ModbusPollResult{kind, size, comm_error, oper_error}`. The kind is
`ModbusPollKind::Pending`, `Response`, `BroadcastComplete` or `Error`. Response is
one complete raw PDU, at most253 bytes; the callback must honor the buffer
capacity. `cancel(void*, ModbusToken)` retires pending transport resources. A
successful poll consumes its token; rejected starts own their cleanup. Cancel
must also tolerate a token already consumed by a malformed/exception response. Callbacks
are nonthrowing, nonreentrant and synchronous; pending I/O is represented by a
token, never by blocking a scan. They must route each reply to its exact token.
No socket, CRC, MBAP, wall-clock peer or physical port is supplied implicitly.

The SDK controls edges, per-link ownership, Busy/Done/Aborted/Error, numeric
errors, captured timeout and atomic MW response mutation. It encodes and validates
FC1/2/3/4/5/6/15/16/23 with the limits above, big-endian registers and LSB-first
packed bits. Write replies must echo the request; partial/malformed responses and
invalid Modbus exceptions mutate no MW. Outgoing global-image words pass through
`read_word` so an indeterminate source cannot silently become wire data. Validated
receive words use `write_word`, recovering only overwritten word masks while
preserving S17/S18/SW17 and all unrelated cells. Canceled tokens are never polled again.
Active requests retain a copy of callbacks/context across global rebinding.
Context and functions must outlive their accepted transactions. Communication
instances are noncopyable identities and cancel unfinished raw work at destruction.
Storage is fixed by the253-byte PDU maximum,125 read words and two embedded links;
no private PLC MW reservation or retry/queue is introduced.

First TRUE creates no edge. Abort takes priority over polling and timeout while
Busy; timeout uses captured100ms units and zero disables expiry. Invalid effective
config gives6/0, occupied link255/11, missing/incomplete transport255/15, malformed
reply0/2 and valid Modbus exception254/exception code. SL1 WRITE id0 succeeds only
with explicit `BroadcastComplete`; a unicast request rejects that acknowledgement.
Terminal status remains while Execute is TRUE; if completion occurs with Execute
FALSE, it is visible for that invocation and cleared on the next idle FALSE call.
These are the currently admitted local VM policies, not proof of native timing.

The existing `detail::communication_hook` signature remains a deprecated explicit
status-provider compatibility path when no raw transport is installed; it is not
the independent engine. An already Busy legacy request retains its captured hook
and config until terminal completion even if either global hook/transport changes.
Raw transport takes precedence for subsequent work. Legacy callback I/O/state and
mixed-mode contention remain the provider's responsibility. Single-threaded scan
invocations are required; this does not add tasks, lifecycle scheduling, SEND/EXCH,
IOScanner or an external Modbus connection.

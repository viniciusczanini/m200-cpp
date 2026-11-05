# TM200CE40T — inventário de capacidades e limites

Auditoria somente de leitura, realizada em 2026-11-05. O inventário descreve capacidades documentadas do PLC e seus acessórios. Não comprova implementação do compilador C++, compatibilidade do XML/SMBP, aceitação pelo editor oficial ou funcionamento no PLC físico. Não houve escrita de firmware, transmissão de programas nem acionamento de I/O.

O JSON complementar é `/tmp/m200-hardware-capabilities.json`. Cada entrada possui ID estável, aplicabilidade, estado da evidência, campos de configuração e páginas oficiais. Os campos de configuração são nomes da interface oficial; **não são tags XML nativas comprovadas**.

## Fontes oficiais

P = EIO0000002019.06, Programming Guide; H = EIO0000002023.06, Hardware Guide; G = EIO0000003289.04, Generic Functions Library Guide; O = EIO0000003281.04, Operating Guide; C = DIA3ED2140906EN v10.0, catálogo de 2026-10-02.

Nos quatro manuais, página impressa = página PDF de base1. No catálogo, a seleção impressa6–7 corresponde à página PDF9, inspecionada visualmente. Os manuais locais foram fornecidos pelo estudo principal; o catálogo foi obtido diretamente do servidor Schneider.

- **PROG: EIO0000002019 v06** — [Modicon M100/M200 Logic Controller — Programming Guide](https://www.se.com/ww/en/download/document/EIO0000002019/). SHA256 `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`.
- **HW: EIO0000002023 v06** — [Modicon M100/M200 Logic Controller — Hardware Guide](https://www.se.com/ww/en/download/document/EIO0000002023/). SHA256 `184dd6da7ae276d72e05e67a9640ed8ff3a4211b603bdca4c4b6c7aec597cd69`.
- **GEN: EIO0000003289 v04** — [EcoStruxure Machine Expert Basic — Generic Functions Library Guide](https://www.se.com/ww/en/download/document/EIO0000003289/). SHA256 `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`.
- **OPER: EIO0000003281 v04** — [EcoStruxure Machine Expert Basic — Operating Guide](https://www.se.com/ww/en/download/document/EIO0000003281/). SHA256 `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5`.
- **CAT: DIA3ED2140906EN v10.0** — [Modicon M200 Logic controllers for simple machines up to 196 I/O](https://www.se.com/my/en/download/document/DIA3ED2140906EN/). SHA256 `7f0ea63961360c15c3cf3e9781b47686ed20fe29b62aa6e6502d1fb1e5130c09`.

## Estado das capacidades

- **Documentada:** há suporte explícito no manual do M200 ou no catálogo oficial. Continua pendente a validação do compilador, editor e equipamento.
- **Opcional:** requer o cartucho, módulo de expansão ou dispositivo remoto declarado. Não é recurso embarcado disponível apenas porque um endereço foi aceito.
- **Não suportada no modelo:** exclusão explícita, como ausência de analógicos embarcados ou bits de controle de velocidade Ethernet marcados “not supported”.
- **Conflitante / desconhecida:** fontes oficiais divergem ou omitem a configuração necessária. Deve permanecer visível na matriz e falhar explicitamente na autoria ainda não implementada; não deve ser anunciada como implementada nem como impossível no hardware.

## Recursos embarcados e alocação

| IDs JSON | Capacidade do TM200CE40T | Limites, conflitos de recurso e campos | Fonte |
|---|---|---|---|
| `HW.DIGITAL_INPUTS` | 24 entradas digitais `%I0.0..23` | 24Vdc, sink/source; I0/I1/I6/I7 são HSC; I2..I5 são FC/evento/latch; I8..I23 regulares. | H15,20–21; P24,51–53 |
| `HW.DIGITAL_INPUT_FILTER` | Filtro integrador | No Filter /3ms /12ms; padrão3ms. Latch e evento exigem No Filter. | P52; H65 |
| `HW.DIGITAL_INPUT_LATCH` | Latch nas I2..I5 | Apenas borda de subida; pulso>=1ms; entregue no próximo scan; incompatível com filtro, evento e Run/Stop. | P52; H65–66 |
| `HW.RUN_STOP_INPUT` | Uma entrada Run/Stop adicional e chave física | Borda de subida solicita RUN, nível baixo força STOP. Exclusiva. Linha I16 da tabela H69 contradiz a frase “todos os inputs”; manter essa exceção pendente. | P32–33,52; H69,75–76 |
| `HW.DIGITAL_OUTPUTS` | 16 saídas transistor **source/PNP** `%Q0.0..15` | Q0/Q1 rápidas; Q2..Q15 regulares. 0,5A por saída regular. Grupos: Q0..3=2A, Q4..7=2A, Q8..15=4A. Em modo rápido H26 limita a50mA; não assumir0,5A a100kHz. | H15,25–27 |
| `HW.STATUS_ALARM_OUTPUT` | Uma saída de estado RUNNING | Escolha em Q0..Q7, exclusiva;1em RUNNING,0nos demais estados. | P54–55 |
| `HW.OUTPUT_FALLBACK` | Fallback0/1 ou Maintain values | Expert I/O tem regras próprias; PTO força0. Forcing não vale para HSC/PLS/PWM/PTO/FREQGEN. Ver conflito específico de HSC abaixo. | P35–37,55,175; H72 |
| `HW.FAST_COUNTER` | Quatro FC de5kHz | FC0=I2,FC1=I3,FC2=I4,FC3=I5. Up/Down;16ou32bits; presets0..65535/0..4294967295. IN,R,D,P/PD,V/VD. | H21,69; P169–171 |
| `HW.HSC` | Quatro canais monofásicos ou dois bifásicos |100kHz; HSC0=I0,HSC1=I6,HSC2=I1,HSC3=I7; bifásicos HSC0=(I0,I1),HSC1=(I6,I7). Pulse/Direction,CW/CCW,QuadratureX1/X2/X4.16/32bits; em X1 o limite32bits documentado é2147483647. | P61–68,172–176; H21 |
| `HW.HSC_AUX` | Preset/captura, thresholds e saídas reflexas | HSC0: presetI2,capturaI3,reflexosQ4/Q5. HSC1: presetI5,capturaI4,reflexosQ6/Q7. Ocupação de I2..I5 exclui FC/evento. Bifásico HSC0 exclui HSC2; bifásico HSC1 exclui HSC3. | P62–68; H69,71–72 |
| `HW.HSC_FREQUENCY_METER` | Dois medidores de frequência | HSC0/I0 e HSC1/I6; janela100ms ou1s;100Hz..100kHz. | P69,184–185 |
| `HW.PULSE_RESOURCES` | Dois recursos de pulsos em Q0/Q1 | Cada canal escolhe PLS/PWM/PTO/FREQGEN. Exclusão por pino, inclusive direção de PTO. CW/CCW de PTO0 ocupa Q0/Q1 e desativa PTO1. | P55–61,210,223; H71–72 |
| `HW.PLS` | Trem de pulsos50% | Configuração documentada:0,5Hz..10kHz; P0 para. N0=ilimitado; N16bits0..32767,N32bits0..2147483647. Troca de período no fim do período atual. H27 anuncia100kHz, divergindo da configuração P187. | P57–58,185–188; H27 |
| `HW.PWM` | Dois PWM |1Hz..10kHz; duty0..100%, passo1%; P/R/IN; ratio>100 tratado100; P0 para. | P58,210–212; H27 |
| `HW.FREQGEN` | Dois geradores de frequência |0..100000Hz,passo1Hz,50%; ENABLE,SYNC,Freq,INFREQ,BUSY,ERROR,ErrorId. SYNC aplica sem aguardar fim do período; erro3002 para frequência inválida. | P24,61,291–293; H71 |
| `HW.PTO_AXIS` | Dois eixos independentes Pulse/Direction ou um CW/CCW |0..100kHz,passo1Hz; posição signed32; aceleração/desaceleração1..100000Hz/ms; perfil trapezoidal/S. Direção defaultQ2/Q3 ou outro Q disponível; Not used exige FL>=5.0. Não é prova de interpolação/coordenacão de eixos. | P59–60,223–226,240–241 |
| `HW.PTO_AUX_INPUTS` | REF/INDEX/PROBE específicos do CE40T | PTO0=I8/I9/I12;PTO1=I10/I11/I13. DriveReady,LimP,LimN,DriveEnable são atribuídos pela aplicação. Não copiar os pinos do modeloC16. | P60,224,240; H26,69 |
| `HW.PTO_HOME` | Homing, backlash e limites | Métodos0,1,20,21,22; offset signed32; backlash0..65535pulsos; movimento absoluto exige Homed. Limites de hardware fazem parte do funcionamento documentado do homing. | P228–230,241–248,267 |
| `HW.PTO_QUEUE` | Uma posição de buffer de movimento | Modos0aborting,1buffered,3blending,10trigger,11bufferedDelay. Stop/aborting/ErrorStop limpam fila. Não compartilhar instância entre tasks nem alterar AXIS executando. | P232,240,248,254 |
| `HW.PTO_MOTION_TABLES` | Sequência de até16passos | MoveAbs/Rel/Vel,Halt,SetPos; condição Done/InVel/blending/probe/SW/delay. Um probe por tabela; SW event avaliado a cada4ms; delay0em espera de evento significa sem timeout. | P232–236 |
| `HW.PTO_PARAMETER_ACCESS` | Acesso de parâmetros por número |1posiçãoR;2/3limitesRW;4/5enablelimitesRW;9maxvelRW;10velR;11velcomandadaR;13/15acel/desacelRW;1000delayRW;1004/1005direçõesRW. | P248–249,287–290 |

### Blocos de movimento PTO

Todos têm ID `HW.PTO_BLOCK.<NOME_EM_MAIÚSCULAS>`. São recursos documentados; a tabela não declara que o compilador já implementa seus estados assíncronos.

| Bloco | Função / restrição | Páginas P |
|---|---|---|
| MC_MotionTask_PTO | Executa uma tabela de movimento; até2instâncias. |25,255–257 |
| MC_Power_PTO | Habilita o eixo; obrigatório antes de mover. |25,258–260 |
| MC_MoveVel_PTO | Movimento contínuo a velocidade comandada. |25,261–263 |
| MC_MoveRel_PTO | Distância incremental. |25,264–266 |
| MC_MoveAbs_PTO | Posição absoluta; exige eixo referenciado. |25,267–269 |
| MC_Home_PTO | Referenciamento. |25,270–271 |
| MC_SetPos_PTO | Modifica coordenada sem movimento físico. |272 |
| MC_Stop_PTO | Para e entra em Stopping; aborta movimento. |273–274 |
| MC_Halt_PTO | Desacelera a zero e volta a Standstill. |275–277 |
| MC_ReadActVel_PTO | Lê velocidade. |25,277–278 |
| MC_ReadActPos_PTO | Lê posição. |25,278–279 |
| MC_ReadSts_PTO | Estado do eixo. |25,279–281 |
| MC_ReadMotionState_PTO | Estado de movimento. |25,281–282 |
| MC_ReadAxisError_PTO | Erro do eixo. |25,282–283 |
| MC_Reset_PTO | Reset de erros quando permitido. |25,283–284 |
| MC_TouchProbe_PTO | Ativa captura/trigger do probe. |25,284–286 |
| MC_AbortTrigger_PTO | Aborta trigger. |25,286–287 |
| MC_ReadPar_PTO | Lê parâmetro. |25,287–289 |
| MC_WritePar_PTO | Escreve parâmetro. |25,289–290 |

P25 lista86instâncias para Power/MoveVel/MoveRel/MoveAbs/Home e40para os blocos administrativos. Não lista máximo específico para SetPos/Stop/Halt: esse máximo ficou **desconhecido**, sem extrapolação.

## Analógicos, cartuchos e expansão

**O CE40T não possui analógicos embarcados** (P24). Possui dois slots de cartucho e aceita até quatro módulos locais TM3/TM3R/TM2. O orçamento do barramento é360mA a5V e320mA a24V; TM2 não pode vir antes de TM3/TM3R (H17–18). O tipo exato de módulo deve ser declarado e validado com seu próprio manual; suporte à família não autoriza todos os acessórios TM3.

Endereços de cartucho: `%I0.x0y`, `%Q0.x0y`, `%IW0.x0y`, `%QW0.x0y`; x=slot1/2,y=canal. Exemplo P22: `%IW0.101` é entrada analógica1do cartucho1. Status por canal: `%IWS0.x0y`/`%QWS0.x0y`. Expansão usa índice de módulo1..4.

| ID | Acessório opcional | Características / campos | Fonte |
|---|---|---|---|
| `HW.CARTRIDGE_DIGITAL` | TMCR2DM4U |2DI+2DO **sink**,0,5A; não herda a lógica source do controlador. | H27–29; P78 |
| `HW.CARTRIDGE_AI2` | TMCR2AI2 |2AI12bits;0..10V,0..20mA,4..20mA;10ms/canal; escala signed16; Type,Scope,Min/Max,Filter,Filter Unit. | H30–31; P78–79 |
| `HW.CARTRIDGE_AQ2V` | TMCR2AQ2V |2AO12bits,0..10V,carga>2kΩ; conversão20ms/transferência40ms; escala e fallback. | H31–33; P80–81 |
| `HW.CARTRIDGE_AQ2C` | TMCR2AQ2C |2AO12bits,4..20mA,carga<500Ω; conversão20ms/transferência40ms. | H33–34; P79–80 |
| `HW.CARTRIDGE_AM3` | TMCR2AM3 |2AI+1AO16bits;0..5V,0..10V,0..20mA,4..20mA; Filter0..6. Isolado da lógica, AI/AO não isolados entre si. | H34–37; P81–83 |
| `HW.CARTRIDGE_TI2` | TMCR2TI2 |2TC/RTD3fios; TC K/J/R/S/B/E/T/N/C; RTD PT100/PT1000/NI100/NI1000.125ms/canalTC,250ms/canalRTD. Resolução nominal14bits, passos reais dependem do sensor. | H37–39; P83–85 |
| `HW.SERIAL_OPTIONAL` | TMCR2SL1 | Uma porta RS232 ou RS485, não isolada;1200..115200bps. | H39–40; P85–89 |
| `HW.SERIAL_OPTIONAL` | TMCR2SL1A | Uma RS485 isolada;1200..115200bps. | H40–41; P90–93 |
| `HW.SERIAL_OPTIONAL` | TMCR2SL1S | Uma RS485 isolada; FL>=12.1;1200..115200bps. | H42–43; P74–75,94–97 |
| `HW.CARTRIDGE_SLOTS` | Combinações | Legado: um SL1 ou SL1A. FL>=12.1: SL1A+SL1S ou2×SL1S permite duas portas adicionais. Dois SL1/SL1A não autorizados. O catálogo mantém regra antiga de um serial; ver conflito. | P75 |
| `HW.ANALOG_DIAGNOSTICS` | Status por canal | Input0normal,1conversão,2init,3config,5alto,6baixo,7flash; output0normal,2init,3config,7flash. Status de módulos externos pode ter códigos diferentes. | P97–98,109–110 |
| `HW.EXPANSION_BUS_ERRORS` | Tratamento do barramento | S106=0default:2ciclos falhos causam bus off e TM3outputs0. S106=1: TM3mantém~10s;TM2mantém indefinidamente. Restart risingS107 com condições SW118/SW120. | P70–72,335 |

O JSON contém as faixas de temperatura por sensor. TI2 escala usualmente0,1°C/°F; B/C em Fahrenheit usam0,2°F. AM3 suporta tensão **e corrente**, apesar do resumo P74 dizer apenas tensão.

## Comunicação

| IDs | Capacidade | Limites e configuração | Fonte |
|---|---|---|---|
| `HW.ETHERNET` | Uma Ethernet RJ45 |10/100Mbps,autonegociação,MDI/MDIX. ModbusTCPcliente/servidor/slave mapping,programação/monitoramento. Security Parameters habilitam programação,descoberta e Modbus. | H129–130; P111–116 |
| `HW.ETHERNET_ADDRESSING` | Fixed/DHCP/BOOTP |0.0.0.0gera10.10.últimos2bytesMAC. Duplicação também usa fallback,SW118bit9/SW62. SW33..38+S33 para configuração em execução. | P113–115,329,334 |
| `HW.ETHERNET_RATE_OVERRIDE` | **Não suportado** forçar speed/duplex/autoneg via S34..36 | P323 marca esses três bits “not supported”; Transfer Rate é Auto somente leitura. | P114,323 |
| `HW.MODBUS_TCP_CONNECTIONS` |8conexões servidor,1cliente |16remotos configuráveis não significam16clientes TCP simultâneos. Excesso fecha a conexão mais antiga, preservando o editor. | P112,118–119,338 |
| `HW.MODBUS_TCP_MAPPING` | Mapeamento separado | FL>=3.2;UnitID1..247;1..20 `%IWM` recebidos e `%QWM` enviados,padrão10cada. UnitID diferente retorna `%MW` comum sem erro. FC3lêQWM,4lêIWM,6/16escreveIWM,23lêQWM/escreveIWM. | P117–118,136,215–216 |
| `HW.MODBUS_SERIAL` | SL1 RS485 embarcada **não isolada** |1200..115200bps; padrão19200,Even,8,1; RTU/ASCII master/slave ou ASCII; endereço1..247; polarização opcional. Hardware informa **sem5V**. | H132–133; P124–128 |
| `HW.MODBUS_FUNCTION_CODES` | Operações do servidor serial | FC1/2=%M,3/4=%MW,5,6,8(sub0,10..18),15,16,23,43/14. MapeamentoTCP tem subset e semântica própria. | P134–136 |
| `HW.MODBUS_IOSCANNER` | Um único IOScanner global | Serial **ou** Ethernet;16devices;20init/device;10channels/device. FL>=6.0paraTCP e512objetos; níveis anteriores128. Init precisa ser reconhecida antes dos dados cíclicos. | P116,118–124,128–136 |
| `HW.MODBUS_IOSCANNER_LIMITS` | Payloads por função | Leitura bits128;words125. Escrita bits128;words123. FC23:125read/121write. Ciclo1..6000×10ms;padrão200ms; também trigger rising%M. Política de erro0ou retain last. | P121,123,131,133–135 |
| `HW.COMM_READ_VAR` | Leitura ModbusSL/TCP | FC3/2/1/4;125words ou2000bits; FirstObj0..65535; buffer%MWvalidado por completo. | G171–177 |
| `HW.COMM_WRITE_VAR` | Escrita ModbusSL/TCP | FC16até123words,FC15até1968bits; FC5/6single exigeFL>=5.0. ID0broadcast sem resposta. | G177–182 |
| `HW.COMM_WRITE_READ_VAR` | FC23/0x17 read/write | Até121wordswrite e125read. P185usa “17” sem indicarhex; não implementar FC17decimal. | G182–187; P135 |
| `HW.COMM_SEND_RECV_MSG` | ASCIIserial | Send/receive0..255bytes;send0=receive-only,recv0=send-only. SizeRecvBuffer não é condição de fim. Comprimento/silêncio/caracteres configuram fim. | G187–192; P128 |
| `HW.COMM_EXCH` | EXCH1/2/3/4 | SL1/SL2/Ethernet/SL3 conforme presença; compartilha recurso por porta com FBs; diagnósticosSW63..66. | G171; P331–332 |
| `HW.ATV_BLOCK.*` | Sete FBs para Altivar remoto | Power,Jog,MoveVel,Stop,ReadStatus,ReadMotionState,Reset. Até16instâncias de cada; `%DRV0..15`; scanner configurado; FC23transfereregistros. Não ocupa PTO embarcado. | P189–207 |
| `HW.ETHERNET_IP_ADAPTER` | **Anunciado, configuração desconhecida** | Catálogo oficial v10listaEtherNet/IPadapter noCE40T. P112não lista o serviço, masSW190..206contém Class1/Class3/assembly. Não foram encontrados EDS,assemblysizes,RPI ou configuração nativa. Preservar como pendente; não chamar de “hardware incompatível”. | C PDF9/impressa6–7; P112,338–339 |
| `HW.OTHER_NETWORK_PROTOCOLS` | Desconhecidos | RawTCP/UDP,OPCUA,MQTT,HTTP,CANopen,PROFINET,EtherCAT e EtherNet/IPscanner não foram estabelecidos pelas fontes revisadas. Ausência no estudo não prova impossibilidade em firmware futuro. | P112,124; H129,132 |
| `HW.USB_PROGRAMMING` | USBMini-Bdevice paraPC | Programação/manutenção; não é USBhost nem porta genérica de periféricos. | H130–131 |

FBs de comunicação compartilham semântica Execute/Abort por borda, Busy/Done/Aborted/Error, CommError/OperError. TRUE no primeiro ciclo RUN não conta como borda: deve observarFALSE antes. Timeout em unidades100ms,padrão100=10s,0sem timeout. Apenas uma operação ativa FB/EXCH por porta. Quantidade de READ/WRITE/WRITE_READ:16por tipo atéFL<10.1 e32emFL>=10.1 (P25,G171–185). SEND_RECVtem16instâncias.

IOScanner endereça `%IN/%QN/%IWN/%QWN a.b.c`: a=100+deviceSL1,200+deviceSL2,300+deviceETH1,400+deviceSL3;b=channel;c=objeto. `%IWNSa`/`%IWNSa.b` fornece diagnóstico. SW210/211/213/212 são estados SL1/SL2/SL3/ETH1, com0stopped,1init,2operational,3partial,4suspended. Reset e suspend constam no JSON.

## RTC, memória, SD e execução

| IDs | Capacidade / limite | Fonte |
|---|---|---|
| `HW.RTC` | RTC embarcado exige bateria TMARBAT1 adquirida separadamente; BR2032; drift<90s/mês a25°C;backup>=3anos. Dois FBsRTC;FL>=5.0. RD+WRsimultâneo erro256;S50ativoerro257. | H79–81; P25; G163–166 |
| `HW.RTC_SYSTEM_WORDS` | SW49weekday,SW50seconds,SW51HHMM,SW52MMDD,SW53CCYYemBCD. S50=1permite editar; borda1→0aplica. S51timeinvalid,S52writeerror;SW59/S59ajuste,SW60correção. | P324,330–331 |
| `HW.RTC_SCHEDULE` |16blocos `%SCH`, habilitaçãoSW114(defaultFFFF);calendário/dias/horários e bit de saída. | P25,334; G158–162 |
| `HW.PERSISTENT_AUTO` | Salva automaticamente na queda de energia `%MW0..2999` e `%M0..499`; restaura mesmo sem bateria. Novo download,INIT ouS0reinicializa. Não reter silenciosamente os8000words. | P33–34 |
| `HW.PERSISTENT_REQUEST` | S90selecionaNVM/SD;S91erase,S93save,S94restore,S92available;SW148count. NVMsolicitadaM200=MW3000..4999;SDpode salvar todos desdeMW0. Erase remove o conjunto inteiro. SW147resultadoSD. | P34–35,325,337 |
| `HW.SD` | MicroSD/SDHC,FAT/FAT32; H79max32GB(conflitaP13764GB);classes4..10. Acesso segundo hardware somenteSTOP. Inserção emRUNnão executa. Não é prova de API de filesystem live ou datalogger. | H76–79; P34,137–138 |
| `HW.SD_FILE_LAYOUT` | `/Script.cmd`,`/Script.log`,`/sys/os/M200M100.mfw`,`/TM3/TM3_Ana.mfw`,`/usr/app/*.smbk`,`/usr/cfg/Machine.cfg`,`/usr/mem/Memories.csv`,`/sys/log/PlcLog.csv`. `.smbp` é projetoPC; não equivale a aplicação `.smbk` pronta paraPLC. | P138–160 |
| `HW.POST_CONFIGURATION` | `Machine.cfg` usa `channel.parameter=value`,case-sensitive,ANSI,#comentário. ETH:IPMODE/IP/MASK/GATEWAY/NETWORKNAME. SLn:HW/BAUDS/PARITY/DATAFORMAT/STOPBIT/MODBUSADDR/POLARIZATION. SL1.HWdeve1(RS485). | P38–40; H77 |
| `HW.TASKS` | Uma master(normal/periodic1..150ms),uma periodic1..255ms,até8eventos(4inputsI2..5+4thresholdsHSC).1ms exigeFL>=5.0. Prioridade evento>periodic>master;evento0mais alta..7mais baixa,todasúnicas. Eventtask só permiteI/Oembarcado. | P26–28; O57,88–90 |
| `HW.WATCHDOG` | Watchdog aplicação10..500ms emSW11; watchdogCPU>80% levaHALTED/S11. S19overrun de período separado. SW30..32ms eSW70..72restoµs;SW75CPU. Testes host não comprovam timingPLC. | P27,33,322–323,328–332 |
| `HW.EVENT_QUEUE_CONTROL` | S38permite enfileirar; profundidade da fila não verificada. Tempos/contadores nosSW39..48,130..138,149..166. | P323,330,336–338 |
| `HW.DIAGNOSTICS` | Estado,firmware,ID,serial,assinatura,barramento,cartuchos,overload,logs e contadores de rede. Respeitar campos readonly; não tratar todoSWcomo memória gravável. | P321–340 |
| `HW.PID_PROCESS_CONTROL` | Até14PID; cálculo não cria AI/AO físico. Semântica completa/autotuning depende do Advanced Functions Library Guide não incluído neste estudo. | P25; G166 |

## Divergências que precisam continuar visíveis

| ID de conflito | Evidências oficiais | Tratamento proposto |
|---|---|---|
| `CF.PLS_FREQUENCY` | H27:PLS100kHz;P187:configmáxima10kHz | Limitar autoria documentada a10kHz;100kHzPLS pendente de editor/PLC. |
| `CF.PLS_DUTY` | P185:50%fixo;P187:linhaPLS.RparecePWM | Preservar50%até evidência executável do editor. |
| `CF.FAST_OUTPUT_CURRENT` | H26:50mArápido;P225/240:200mA | Usar limite elétrico50mA conservador, confirmar fisicamente. |
| `CF.SD_CAPACITY` | H79:32GB;P137:64GB | Teto32GB até confirmação. |
| `CF.SD_RUN_ACCESS` | H76–77:STOP;P34:pedidosSDporS93/S94 | Não prometer acessoRUN; modelar restrição e estado pendente. |
| `CF.SERIAL_CARTRIDGE_COUNT` | P75:SL1S+SL1Aou2SL1SnoFL12.1;C9umserial | Aplicar gate de funcionalidade; catálogo tem regra anterior. |
| `CF.AM3_SIGNAL_TYPES` | P74:tensão;P81–83/H35–37:tensão/corrente | Descrição detalhada e hardware prevalecem. |
| `CF.AI2_FILTER_RESOLUTION` | H31:10ms;P79:100ms | Gerar configuração documentada em100ms. |
| `CF.ETHERNET_IP_ADAPTER` | C9:adapter;P112sem seção;SW190..206CIP | Documentado em catálogo, autoria/configuração desconhecida. |
| `CF.RS485_5V` | H132:sem5V;C9com5V | Não depender de alimentação5V nessa porta. |
| `CF.ETHERNET_RATE_BITS` | P323não suportado;H130dizreinit | Rejeitar S34..36como controle suportado. |
| `CF.HSC_FALLBACK` | P37expert0;P175reflexo depende configuração | Manter caso específico pendente e preservar configuração. |
| `CF.MASTER_DEFAULT_PERIOD` | P26padrão10ms;O57padrão100ms | Exigir período explícito. |

## Recomendações para implementação e testes locais

1. Manter separadas seis evidências: capacidade física documentada, parser/C++ aceito, lowering IL implementado, configuração nativa serializada, editor oficial aceitou, PLC físico validado. Uma tabela “supported=true” não representa essas seis situações.
2. Criar alocador de recursos por modelo: todos os pares de conflitos de pino, funções rápidas, direçãoPTO, REF/INDEX/PROBE, alarm e reflexos. Exigir cartucho/módulo antes de aceitar endereço analógico ou expansão.
3. Testar limites e valores imediatamente fora deles: pinos finais, ranges16/32bits, períodosPWM/PLS,count0,Freq0/100000,posição signed32,FLgates,4módulos e budget5V/24V. Validar final de buffers%MW e empacotamento de bits/bytes.
4. Modelar estados assíncronos de comunicação/movimento, bordas Execute/Abort, contenção por porta, filaPTOde uma posição, Homed,ErrorStop,Stop/Halt,timeout,resposta atrasada e políticas zero/retain-last do scanner.
5. Testar retenção por região e por evento, calendário/BCD/ano bissexto, RTCerro256/257, estadosSTOP/SD e watchdog/overrun distintos. Não promover timing do host a timing doPLC.
6. Preservar configuração nativa desconhecida de forma opaca e falhar explicitamente ao tentar criá-la sem esquema comprovado. Quando Windows estiver disponível, gerar fixtures no Machine Expert Basic para cada família, verificar compilação oficial e só depois executar bancada autorizada com cargas desconectadas.

O JSON inclui a matriz de testes e os campos detalhados. Este estudo não cria nem executa CI remoto.

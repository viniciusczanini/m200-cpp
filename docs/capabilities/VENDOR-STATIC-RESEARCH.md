# Pesquisa estática oficial Schneider — 2026-11-05

## Resultado

Foi possível obter um projeto SMBP autêntico publicado pela Schneider, sem login, e inspecionar seu XML no macOS. Não foi encontrado um instalador/pacote do editor oficialmente público sem cadastro nos três caminhos concretos verificados. Não houve download de EXE/DLL, execução de arquivo do fornecedor, instalação, modificação do sistema, Git, produção ou controlador.

AGENTS.md, docs/PARITY.md e docs/MODBUS.md de `/Users/tommy/Offline/projects/m200-cpp` foram lidos. O projeto encontrado continua sendo **TM221CE24R**, sem alteração de bytes/CPU. Ele fornece evidência de serialização, não um template TM200CE40T ou validação no editor.

## Instaladores oficiais verificados

| Página oficial | Arquivo | Tamanho anunciado | checkSum do HTML, algoritmo não especificado |
|---|---|---|---|
| https://www.se.com/us/en/download/document/MachineExpertBasicV1_4/ | MachineExpertBasic_V1.4_Build484.exe | 695.3 MB | 9ab5b91f333d6c5b76a899249aa7de7c |
| https://www.se.com/in/en/download/document/MachineExpertBasicV1_3/ | MachineExpertBasic_V1.3_build 215.exe | 582.4 MB | bcf1b4e466287e04b77eac0c3a4f5ece |
| https://www.se.com/us/en/download/document/MachineExpertBasic_V1_2_SP1_P1/ | MachineExpertBasic_V1.2_SP1_Patch1_build65760.zip | 802.9 MB | 0e4ce1d311b3e59dd5242c8e592a71f6 |

Em todas as três páginas, os arquivos têm `audience.label=Registered`, URL `https://download.se.com/private/files?...`, e o botão anuncia `Log in or create account`. As release notes associadas também estão marcadas Registered. Por isso, nenhum arquivo desses foi solicitado ao endpoint de download; não houve tentativa de remover `/private`, reutilizar cookies, credenciais ou contornar o requisito de cadastro. Os checksums acima são metadados do fornecedor, **não hashes calculados de pacotes obtidos**. Os tamanhos são arredondados pelo site; não há tamanho exato confirmado do pacote.

Metadados completos, URLs exatas de cada arquivo, checksums e hashes das páginas salvas: `/tmp/m200-vendor-static/installer-page-metadata.json`. HTMLs originais: `download-v14.html`, `download-v13.html`, `download-v12sp1p1.html` no mesmo diretório.

O FAQ oficial https://www.se.com/uk/en/faqs/FA348569/ informa que SoMachine Basic 1.6 SP2 deixou de estar disponível e foi sucedido pelo Machine Expert Basic. Não se usou mirror de terceiros nem Baidu. A pesquisa foi encerrada após esses caminhos e o exemplo público abaixo.

## Exemplo público oficial preservado

Página oficial: https://www.se.com/uk/en/faqs/FA361549/

Título: How do you setup an ATV Process drive with an M221 with Modbus TCP control.

Anexo identificado pela página como `_M10.4 IO Scanner Modbus TCP for ATVs (ETH_DIRECT).smbp` (246.49 KB).

URL pública, extraída diretamente dos metadados de anexos na página oficial:
https://se.my.site.com/ckmContent/sfc/servlet.shepherd/document/download/069Kj00000TaGRLIA3

HEAD sem credenciais: HTTP 200, Content-Length 252402, Content-Disposition de SMBP. Nenhum redirecionamento para login. O corpo foi então baixado sem cookies/credenciais e analisado apenas como XML.

- Arquivo: `/tmp/m200-vendor-static/official-atv-eth-direct.smbp`
- Bytes: **252402**
- SHA256: **9c992fedd4ad6d0fdf73e85d5e05edbaa2536cfe6257261e2eb3d0d9c4493bf4**
- CPU declarada: **TM221CE24R**
- Raiz: `ProjectDescriptor`
- ProjectVersion: `2.7.0.0`
- ManagementLevel: `FunctLevelMan18_0`
- Namespaces XML Schema e XML Schema Instance são declarados; **não há schemaLocation nem referência .xsd**.

Página de origem preservada: `/tmp/m200-vendor-static/faq-FA361549.html`; cabeçalhos HEAD: `atv-example-headers.txt`.

## O que o XML comprova

O projeto contém `LadderElements/LadderEntity` e `InstructionLines/InstructionLineEntity/InstructionLine` no mesmo `RungEntity`. Um bloco ATV real usa a sequência IL `BLK %MC_POWER_ATV0`, `LD 1`, `AND %M0`, `ENABLE`, `OUT_BLK`, leitura de `STATUS`/`ERROR`, e `END_BLK`. `IsLadderSelected=true` está presente. Isso é evidência estática da representação publicada, sem afirmar que um artefato gerado pelo nosso exportador será aceito.

`SoftwareConfiguration/FunctionBlocks/IFunctionBlock` contém sete tipos completos em atributos `Type`:

- McJogAtv
- McMoveVelocityAtv
- McPowerAtv
- McReadMotionStateAtv
- McReadStatusAtv
- McResetAtv
- McStopAtv

Todos sob `SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.Drive`, assembly `SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07`.

Os parâmetros `Axis` usam `FbParameterElementEnumType<DriveAxis>` com `<Value><DriveAxis>DRV0</DriveAxis></Value>`. `Vel` usa `FbParameterElementRangeType<System.Int16>` e `<Value><short>...</short></Value>`. A identidade de `System.Int16` cita `mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089`.

As nove strings `Type` completas, inclusive nomes genéricos serializados .NET, estão em `/tmp/m200-vendor-static/official-atv-dotnet-types.txt`; todos os endereços, parâmetros, tipos de elemento Ladder e seções estão em `official-atv-evidence.json`. **Nenhuma DLL/assembly foi obtida ou carregada.** Os nomes vêm exclusivamente do XML oficial.

Valores observados no exemplo: FastTask Period=255; MastTask UsePeriodScanMode=false, PeriodScan=100; StartingMode=StartAsPreviousState; AutoSaveRamOnEeprom=true; WatchdogPeriod=250. São **configuração desse exemplo**, não defaults universais nem defaults de TM200CE40T.

## Conferência das lacunas de docs/MODBUS.md

| Recurso procurado | Evidência no exemplo |
|---|---|
| WRITE_READ_VAR gráfico | Ausente. Só existe `WriteReadVarBasicMax=32` no TechnicalConfiguration da CPU estrangeira; não comprova layout gráfico/instância. |
| READ_VAR/WRITE_VAR enums bits/Single | Ausentes. `IoScannerInitRequestAccessWriteSingleRegister` existe em AccessType de inicialização do IO Scanner; pertence a outro domínio e não autoriza inventar enum de WriteVarBasic. |
| ABORT gráfico de comunicação | Ausente. `CMDABORTED` é saída dos blocos de movimento ATV; não é pino ABORT de READ_VAR/WRITE_VAR. |
| Base Timer10ms | Ausente; `Timers` está vazio. `TraceTimeBase=Time5Sec` não é base de timer. |
| PID e contadores nativos | `Pids`, `Counters` e `FastCounters` vazios. Máximos técnicos e símbolos de sistema não comprovam instâncias/defaults. |
| Operandos indexados nativos | Nenhum InstructionLine com operando `%...[%...]`; ocorrências textuais de indexed em comentários de sistema não comprovam sintaxe. |
| Outros blocos/tipos .NET | Sete classes ATV e wrappers de enum/Int16, como acima. |

Os limites técnicos desse TM221CE24R não foram promovidos a limites do alvo TM200CE40T.

## ManagementLevel: conclusão explícita

A única associação comprovada por este artefato é **TM221CE24R / ProjectVersion 2.7.0.0 / token FunctLevelMan18_0**. O arquivo não contém o nível funcional apresentado na interface, nem tabela de conversão entre tokens e versões. Portanto, **não foi comprovado que N_N em FunctLevelManN_N seja numericamente o nível funcional documentado**. Não há evidência nova para mapear FunctLevelMan11_0, FunctLevelMan18_0 ou outros tokens a 10.1/11.0/18.0 da documentação. Não é válido derivar esse mapa apenas pelo nome do enum, pela data do arquivo ou por ProjectVersion.

## Pendências e caminho concreto

Para extrair templates, XSD, recursos ou tabelas/enums de assemblies do instalador, ainda é necessário um pacote obtido legitimamente fora do fluxo de cadastro vedado nesta pesquisa, ou fornecido pelo usuário. A inspeção deverá permanecer estática. Mesmo que tais recursos sejam encontrados, continua necessário abrir, compilar, visualizar, salvar e reabrir os bytes exatos no editor e testar o hardware quando a semântica depender dele.

Não houve build/testes do repositório porque esta subtarefa não modificou código. A verificação realizada foi HTTP público, tamanho/hash, parse XML, inventário de elementos/atributos e conferência das lacunas. Não houve comprovação de aceitação no editor, simulação oficial ou execução no TM200CE40T.

## Preservação no projeto

O SMBP oficial e as evidências selecionadas foram preservados em `research/downloads/vendor-static`. O manifesto recuperável está em `docs/capabilities/VENDOR-STATIC-SOURCES.json`. Os caminhos /tmp acima descrevem a pesquisa original; os dados baixados ficam fora do Git.

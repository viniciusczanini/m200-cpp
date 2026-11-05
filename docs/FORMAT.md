# Formato e evidência

O guia Schneider EIO0000003281.04 documenta `.smbp` como projeto e a reversibilidade IL/Ladder, incluindo restrições de blocos. Não foi localizado um XSD público suficiente para conferir sozinho todos os requisitos do editor. O backend atual é experimental.

O leitor/escritor foi baseado em propriedades observadas em arquivos originais públicos e na documentação, sem incorporar programas de terceiros. `ProjectDescriptor`, `SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity`, `InstructionLines/InstructionLineEntity` e `LadderElements/LadderEntity` foram observados diretamente. Metadados de layout e enumerações não equivalem a um contrato oficial estável.

Bases de timer observadas: `OneMilliSeconds`, `OneHundredMilliSeconds`, `OneSecond`; a base padrão de um minuto está documentada e pode ser omitida em projetos existentes. `Type` usa `TON`, `TOF` e `TP`. A enumeração de 10 ms não foi confirmada nesta pesquisa e não é inventada pelo exportador.

As regras do parser são deliberadamente conservadoras. IL e gráficos presentes precisam concordar no subconjunto implementado; os comentários não são utilizados como fonte de lógica. Programas sem gráficos só são aceitos como rungs IL, não como Ladder selecionado. Cada importação continua identificada como não validada no editor, mesmo que tenha sido produzida por ele.

Fontes primárias consultadas em 2026-11-05:

- [Guia de operação do Machine Expert Basic](https://www.se.com/us/en/download/document/EIO0000003281/), especialmente reversibilidade, projetos e simulação.
- [Guia de programação M100/M200](https://www.se.com/id/en/download/document/EIO0000002019/), edição 06: limites, endereçamento, timers, memória e execução.
- [Guia de hardware](https://www.se.com/ph/en/download/document/EIO0000002023/), edição 06.
- [Machine Expert Basic V1.4](https://www.se.com/uk/en/download/document/MachineExpertBasicV1_4/), Build 484.
- [Arquivo original IL/Ladder](https://github.com/ss56/somachine-basic-programs/blob/master/counter%20and%20timer.smbp).
- [Arquivo original com timer TOF e base OneSecond](https://github.com/LiuYuancheng/Power_Generator_Manager/blob/75cf5666462cc2b5f4701209b8854d5c40ca6165/src/S1new_192_168_10_72.smbp).
- [Arquivo original com base OneMilliSeconds](https://github.com/Lawijayaaa/autolub/blob/main/PLC.smbp).
- [Arquivo original com base OneHundredMilliSeconds](https://github.com/dtmkeng/Embedded_System-3-2560/blob/master/PLC_getstart.smbp).
- [Clang AST](https://clang.llvm.org/docs/IntroductionToTheClangAST.html).
- [Apple Container machines, WWDC26](https://developer.apple.com/videos/play/wwdc2026/389/).
- [UTM: Windows 11](https://docs.getutm.app/guides/windows/).
- [Windows ARM: emulação de aplicativos e requisitos de drivers](https://learn.microsoft.com/en-us/windows/arm/faq).

Ainda é necessário obter um template autêntico do TM200CE40T e fazer o ciclo abrir → compilar → visualizar Ladder → salvar → reabrir no editor oficial. O firmware físico, a temporização real, os modos STOP/RUN e o comportamento em falta de energia permanecem sem comprovação.

## Extensão numérica (2026-11-05)

O backend numérico usa Operation/OperationExpression no término da linha (coluna 9, duas colunas, conexão Left) e Comparison/ComparisonExpression para contatos numéricos (duas colunas, Left, Right). Os campos contêm a expressão sem colchetes. A comparação entre gráfico e IL analisa os tokens; não remove espaços dentro de nomes/endereços. Operações inline `OPER [...]` vistas em outros projetos ainda não fazem parte deste importador.

A memória tem coleções MemoryWords/MemoryWord, MemoryDoubleWords/MemoryDoubleWord e MemoryFloats/MemoryFloat, com Address/Index/Symbol. O índice é o endereço word inicial, inclusive MD/MF. O exportador configura MemoryWordsMemoryAllocation como Manual/ForcedCount para cobrir o maior endereço utilizado; não inventa InitialValue nem enum Automatic específica dessa coleção. A inicialização do contrato C++ é lógica explícita em rungs de primeiro scan.

Evidência primária de autoria do formato, com commits fixados (projetos M221 do mesmo editor; não são templates CE40T):

- [Operation em equations.smbp](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/equations.smbp#L14-L95).
- [Comparison e alocação em demo3.smbp](https://github.com/wavestone-cdt/plc-code-security/blob/a7fc4f9aa395ccbf628e888918fb6281995901b9/icsjwg2022/plc_programs/demo3.smbp#L14-L102).
- [Memória double-word em simulation.smbp](https://github.com/wavestone-cdt/plc-code-security/blob/a7fc4f9aa395ccbf628e888918fb6281995901b9/dc30/PLC%20Programs%20examples/simulation.smbp#L2964-L2968).
- [Memória REAL em Program.smbp](https://github.com/afafirmansyah/automatic-tank-gauging/blob/0a32c0f49051d84e5c341dbcf5d9cb7160446c62/Program.smbp#L2211-L2220).

Proveniência, versões e localização dos excertos de esquema estão em docs/capabilities/FORMAT-EVIDENCE.json. A aritmética e seus operandos foram cruzados com EIO0000003289.04, pp49–72; casos ainda ambíguos são lacunas do catálogo. A existência desses nós em projetos públicos não comprova que o editor aceitará os arquivos gerados.

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

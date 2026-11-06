# Cobertura e lacunas

A meta é acessar todos os recursos realmente disponíveis no TM200CE40T pelo C++ restrito, com ida e volta para o editor. O inventário é uma base de rastreamento, não uma declaração de que essa meta foi atingida.

O critério final é a [equivalência funcional](../PARITY.md): qualquer algoritmo
aceito pelo software oficial para esse perfil deve ser expressível em C++.
Uma lacuna desta tabela não reduz esse requisito e não pode ser apresentada
como uma incapacidade do PLC. A alocação/reuso conservadores, o scan único e o
fluxo de controle ainda parcial precisam evoluir para isso. O alocador já usa
todo o banco, preserva globais/endereço explícito/buffers e considera saltos,
vida entre scans e a ordem das instruções dentro de cada rung; não é uma prova
de alocação ótima nem elimina todo overhead do compilador.

`instructions.json` registra 161 itens; `hardware.json` registra 89. São 250 registros, com sobreposição entre instrução e hardware, e não 250 funcionalidades independentes. Alguns descrevem ausência de recurso, como analógicos embarcados. Cada entrada conserva limites, requisitos de versão funcional, objetos/endereço, configuração, fontes/páginas e pontos de validação. `HARDWARE-AUDIT.md` explica os 13 conflitos encontrados entre documentos.

| Grupo | Implementado no protótipo | Ainda falta |
|---|---|---|
| Digital e estado booleano | I/O embarcado, memória M, gates, if/else, clocks, classes de borda e contatos nativos LDR/LDF/ANDR/ANDF/ORR/ORF/XORR/XORF em I0/M; RISINGn/FALLINGn no modelo local, APIs por identidade e expansão em M/gates; STN/N, MPS/MRD/MPP e grupos AND(/OR( em IL/VM/reversão, normalização para Ladder | XML raw de blocos/nível funcional, modificadores de parênteses restantes, fase/partida/repetição de bordas comprovadas, conflito MPS11/32, filtros/latch/reflexos, alarm/fallback, I/O imediato, mapa completo S/SW, retenção configurável |
| Numéricos | i16/i32/f32, 47 intrínsecos, INC/DEC em IL, comparações, MW/MD/MF compartilhada, MW:X e grupos packed M/I0/Q0 com portador16/32 e snapshot, API nativa indexada por MW com WordMemory/S20/reset, arrays contíguos com índice literal/calculado, S17/último bit de shift e S18/overflow inteiro sticky com reset e resultados modulares locais, XML Operation/Comparison, reversão; bits indexados em C++/IL/VM/reversão com BitMemory | XML de bits indexados (mapeamento FL10.0 sem prova), outros bancos de bits/sequências, atribuições nativas sobrepostas/desiguais sem prova, arrays multidimensionais, indexação constantes, demais flags numéricos/SW17 e recuperação de resultados indeterminados, confirmação física da política modular, demais operandos, operações/casos ambíguos, BCD/ASCII/strings/tabelas |
| Blocos | TON/TOF/TP, P/V/Q, modos locais retentivo TON/TOF e DynamicPreset TON/TOF/TP, identidade/base/opções explícitas e progresso interno sob saltos; classes de clock/borda; %C com P/V/E/D/F, R/S/CU/CD, configuração e modelo local provisório, reversão e Counter gráfico nativo e importação de branches/saídas puras com prova exata de portas/ordem, incluindo status BOOL de comunicação | Semântica física de %C (conflito E/interações/ciclo de vida), comparações/efeitos numéricos nos gráficos raw; XML dos modos true por mapeamento de nível funcional sem prova, ciclo de vida nativo e fase de ticks comprovados; contadores FC/HSC, registradores, drum/SBR/SC, RTC/schedule, PID e seus parâmetros |
| Hardware rápido | limites e conflitos de pinos documentados | configuração e execução de HSC, PWM/PLS/FREQGEN/PTO e blocos de movimento |
| Comunicação | ReadVar/WriteVar/WriteReadVar em C++/IL e modelo assíncrono; FC1/2/3/4/5/6/15/16/23; MBAP; TCP local; XML de READ/WRITE word e perfis de porta comprovados | demais enums/configurações XML, propriedades dinâmicas dos blocos, IOScanner, EXCH/MSG, serial ASCII/RTU físico, mapas específicos de servidor e EtherNet/IP; validação oficial |
| Expansão | cartuchos e TM2/TM3/TM3R documentados | perfil de configuração, tipos de I/O, conversões/calibração/diagnósticos e conflitos |
| Execução | scan mestre restrito, inicialização do contrato local, while/for/do, break/continue, goto/labels e JMP/JMPC/JMPCN reais em IL/VM/reversão; XML Jump/JMPC observado | demais estruturas/operadores C++, fluxo/chamadas completo, tarefas/eventos, prioridades, watchdog comprovado, subrotinas nativas, UDF/UDFB, Grafcet, STOP/RUN e retomadas |
| Projeto oficial | subconjunto XML, coerência gráfica, preservação do template e reversão; lógica nativa normalizada para rungs série; entradas Timer compostas/S/R e posições observadas conferidas com originais | template autêntico CE40T, enums restantes, schema real, abrir/compilar/salvar no editor oficial, simulador oficial e hardware |

Os estados normalizados por fase na API de catálogo começam conservadoramente em `missing` (frontend/IL/reversão/SMBP/local) e `pending` (editor/hardware). Eles não são promovidos por texto de pesquisa. O comando `capabilities` mostra separadamente a biblioteca implementada. A granularidade dos registros inclui famílias com muitos operandos/modos; um caso local funcionando não conclui a família toda. Não há porcentagem artificial de conclusão.

Para cada lacuna, a conclusão exige definir a API e o estado/configuração, emitir instrução e gráfico coerentes, recuperar C++ do programa real, testar limites e erros com referência independente, e obter a evidência externa correspondente. Periféricos assíncronos não devem ganhar stubs que retornam sucesso. Configurações/enums desconhecidos continuam recusados.

A falta atual de Windows/editor/PLC impede a garantia final solicitada. Não impede desenvolver as partes locais restantes; as pendências da tabela permanecem trabalho aberto. A base XML de timer de 10 ms ainda não foi confirmada em um projeto original e continua bloqueada na exportação.

Fontes oficiais centrais: [programação M100/M200](https://www.se.com/id/en/download/document/EIO0000002019/), [hardware](https://www.se.com/ph/en/download/document/EIO0000002023/), [funções genéricas](https://www.se.com/us/en/download/document/EIO0000003289/), [operação](https://www.se.com/us/en/download/document/EIO0000003281/). Os registros conservam versão e hash para evitar confundir edições futuras com as auditadas.

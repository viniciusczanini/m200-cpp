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
| Digital e estado booleano | I/O embarcado, memória M, gates, if/else, bordas, clocks | filtros/latch/reflexos, alarm/fallback, I/O imediato, mapa completo S/SW, retenção configurável |
| Numéricos | i16/i32/f32, 47 intrínsecos, INC/DEC em IL, comparações, MW/MD/MF compartilhada, API nativa indexada por MW com WordMemory/S20/reset, arrays fixos com índice literal, XML Operation/Comparison, reversão | array C++ com índice calculado/multidimensional, indexação bit/constantes, flags numéricos e recuperação completa, demais operandos, operações/casos ambíguos, BCD/ASCII/strings/tabelas |
| Blocos | TON/TOF/TP e classes de clock/borda | contadores C/FC/HSC, registradores, drum/SBR/SC, RTC/schedule, PID e seus parâmetros |
| Hardware rápido | limites e conflitos de pinos documentados | configuração e execução de HSC, PWM/PLS/FREQGEN/PTO e blocos de movimento |
| Comunicação | ReadVar/WriteVar/WriteReadVar em C++/IL e modelo assíncrono; FC1/2/3/4/5/6/15/16/23; MBAP; TCP local; XML de READ/WRITE word e perfis de porta comprovados | demais enums/configurações XML, propriedades dinâmicas dos blocos, IOScanner, EXCH/MSG, serial ASCII/RTU físico, mapas específicos de servidor e EtherNet/IP; validação oficial |
| Expansão | cartuchos e TM2/TM3/TM3R documentados | perfil de configuração, tipos de I/O, conversões/calibração/diagnósticos e conflitos |
| Execução | scan mestre restrito, inicialização do contrato local, while/for/do, break/continue, goto/labels e JMP/JMPC/JMPCN reais em IL/VM/reversão; XML Jump/JMPC observado | demais estruturas/operadores C++, fluxo/chamadas completo, tarefas/eventos, prioridades, watchdog comprovado, subrotinas nativas, UDF/UDFB, Grafcet, STOP/RUN e retomadas |
| Projeto oficial | subconjunto XML, coerência gráfica, preservação do template e reversão | template autêntico CE40T, enums restantes, schema real, abrir/compilar/salvar no editor oficial, simulador oficial e hardware |

Os estados normalizados por fase na API de catálogo começam conservadoramente em `missing` (frontend/IL/reversão/SMBP/local) e `pending` (editor/hardware). Eles não são promovidos por texto de pesquisa. O comando `capabilities` mostra separadamente a biblioteca implementada. A granularidade dos registros inclui famílias com muitos operandos/modos; um caso local funcionando não conclui a família toda. Não há porcentagem artificial de conclusão.

Para cada lacuna, a conclusão exige definir a API e o estado/configuração, emitir instrução e gráfico coerentes, recuperar C++ do programa real, testar limites e erros com referência independente, e obter a evidência externa correspondente. Periféricos assíncronos não devem ganhar stubs que retornam sucesso. Configurações/enums desconhecidos continuam recusados.

A falta atual de Windows/editor/PLC impede a garantia final solicitada. Não impede desenvolver as partes locais restantes; as pendências da tabela permanecem trabalho aberto. A base XML de timer de 10 ms ainda não foi confirmada em um projeto original e continua bloqueada na exportação.

Fontes oficiais centrais: [programação M100/M200](https://www.se.com/id/en/download/document/EIO0000002019/), [hardware](https://www.se.com/ph/en/download/document/EIO0000002023/), [funções genéricas](https://www.se.com/us/en/download/document/EIO0000003289/), [operação](https://www.se.com/us/en/download/document/EIO0000003281/). Os registros conservam versão e hash para evitar confundir edições futuras com as auditadas.

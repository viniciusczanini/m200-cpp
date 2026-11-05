# Validação futura no Windows

Estado: pendente. Este documento não registra resultados que ainda não aconteceram.

## Preparação por SSH

1. Identificar a versão/build do Windows, arquitetura, versão/build e caminho do Machine Expert Basic.
2. Confirmar como acessar uma sessão gráfica interativa. Um processo aberto pelo serviço SSH pode não aparecer na sessão do usuário; ausência de erro ao iniciar o EXE não comprova abertura ou compilação.
3. Registrar versão do firmware e nível funcional suportado pelo TM200CE40T quando o equipamento estiver acessível. Não atualizar firmware automaticamente.
4. Criar, no editor, um template vazio para TM200CE40T. Salvar, fechar, reabrir e compilar. Transferir o arquivo e seu SHA256 para o projeto.
5. Criar pequenos exemplos oficiais separados: entrada/saída, negação, AND, set/reset, TON, TOF, TP e todas as bases de tempo disponíveis. Capturar as propriedades padrão e os limites do editor. Não substituir um modelo diferente por edição textual.

## Primeiro teste, com o CLP desconectado

1. Gerar um projeto digital mínimo usando o template verdadeiro.
2. Calcular SHA256 dos arquivos e preservar o candidato original.
3. Abrir o candidato no editor. Registrar erros, avisos, reparos/migrações e modelo/nivel funcional mostrado.
4. Conferir que todos os rungs aparecem em Ladder e têm a mesma lógica da IL. Em particular, observar Timer na coluna 3, conexões, bobinas e metadados/alocações.
5. Compilar no editor e capturar a evidência visual/log disponível. Zero erro de XML não equivale a compilar.
6. Salvar uma cópia, fechar e reabrir. Converter a cópia de volta em C++, comparar IL/configuração e executar os testes nativos. Metadados do editor podem mudar; a lógica, a ordem e os endereços observáveis não podem ser descartados da comparação.
7. Repetir a abertura/compilação dos bytes finais que serão entregues e vincular a evidência a seu hash. Um manifesto editado à mão não substitui essa execução.

## Simulador oficial

Rodar as mesmas sequências de entradas/tempo do C++ de referência. Cobrir toggle, if/else, múltiplas atribuições, condição capturada antes de mudar estado, leitura da última escrita de saída, primeiro scan, reset/enable de timers, TON/TOF/TP, clock e bordas. Registrar diferenças de resolução, fase e jitter. Alguns objetos/periféricos não são simulados pelo software; não atribuir a eles validação simulada.

## Equipamento físico, em etapa separada

Após autorização para a sessão de teste física, usar o editor oficial para a transferência. Começar com as cargas isoladas e conferir I/O, RUN/STOP, tempos, reset e retomada de alimentação. O teste lógico local não comprova interface elétrica, correntes, proteções ou acionamento de cargas. A comunicação USB depende de drivers compatíveis com a arquitetura do Windows; Ethernet será verificada separadamente.

O teste deve ocorrer localmente na máquina Windows fornecida. Não criar GitHub Actions, CI ou uma pipeline remota. A presença de SSH não autoriza publicar alterações nem acionar equipamentos fora do ensaio combinado.

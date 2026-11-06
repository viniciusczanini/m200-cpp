# Revisão independente S17/S18

Base 86af2a3; revisão local do diff por integer_flags_review, seguida de revisão
específica do novo stress. Nenhuma edição pelo revisor. Sem achados acionáveis.

Foram examinados VM/modelo, frontend/lowering, fusão/alocação, normalização,
reversão, gráfico/XML e SDK. Foco em snapshots de flags antes/depois de efeitos,
ordem de avaliação, guardas/curto-circuito, clears exclusivos, persistência e
limites das operações.27 testes focados passaram no momento da primeira revisão.

Ensaios extras independentes do revisor: 48 expressões / 192 frames entre C++,
VM, normalização, reversão e recompilação; 17.952 operações do SDK com UBSan e
oracle independente. Na segunda revisão, 24.576 vetores do oracle de shifts
coincidiram com deslocamento de listas de bits, uma posição por vez. Esses
ensaios não fazem parte das contagens reproduzíveis finais de frames do stress.

A segunda revisão confirmou observação de todos os bits pelas tabelas,
captura dos flags antes e depois de clears, execução de cada amostra por par
de rodadas e cobertura exaustiva dos sete controles. Conferiu os oracles ALU,
carry, sticky S18 e laço público e a contagem 218 casos / 62.464 frames-base.
Os dez casos focados passaram; essa evidência foi distinguida da rodada integral.

O revisor não aprovou semântica física: política modular além do ADD word G55,
resultados indeterminados de DIV0/SQRT negativo, float/SW17, editor e PLC
continuam explicitamente pendentes. Biblioteca completa permanece false.

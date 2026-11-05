# Revisão de contatos de borda nativos — 2026-11-05

Diff após `292f5a2`; revisão independente em contexto novo e modo read-only.
Contrato: `../capabilities/NATIVE-EDGE-CONTACTS.md`. Escopo: gramática,
operandos, reservas, amostragem antes do CFG, SDK/hook, frontend, reversão,
normalização, gráficos e testes focados. Nenhum achado crítico, importante ou
menor de correção foi relatado no diff revisado.

Verificações adicionais do revisor, separadas do stress versionado:

- 1.500 programas aleatórios com todos os operadores de borda, lógica booleana
  e ST/STN/S/R em M/Q, total 45.000 scans: VM original e normalizada concordaram
  em saídas e células M explícitas.
- 30 programas com saltos condicionais para frente, total 600 scans únicos:
  VM original, normalizada, C++ reconstruído nativo e IL recompilada concordaram.
- `git diff --check` aprovado. Reproduções em diretórios temporários, sem
  editar o repositório, executar CI ou acessar PLC.

Esses 45.600 scans extras não entram nos totais da rodada reproduzível. A revisão
não julgou fase física de entradas, partida/retomada/retenção, aceitação oficial,
blocos RISINGn/FALLINGn ou modificadores de parênteses ainda não implementados.
A rodada integral e Task2 permaneciam sob verificação do implementador.

Antes da revisão, o implementador reproduziu e corrigiu colisão de nome de
helper não qualificado com `plc::input_rising`; regressão RED/GREEN:
`test_unqualified_helper_does_not_become_a_plc_edge_api`.

# Modos retentivo e preset dinâmico: contrato local

Etapa de 2026-11-05, base `12ab05b`. Meta integral em `../PARITY.md` permanece.
Fonte principal: Generic Functions EIO0000003289.04, pp. 108–118, mesmo hash
de `TIMER-PROPERTIES.md`. Diagramas 111/112/116 conferidos visualmente. A
[FAQ Schneider FA369738](https://www.se.com/us/en/faqs/FA369738/) (atualizada
15/01/2026, escopo explícito M221/Basic) confirma retenção para TON/TOF e
indisponibilidade para TP. O guia genérico associado ao M200 tem diagramas
retentivos apenas para TON/TOF; não se inventa TP retentivo.

## Contratos e política de tempo

- TON retentivo pausa em INfalse antes de terminar e retoma do V retido em
  INtrue. Depois de terminar, INfalse zera V/Q. TOF retentivo pausa em INtrue
  antes de terminar e retoma em INfalse; depois de terminar, INtrue zera V e
  põe Qtrue. Retenção aqui é pausa pelo IN, não retenção de alimentação/RUN.
- Dynamic Preset=true permite mudar P enquanto roda. O novo P é considerado
  na próxima atualização da base. Se V já é maior/igual, conclui mantendo o V
  atingido; os diagramas mostram V acima de P após redução, sem clamp para P.
- Com as duas opções, P estritamente menor que V enquanto pausado zera V;
  igualdade não dispara essa regra. No modo não dinâmico P segue capturado na
  próxima ativação, preservando o comportamento anterior.
- Modelo local: ticks relativos à ativação/resumo. A pausa retém unidades
  inteiras V; fração de tick não é retida. Escrita P primeiro processa ticks
  decorridos com P anterior e só afeta tick posterior à escrita. Depois de
  concluída, a ativação fica concluída até a transição de reinício, sem
  ressuscitar se P crescer. Essa fronteira após conclusão e a fase/fração
  real dos ticks ainda exigem ensaio no editor/PLC; não se alegam comprovadas.
- O progresso sob saltos e a distinção Q interno/saída ligada ao bloco são
  preservados. Erros de P continuam com a política explícita anterior.

## API, configuração e gates

`Ton/Tof/Pulse{index,base_ms,preset,retentive,dynamic_preset}` usa dois bools
literais. Construtores anteriores permanecem. TP com retentive=true falha
explicitamente. Timer JSON preserva campos bool, com false por omissão para
arquivos antigos; strings/números não são coerções válidas. Reversão conserva
os dois flags da configuração real, sem alterar endereços/base.

Retentive requer nível funcional 3.3 e Dynamic Preset 12.0. O original público
`06-correto.smbp` (manifesto pinado) contém TM3 retentivo, base 1 s/preset 2, CPU
TM200CE24R e token `FunctLevelMan13_0`; seus bytes/CPU são preservados. Ele
prova a serialização IsRetentive=true em outro M200, sem provar a relação
ordinal do token com nível funcional nem compatibilidade CE40T.

Por isso XML com qualquer opção true continua recusado antes de substituir
destino, enquanto o mapeamento de nível funcional estiver sem prova. O parser
lê os flags sem descartá-los e chega a esse gate explícito; não simula true
como false. JSON/IL com configuração/VM/SDK/reversão são os caminhos locais
exercitados. Isso é uma lacuna de exportação/perfil ainda aberta, não redução
da meta nem uma impossibilidade do PLC.

## Implementação e cobertura local

Os flags estão implementados no modelo/JSON, frontend, SDK, IL/VM e reversão.
`tests/test_timer_modes.py` contém 12 testes com sequências temporais explícitas, valores
retidos, igualdade P/V, escrita e leitura no mesmo instante, conclusão e
reinício, guardas/saltos, preservação dos flags e proteção do destino XML.
Os modos antigos sem flags continuam com defaults false.

O stress `tests/stress/timer_modes.py` usa um oráculo separado que processa
um evento por tick; não usa o estado de produção para gerar expectativas.
São 35 combinações de modo/base (cinco bases) e uma configuração real isolada,
com 512 scans cada. Compara C++ original/reverso, VM, JSON e recompilação, e
exige recusa do XML sem alterar um destino existente. O caso público usa
a configuração TM3 do original, com harness de entrada/observação construído
para o teste: não foi encontrada execução de TM3 nos rungs desse arquivo.
Isso não é ensaio do algoritmo integral do projeto original.

A revisão independente não encontrou falhas de correção no diff e executou
22 testes (modos/propriedades), 17 casos manuais e rejeições de XML malformado/
duplicado. As decisões de fase/fração do tick e P após conclusão permanecem
experimentais, mesmo com concordância entre referências locais.

O inventário CLI e `examples/timer_modes.cpp` expõem o uso local. A rodada
integrada e os hashes dos arquivos estão em
`../validation/TIMER-MODE-LOCAL-RESULTS.json` e
`../validation/TIMER-MODE-STRESS-RESULTS.json`. A meta final e todos os gates
externos continuam abertos.

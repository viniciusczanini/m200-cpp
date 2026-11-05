# Revisão de bits e sequências — 2026-11-05

Diff após `d8b3e 5a`, revisão independente do código/contrato em modo read-only.
Escopo: frontend, SDK, VM, reversão, normalização, XML, aliases, faixas, vida
de temporários e imagem de saída no scan. Nenhuma ação remota/PLC.

## Achado importante corrigido

`direct_bit_limit` contava `%M512:32` como limite 513 em vez de 544. Um acesso
posterior `%M0[%MW0]` com MW0=543 retornava false e acionava S20, embora M543
tivesse sido escrito true. A reversão emitia BitMemory513 e o SDK abortava.

`test_packed_extent_is_visible_to_indexed_bit_bounds` reproduziu `[False,True]`
antes da correção. O cálculo passou a usar `memory_bits_used`, incluindo a
região inteira. O mesmo teste passou com `[True,False]` na VM, C++ nativo e
IL recompilada. A rechecagem independente confirmou o reparo.

## Conferências adicionais

O revisor gerou 35 programas C++ determinísticos com 50 operações e 5 frames,
conferindo frontend/VM com SDK. Outros 35 programas IL com 40 operações e 4 frames
conferiram VM, normalização, C++ reverso e IL recompilada. Os casos combinaram
seletores, sequências, saídas e condições. Nenhum outro achado importante ou
crítico ficou aberto. Esses ensaios extras não entram na contagem do stress
reproduzível versionado.

Após o reforço do usuário sobre controle de portas, o mesmo revisor conferiu
a nova matriz de I/O: 48 casos cobrem todas as 768 ligações entrada/saída/polaridade,
com walking-one/zero; o caso condicional cobre as 32 combinações de seus 5 controles,
ordem, retenção e encaminhamento packed. Não houve achados importantes/críticos.
Outros 32 frames temporários verificaram trocas entre portas, leituras sequenciais
no mesmo scan e truncamento packed com fonte sobreposta, passando nas etapas
de comparação. Esses 32 frames extras também não entram no total versionado.

Isso verifica consistência local dos casos testados. O editor oficial e o
TM200CE40T físico continuam pendentes; a biblioteca integral não está completa.

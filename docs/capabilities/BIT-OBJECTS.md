# Bits de words e sequências de bits

Etapa após `d8b3e5a`, em 2026-11-05. Meta integral em `../PARITY.md`.
Fonte primária: [Generic Functions EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/), pp. 27/31/41/51–53. O PDF/hash é o já preservado no projeto.

## Contrato e escopo

- `%MWi:Xk` seleciona um dos 16 bits do word. Leituras/escritas usam o mesmo
  banco MW/MD/MF; escrever um bit preserva todos os outros. Não se inventa
  campo MD/MF:X nem se inclui SW/KW/IW/QW sem o respectivo perfil.
- Sequências são bits adjacentes de mesmo tipo, começando em fronteira de byte.
  Esta etapa cobre M e I0/Q0 embarcados, dentro de 1024/24/16 bits. Comprimento
  de 1–32, limitado também ao portador i16/i32 escolhido. Entradas são read-only.
- O primeiro bit da sequência corresponde ao bit0 do valor; leitura preenche
  bits altos com zero, interpretando o resultado no portador signed de 16/32bits.
  Escrita usa os bits baixos do portador e preserva os bits fora do destino.
- Atribuição nativa entre sequências exige tamanhos iguais. Sobreposição de
  regiões distintas e tamanhos diferentes ficam recusados até evidência da
  semântica nativa. A API explícita de cópia captura primeiro um valor packed
  e escreve depois, tornando sua política de snapshot independente de memcpy.
- Sequências aparecem apenas em atribuições, não são presumidas operandos
  aritméticos/comparações nativas. A biblioteca faz snapshot em word antes de
  usar essas operações. Indexados word/dword nas transferências preservam os
  contratos S20/limites anteriores.

## API e preservação

`read_word_bit(word,bit)` / `write_word_bit(word,bit,bool)`.
`read_m_bits_i16/i32(first,count)`, `read_input_bits_i16/i32`,
`read_output_bits_i16/i32`, `write_m_bits_i16/i32`,
`write_output_bits_i16/i32`; `copy_m_bits(destination,source,count)` faz snapshot.
Endereços/comprimentos são literais e os flags de valor respeitam o tipo.

Frontend reserva o word inteiro de um seletor e toda a região M de uma sequência,
inclusive escrita sem leitura. Normalização/resumo/alocação usam as mesmas
extensões, inclusive o limite usado por acessos indexados e na reversão.
A VM opera sobre os bancos existentes, não em memória paralela.
Leituras/escritas agrupadas de Q usam a imagem privada já existente do frontend,
enxergando escritas anteriores no mesmo scan. Snapshots tipados são montados
por seletores de bits dos words privados; esses views participam da análise
de vida do mesmo registro, sem tratar escrita parcial como definição integral.
Reversão usa os operandos/configuração reais e APIs tipadas, sem C++ em metadados.
Emissão XML usa contatos/coils e Operation já conhecidos; aceitação pelo editor
e execução física continuam pendentes, inclusive fronteiras/overlap não cobertos.

Originais preservados incluem `%MW2009:X0` em D do inventário de indexação e
`%MW0 := %I0.0:8` em `flow-original-loop.smbp`. O stress verifica o hash de cada
arquivo antes de extrair IL: rung1 inteiro do segundo; no primeiro, segmento
contíguo [2:8] do rung9, excluindo explicitamente MULTIFB/bloco Timer. Adaptadores
de entrada/observação são separados. CPU/bytes não são reescritos e não há
alegação de importação integral, execução de MULTIFB ou validação gráfica do original.
Para obter/verificar os originais fixados antes do stress, usar
`make public-flow-fetch public-indexed-fetch`; os downloads ficam ignorados pelo
Git e a conferência exige tamanho, SHA256 e Git blob SHA1 corretos.

`tests/stress/digital_io.py` cobre explicitamente as 24 entradas e 16 saídas:
todas as 768 ligações entrada/saída/polaridade em 48 casos, mais um caso de
retenção, condições, inversão e imagem agrupada no mesmo scan. São 12.800 ciclos
com referência separada e comparação C++/IL/JSON/normalização/reversão/XML.
Pode ser executado isoladamente por `make digital-io-stress`; o alvo `stress`
também o inclui. Isso não testa a interface elétrica, filtros/fallback ou
modos de partida do hardware, que continuam pendentes no perfil.

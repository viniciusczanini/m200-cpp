# Projetos públicos reais: escopo e resultado local

Em 2026-11-05, o ensaio local executou **19 casos e 16.128 scans**, comparando
as 16 saídas de cada scan com um oráculo independente em três caminhos:
IL original extraída → VM, C++ reconstruído → executável nativo e C++
recompilado → VM. Os 19 casos passaram. A primeira execução completa levou
21,443 s. Não houve editor oficial, PLC físico, transmissão a PLC nem CI remoto.

**Nenhum dos dez projetos completos foi importado.** Todos têm CPU diferente
do destino TM200CE40T. Na primeira execução, `load_project` recusou nove
originais em `duplicate XML singleton: AnalogInputs/AnalogIO` e o arquivo07
em `duplicate XML singleton: FunctionBlocks/IFunctionBlock`, antes da checagem
da CPU. O diagnóstico foi corrigido com regressão: agora todos são recusados
primeiro com a CPU encontrada e o destino TM200CE40T exigido. Os cabeçalhos
não foram trocados para forçar aceitação. A implementação de Modbus também
passou a reconhecer os dois gráficos de comunicação desse arquivo.

O `PASS` do comando confirma integridade dos originais, recusas esperadas e
execução da lógica isolada especificada abaixo. A compatibilidade integral
no EcoStruxure Machine Expert Basic e no TM200CE40T permanece pendente.

## Reprodução

Os arquivos de terceiros ficam somente em
`research/downloads/public-projects/`, ignorado pelo Git. O manifesto pequeno
[manifest.json](../../tests/public/manifest.json) fixa repositório, caminho,
commit, permalink, tamanho, SHA-256 e Git blob SHA-1 de cada original.
Os projetos não são redistribuídos neste repositório.

```sh
# Rede somente neste comando explícito; arquivos existentes são só verificados.
python3 tests/public/fetch.py

# Sem rede. Usa os downloads originais e cria uma pasta temporária de resultados.
python3 tests/public/run.py

# Caminhos alternativos; a pasta de saída deve estar ausente ou vazia.
python3 tests/public/run.py --corpus /caminho/dos/originais --output /tmp/m200-public-audit
```

O runner imprime o diretório criado. `results.json` contém procedência, CPU
original, erro de importação integral, resultado de IL e gráfico de **cada
um dos 119 rungs**, adaptações, recusas e resultados dos casos. Cada caso
preserva `isolated.il.json`, `reversed.cpp`, `recompiled.il.json`, `trace.json`,
`observations.json` e `result.json` para inspeção e reprodução.

O comando falha se houver mudança de hash/tamanho/blob, resultado inesperado
de validação, erro de compilação/execução, diferença em qualquer saída ou
falta de um dos 19 casos/16.128 scans. Verifica novamente os dez originais
ao terminar, inclusive quando um teste falha. O XML só é analisado depois
da identidade do arquivo; tamanho/UTF-8, DTD/entidades e profundidade são
limitados. Não modifica o download, a CPU ou a configuração do projeto.

## Fontes e comportamento efetivamente exercitado

Os números dos rungs abaixo começam em zero, na ordem do XML original.

| Original e fonte fixada | CPU original | Lógica isolada e oráculo | Scans |
| --- | --- | --- | ---: |
| [00 XIC-XIO](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/XIC-XIO.smbp) | TM221CE16R | Rungs 0/1; `Q0 = !I0 && !I2`, `Q1 = I1 && I0 && I2`; 8 combinações repetidas 64 vezes. | 512 |
| [01 XIC-XIO parallel](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/XIC-XIO%20parallel.smbp) | TM221CE16R | Somente rung 0, mesma equação de Q0. Rung 1 com `AND(` e parênteses recusado explicitamente. | 512 |
| [02 equations](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/equations.smbp) | TM221CE16R | Ambos os rungs incrementam MW1, portanto cada scan com I0 ativo soma **2**. Estado inicial zero; observa todos os 16 bits. | 4.096 |
| [03 memory floats multiply](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/memory%20floats%20multiply.smbp) | TM221CE16R | O conteúdo real atribui inteiro `MW0 := 1`, depois compara `MW0 > 1`: Q1 sempre ativo, Q2 inativo. Verifica `OPER` antes da bobina. | 128 |
| [04 timer test](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/timer%20test.smbp) | TM221CE16R | Cinco blocos TM0..4, porém `Timers` está vazio. A execução recusa temporizadores indefinidos; tipos/presets padrão não foram inventados. | 0 |
| [05 Counters1](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/Counters1.smbp) | TM221CE16R | Conteúdo real: `LD %M0; ST %M0`. Teste de identidade de memória; o original não contém contador nativo. | 128 |
| [06 correto](https://github.com/GabriWar/ubec/blob/cd7f4b009b53c19a9952173efbbcf29decc12087/PROJETOS/UBEC/correto.smbp) | TM200CE24R | Rung 4: `Q4 = !I13 || M4`; ação após bobina grava MW604=1 quando habilitada e preserva o valor depois. | 2.048 |
| [07 Ladder_Code](https://github.com/Mohammed-Helal/GP26/blob/0f68ca90f7fd51d44176b8bea01e73039c8e0641/Ladder_Code.smbp) | TM200CE40R | Rungs 0..5: selo `M0 = (I0 || M0_anterior) && I1`, propagação por MW11/M1 até Q0 e escrita persistente MW10 quando I16 está inativo. | 2.048 |
| [08 memory floats gt](https://github.com/ss56/somachine-basic-programs/blob/c6e657a1759625d772fa01751259ff0cde6f0252/memory%20floats%20gt.smbp) | TM221M16R/G | Rungs 1..5 e 21..26, cada um em caso próprio: 11 comparações simples × 512 scans, preservando a sobreposição de MF1/MF2. | 5.632 |
| [09 Power Generator Manager](https://github.com/LiuYuancheng/Power_Generator_Manager/blob/75cf5666462cc2b5f4701209b8854d5c40ca6165/src/S1new_192_168_10_72.smbp) | TM221CE16R | Todos os seis rungs de lógica com TM0 **TOF de 25 s explicitamente configurado**. Oráculo verifica retenção, expiração, reinício e ordem de scan. | 1.024 |

## Adaptações de observação e limites

As instruções selecionadas vêm diretamente do XML verificado e recebem
somente normalização de espaços. O relatório separa as listas `before`,
`original_rungs` e `after`. As adaptações são partes do ensaio isolado,
não alterações nem uma importação do projeto original:

- Equações: observadores usam scratch MW200, máscaras de bits e Q0.0..15.
  MW1 inicia em zero e fica abaixo do limite signed16 neste ensaio. Não há
  conclusão sobre comportamento de overflow no PLC.
- Autocópia M0: entrada 0 fornece M0 antes do rung; Q15 observa M0 depois.
- `correto`: entrada 1 fornece M4; Q15 observa MW604=1 depois do rung.
  O gráfico paralelo/ações desse rung continua recusado na análise separada.
- `Ladder_Code`: Q15 observa MW10. Os demais rungs de timers e
  READ_VAR/WRITE_VAR não fazem parte do ensaio de execução. Blocos de
  comunicação isolados sem sua configuração não comprovam nem refutam
  o suporte a uma operação Modbus configurada.
- Floats: antes de cada comparação escreve MF1=1.0 e depois MF2=1.0 nos
  endereços **originais**. MF1 usa palavras 1/2; MF2 usa 2/3. A segunda
  escrita deixa MF1=0.0 e MF2=1.0. O oráculo calcula isso com
  `struct.pack/unpack` independente, e Q15 observa MF1=0.0. Endereços
  não foram separados para eliminar a sobreposição. Não há gráfico Ladder
  nesses rungs originais, portanto não se afirma equivalência gráfica.
- Gerador: entradas 0..5 fornecem M40/M0/M10/M60/M4/M5. Q15 observa M30
  depois do timer; Q0/Q1 leem o M30 do scan anterior por sua posição
  **antes** do timer no original. Casos controlados cobrem 24.999/25.000 ms,
  e a sequência determinística inclui deltas de até 3.600.000 ms. O delta
  avança o relógio depois do scan.

Os oráculos são fórmulas booleanas, contagem, máquina de estados explícita,
comparações Python e armazenamento IEEE754 independente. Não usam a VM,
o C++ reconstruído ou a leitura numérica da implementação para calcular as
saídas esperadas. A execução nativa usa o SDK experimental do projeto;
a concordância dos três caminhos e do oráculo é evidência local dentro
desse escopo, sem equivaler à validação oficial ou física.

## Inventário de recusas separado dos testes de execução

Na execução final registrada, dos 119 rungs originais, **92 passaram na validação
de IL e 27 foram recusados**. Na análise gráfica separada, **56 passaram,
33 foram recusados e 30 não contêm elementos Ladder**. Ausência de gráfico
é registrada como `ABSENT`, sem contá-la como equivalência visual.

As recusas incluem parênteses/expressões compostas não suportadas, palavras
de entrada analógica, formas de timer fora do subconjunto ou sem parâmetros,
blocos de comunicação sem configuração no ensaio isolado e conexões/posições
gráficas fora do subconjunto. Cada erro exato e rung original está no
manifesto/relatório. Uma melhora futura de suporte exige revisar essas
expectativas e acrescentar um oráculo para o comportamento recém-aceito.

Relatório final resumido e identidades: `PUBLIC-PROJECTS-RESULTS.json`. Os resultados da integração de Modbus são separados, em `PUBLIC-MODBUS-RESULTS.json` e `../MODBUS.md`; a aceitação gráfica de READ/WRITE não é contada como importação integral de um projeto estrangeiro.

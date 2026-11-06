# Contratos de contadores nativos %C - pesquisa para TM200CE40T

Data: 2026-11-05. Pesquisa somente de leitura do projeto `/Users/tommy/Offline/projects/m200-cpp`, com novos dados e este relatório em `/tmp`. Foram lidos `AGENTS.md` e `docs/PARITY.md`. Nenhum código, configuração de Git, CI, dispositivo ou programa de PLC foi alterado ou executado.

## Resultado e limites

Há evidência oficial para entradas R/S por nível, CU/CD por borda de subida, preset 0..9999, contagem circular 9999->0 e 0->9999, prioridade de R, reset das três saídas, acesso a P/V e duas formas IL. Há originais públicos com XML de configuração e gráfico real de Counter, incluindo R, CU, CD, D, escrita de P, leitura de V e S/CD específicos.

**Não existe base suficiente nesta pesquisa para chamar a semântica completa de E ou de bordas simultâneas no M200 de resolvida.** O manual genérico atual contradiz a si mesmo quanto a E. O manual Twido documenta mais detalhes, mas não substitui o perfil M200. Os projetos públicos examinados são de M221; comprovam os bytes observados de SMBP, sem comprovar aceitação no TM200CE40T. Nenhum editor/simulador oficial foi executado.

## 1. Fontes oficiais e identificação

Páginas abaixo são as páginas impressas, iguais ao índice PDF de base 1 nos PDFs examinados.

| ID | Documento oficial | Origem e cópia local | Páginas úteis |
|---|---|---|---|
| G | EcoStruxure Machine Expert - Basic, Generic Functions Library Guide, EIO0000003289.04, 09/2025 | [Página Schneider](https://www.se.com/us/en/download/document/EIO0000003289/); arquivo já local `research/downloads/manuals/EIO0000003289.pdf` e `.txt` | 35-36 objetos; 39/41 leituras/escritas; 49-51 comparações/atribuição; 103-104 IL de FB; 120-123 contador |
| P | Modicon M100/M200 Logic Controller, Programming Guide, EIO0000002019.06, 07/2026 | [Página Schneider](https://www.se.com/ph/en/download/document/EIO0000002019/); [PDF oficial](https://download.se.com/files?p_Doc_Ref=EIO0000002019&p_enDocType=User+guide&p_File_Name=EIO0000002019.06_M100_200+Programming+Guide.pdf); `/tmp/m200-counter-sources/EIO0000002019-06.pdf` | 21-23 inclusão de %C e remissão ao manual genérico; 25 limite de instâncias |
| O | EcoStruxure Machine Expert - Basic, Operating Guide, EIO0000003281.04 | `research/downloads/manuals/EIO0000003281.pdf` e `.txt`; [Página Schneider](https://www.se.com/us/en/download/document/EIO0000003281/) | Consultado para contexto de objetos; não define os casos de execução ausentes em G |
| S17 | SoMachine Basic, Generic Functions Library Guide, EIO0000001474.08, 12/2017 | [Página Schneider](https://www.se.com/us/en/download/document/EIO0000001474/); [PDF oficial](https://download.se.com/files?p_Doc_Ref=EIO0000001474); `/tmp/m200-counter-sources/generic-2017.pdf` | 181-185 |
| T11 | TwidoSuite V2.3, Programming Guide, 35011386.05, 06/2011 | [PDF oficial Schneider](https://download.se.com/files?p_Doc_Ref=35011386K01000); `/tmp/m200-counter-sources/twido.pdf` | 480-482 |

G é aplicável aos controladores suportados por Machine Expert Basic, e P identifica %C como objeto de software genérico. Isso fundamenta o uso de G para o M200, sem importar automaticamente todos os recursos específicos de M221. P25 permite **255 instâncias %C**. Essa contagem não deve ser confundida com prova isolada de que o índice final seja 255: a faixa exata de endereçamento deve ser vinculada ao perfil/editor.

SHA-256 de PDFs baixados nesta pesquisa:

- P: `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`.
- S17: `f08df49636f8bc61f00de18e4a04ee32a38e090927190a2a2b45ffb125837641`.
- T11: `80fa88ae9fc0995b12f9e734bb78bf8b716ddc3f0221295fcc757a0b815344b9`.

As páginas G120/G122/G123, S17-184 e T11-481 foram renderizadas e inspecionadas visualmente, para excluir erro de extração de tabela. PNGs em `/tmp/m200-counter-sources/`.

## 2. Contrato documentado de entradas, valor e preset

Fonte principal: [G, pp120-122](https://www.se.com/us/en/download/document/EIO0000003289/).

| Aspecto | Contrato comprovado | Limite da evidência |
|---|---|---|
| R | Entrada por nível: quando R=1, V=0; E=D=F=0. R tem prioridade. | Prioridade está descrita para o processamento do contador. Não prova uma prioridade global sobre qualquer instrução posterior em todo o scan. |
| S | Entrada por nível: com S=1 e R=0, V recebe P e D=1. | E/F depois de S não são definidos explicitamente nessa linha. Interação exata S+CU/CD no mesmo processamento não possui tabela completa. |
| CU | Cada borda de subida da entrada incrementa V em uma unidade. Manter entrada alta não equivale a contar uma unidade por scan. | A localização exata do histórico de borda para várias instruções específicas da mesma instância não está explicitada. |
| CD | Cada borda de subida decrementa V em uma unidade. | Mesma lacuna para múltiplos pontos de execução, saltos e chamadas repetidas. |
| Rollover up | Ao incrementar 9999, V torna-se 0 e F é ativado. | Não há regra completa para F ao trocar de direção, acionar S ou editar V. |
| Rollover down | Ao decrementar 0, V torna-se 9999. | O valor é documentado; a transição precisa de E é conflitante, abaixo. |
| P | Faixa configurável 0..9999, padrão 9999; pode ser lido, comparado e escrito pelo programa e editado em tabela de animação. | Valor inválido em escrita de execução: não há regra comprovada de rejeição, saturação, módulo ou flag. Não inventar. |
| V | Palavra corrente; o programa pode ler e testar, mas não escrever diretamente. A tabela de animação pode alterá-la. | Efeito da edição de V sobre E/D/F/históricos não especificado. |
| Troca de P | A alteração por instrução ou ajuste é considerada quando a aplicação processa o bloco, por ativação de uma entrada. | Não assumir recálculo assíncrono de D no momento da simples escrita de P, nem mudança de V. |
| Partida fria/INIT | V=0; E=D=F=0; P retorna ao valor configurado. | Não confundir com R, cuja descrição não recarrega o preset configurado. |
| Partida quente/STOP | A descrição afirma que V não é afetado. | Não especifica nessa tabela P, flags e memórias de borda. Não completar esses estados por analogia. |

O domínio circular normal do contador é 0..9999: incremento/decremento de uma unidade com os dois retornos documentados. Esse contrato não transforma o bloco em um contador IEC CTU saturado em P. G123 usa D como sinalização; o exemplo público `car_garage` adiciona explicitamente `ANDN %C0.D` antes de CU para bloquear novas contagens. A largura de uma palavra em G23 é 16 bits; isso não autoriza ampliar o contador %C a 65535.

**R e P=0 são um caso essencial:** R força D=0 mesmo com V=P=0. Logo, `D := (V == P)` aplicado incondicionalmente após reset viola a tabela de operações. Em contrapartida, S com R=0 força D=1, inclusive para P=0.

## 3. D, E e F: fatos e contradições

Fonte: [G, pp120-123](https://www.se.com/us/en/download/document/EIO0000003289/).

**D:** indica igualdade V=P e é forçado a 1 por S; R e INIT/cold-start forçam a 0. A documentação diz quando D é ativado, mas não enumera todas as transições de desativação após escrita de P ou instruções em diferentes pontos. A igualdade deve respeitar o processamento nativo e as exceções de reset.

**F:** G120 e G122 concordam: a contagem up que passa de 9999 para 0 ativa F; a contagem up seguinte desativa F. Isso é um evento de overflow, não simplesmente `V == 9999`. Se a próxima avaliação não contar, o manual não diz que F dure apenas um scan. Não usar temporização de pulso de um scan sem evidência.

**E apresenta conflito interno confirmado no PDF:**

1. G120, tabela Outputs: descreve E ao chegar a 0; um decremento seguinte passa V para 9999.
2. G122, tabela Operations: descreve E na passagem 0->9999.
3. G122, linha seguinte: descreve a continuação down, mas nomeia `%Ci.F` como bit de overflow down. Essa identificação conflita com o próprio nome/uso de F.
4. G123, exemplo gráfico/textual de contagem alternada: a narrativa usa E quando a contagem regressiva chega a 0, concordando com G120.

S17 (pp182/184) já contém a mesma divergência e o mesmo nome F na linha down. Portanto, consultar a edição de 2017 não resolve o conflito; é uma inconsistência herdada. [Fonte oficial S17](https://download.se.com/files?p_Doc_Ref=EIO0000001474).

T11 p481 diferencia claramente E de F: E é ativado no retorno down 0->9999 e sua tabela de parâmetros diz que a próxima contagem down o desativa. A tabela de operações desse mesmo documento também contém o nome F na linha down. Isso apoia a hipótese de erro editorial nessa linha, mas **não prova que o M200 atual herda exatamente o comportamento de E do Twido**. [Fonte oficial T11](https://download.se.com/files?p_Doc_Ref=35011386K01000).

Decisão para uma implementação que prometa paridade: marcar E como semântica pendente de resolução externa; registrar explicitamente qualquer política provisória. Não apresentar `E=(V==0)`, `E=(down-wrap)` ou a limpeza simétrica de E/F como contrato integral já comprovado no TM200CE40T.

## 4. CU/CD simultâneos e ordem dentro do scan

G120 permite contagem nas duas direções concorrentemente, mas não fornece tabela para duas bordas no mesmo processamento. T11 p481 acrescenta que as entradas são examinadas em sucessão e que ambas em 1 mantêm V. Esse fato é **documentado para Twido**; sua aplicação exata ao M200 é uma hipótese de continuidade que ainda precisa de evidência do M200/editor.

Casos sem resposta completa em G:

- Duas bordas de subida juntas, inclusive em V=0 ou V=9999: V final e E/F intermediários/finais.
- CU já alto e apenas CD sobe, e o inverso. Não confundir duas entradas em nível alto com duas novas bordas.
- Ordem CU/CD invertida dentro do BLK e ordem entre instruções específicas em rungs separados.
- Borda CU/CD no mesmo processamento de R ou S; se a borda é consumida durante o reset/set e o efeito de liberar R/S mantendo CU/CD altos.
- Mesma instância processada duas vezes no scan, ou apenas uma das direções processada; salto sobre o bloco e retomada.

G103 permite instruções específicas em vários pontos do programa. Portanto, não implementar uma fila que junte todas as operações de `%C0` do scan e lhes aplique prioridade global: isso pode apagar observações/escritas intercaladas. R prioritário numa avaliação não demonstra que um `R %C0` anterior invalide um `CU %C0` posterior por todo o scan.

## 5. Sintaxe IL comprovada

G103-104 define `BLK`, `OUT_BLK` e `END_BLK`, e G123 mostra a forma reversível abaixo. Entradas/testes do bloco ficam entre BLK e OUT_BLK (ou END_BLK quando OUT_BLK não existe). `OUT_BLK` inicia a parte de ligação direta das saídas. [G, pp103-104/123](https://www.se.com/us/en/download/document/EIO0000003289/).

Exemplo exato de G123, com preset configurado 5000:

```text
BLK %C8
LD %I0.1
R
LD %I0.2
AND %M0
CU
END_BLK

LD %C8.D
ST %Q0.0
```

A forma específica é `R %C8` / `S %C8` / `CU %C8` / `CD %C8`, após a condição booleana. G103/G123 demonstram R/CU/CD e os originais abaixo demonstram S/CD. Dentro de BLK usa-se R/S/CU/CD sem operando da instância. `R %C0` é reset do bloco; não é uma atribuição ao bit `%C0.D`.

G36 comprova leituras qualificadas `%Ci.E` e leituras curtas `E` na parte reversível de saída. Os originais B e M abaixo mostram `OUT_BLK`, `LD D`, ST e END_BLK juntos.

Para palavras, G49-51 permite `%BLK.x` como fonte e `%Ci.P` como destino: leituras como `[ %MW7 := %C0.V ]`, comparações `LD [ %C0.V > 0 ]` e atribuição a P são composições dessa gramática. O original L contém a forma exata `[ %C0.P := %MW10 ]`.

**Escritas diretas em E/D/F:** G121 permite edição pela tabela de animação. G41 inclui `%BLK.x` genericamente nos operandos de ST/STN/S/R, mas a seção do contador não confirma individualmente a autorização/efeito de escrever suas três saídas pelo programa. T11 lista esses bits como não graváveis. Não concluir daqui que `ST %C0.D` funciona no perfil M200 nem tratá-lo automaticamente como garantidamente inválido sem validação do perfil. V é explicitamente somente leitura no programa.

Não usar `%Ci.PD`/`%Ci.VD` como recurso de contador comum só porque uma tabela genérica lista grafias de double word: G120-121 documenta %C como P/V 0..9999. Não foi obtida configuração ou instância %C double word.

## 6. SMBP: originais públicos primários, integridade e escopo

Arquivos recuperados pelos recursos públicos do próprio GitHub, sem executar conteúdo. Os bytes locais têm Git blob SHA-1 igual ao retornado pela busca/arquivo do GitHub. Manifesto completo, SHA-256, CPU, versão e nível funcional: `/tmp/m200-counter-sources/manifest.json`.

| ID | Original primário fixado em commit | Cópia local | CPU e prova relevante |
|---|---|---|---|
| B | [brymon68/Project1_Part1B](https://github.com/brymon68/cs_8803_7/blob/2cacf9fd8b059a0d87a0fe6105fbf9fa586b5c4f/Project%201/Project1_Part1B.smbp) | `/tmp/m200-counter-sources/Project1_Part1B.smbp` | TM221M16R/G; versão1.6, FL7; Counter, P=5, comentário opcional, CU, D direto via OUT_BLK |
| M | [thalesfb/starting_motors](https://github.com/thalesfb/ind_automation/blob/17a8500ab8189392d11e756324386f4f07ac1544/starting_motors/clp/starting_motors.smbp) | `/tmp/m200-counter-sources/starting_motors.smbp` | TM221CE24R; versão2.9, FL20; Symbol, P=3, R+CU, D para bobina |
| C | [Jaron-voided/car_garage](https://github.com/Jaron-voided/PLC_Ladder_Projects/blob/0677b8cd814ed7a04c20ecede1a24f05c0561e91/Car_Garage/car_garage.smbp) | `/tmp/m200-counter-sources/car_garage.smbp` | TM221M16R/G; versão3.0, FL21; R+CU+CD e gráfico coerente; contato de D em outros rungs |
| L | [didim99/Lab-07-M221-autoOperator](https://github.com/didim99/TSTU/blob/ea8c59ca97fc99d07cc979a2fcb78113c322cf2c/labwork/mps/Lab-07-M221-autoOperator.smbp) | `/tmp/m200-counter-sources/Lab-07-M221-autoOperator.smbp` | TM221ME16R/G; versão2.6, FL17; P=0 configurado, Symbol, escrita de P, S específico, leitura de V e CD específico |

Git blobs respectivos: B `828901f5c25b9598c707862f50920173e212cb70`; M `3deaecd3f64f930ff873dc0ebfd3e65fe5ded6c1`; C `024e4660697a2dc0e8cb08ad2c5d2dc56ab783ca`; L `425372b07a34946b6363b78bd15a5fbf8727cc98`.

Também foi recuperado `Project1_Part3.smbp` do mesmo commit de B; tem contador configurado, mas não acrescenta gráfico de contador. Os dez arquivos do corpus anterior em `research/downloads/public-projects/` têm `<Counters />` vazio, inclusive `05-Counters1.smbp`: não servem como prova positiva do contador.

### 6.1 Configuração XML literal comprovada

Caminho observado: `ProjectDescriptor/SoftwareConfiguration/Counters/Counter`. B linhas1411-1423:

```xml
<Counters>
  <Counter>
    <Address>%C0</Address>
    <Index>0</Index>
    <Preset>5</Preset>
  </Counter>
  <Counter>
    <Address>%C1</Address>
    <Index>1</Index>
    <Comment>Count down from 5</Comment>
    <Preset>5</Preset>
  </Counter>
</Counters>
```

M linhas4136-4144 mostra outra variante real:

```xml
<Counters>
  <Counter>
    <Address>%C0</Address>
    <Index>0</Index>
    <Symbol>CON_CIC</Symbol>
    <Preset>3</Preset>
  </Counter>
</Counters>
```

Não há `Type`, `CounterType`, `Mode`, `Single`, enum de direção, valor corrente ou flags nesses registros. Isso prova somente as variantes observadas; não demonstra que outros campos sejam universalmente proibidos. A palavra SINGLE da representação visual do manual **não é prova de enum XML**.

Correção após conferir novamente os bytes preservados, durante a implementação:
B/M têm `SoftwareConfiguration/CountersMemoryAllocation` vazio, mas C/L têm
`<CountersMemoryAllocation><ForcedCount>1</ForcedCount></CountersMemoryAllocation>`.
A afirmação anterior de ausência de amostra positiva não vazia estava incorreta.
Os hashes dos arquivos são os mesmos; nenhum original foi modificado. Isso
comprova ForcedCount sem Allocation nesses dois arquivos; não comprova tokens
de enum de alocação. Não criar esses enums por analogia com timers.

### 6.2 Graph de Counter literal comprovado

B linhas229-236:

```xml
<LadderEntity>
  <ElementType>Counter</ElementType>
  <Descriptor>%C0</Descriptor>
  <Comment />
  <Symbol />
  <Row>0</Row>
  <Column>2</Column>
  <ChosenConnection>Left</ChosenConnection>
</LadderEntity>
```

M linhas1909-1917 tem a mesma tag `Counter`, Symbol `CON_CIC`, Row0, Column6 e `ChosenConnection` literal `Left, Right`. Portanto, não fixar a conexão em `Left` para todas as topologias.

No original C, o Counter está em Row0/Column2. Os contatos/linhas de R estão em Row0/Column0..1, os de CU em Row2/Column0..1 e os de CD em Row3/Column0..1. A IL correspondente é, exatamente, removendo apenas preenchimento de espaços:

```text
BLK %C0
LD %I0.2
R
LD %I0.0
ANDN %C0.D
CU
LD %I0.1
CD
END_BLK
```

Isso comprova entradas R na linha base, CU na base+2 e CD na base+3. A entrada S na base+1 e as saídas E/D/F em base/base+1/base+2 aparecem no desenho oficial G120; entretanto, o corpus positivo recuperado não contém um Counter gráfico com S/E/F ligados para provar separadamente todos esses conectores XML. B liga D por linhas em Row1, começando Column4, coerente com a saída D no deslocamento +1 e largura do bloco de duas colunas. A representação completa não pode ser reconstruída usando apenas `ChosenConnection` como se ele codificasse individualmente cada pino.

M usa IL com `MPS`/`MPP` para compartilhar prefixo entre R e CU; também usa `OUT_BLK`, `LD D`, `ST %M22`. Não apagar essas estruturas ao importar para uma API simplificada de contador.

### 6.3 IL específica observada no original L

Linhas513/517: `[ %C0.P := %MW10 ]`, seguida de `S     %C0` sob o acumulador booleano existente. Linhas603/632: leitura comparativa de `%C0.V > 0`. Linha636: `CD    %C0`. O gráfico desses rungs específicos não é um Counter reversível, portanto esse exemplo não comprova a geometria da entrada S no Counter.

## 7. Evidência ainda necessária para fechar paridade

1. Perfil exato de editor/firmware/nível funcional do TM200CE40T; abrir, compilar, salvar e reabrir um contador real nesse perfil.
2. Traços oficiais com R=1 e P=0/5, R+S+bordas juntos, S+CU/CD, reset/set mantidos e liberados com CU/CD altos.
3. E em 1->0 e 0->9999; E na contagem seguinte, na troca de direção e em avaliação sem borda. F em 9999->0, contagem seguinte, troca de direção e avaliação sem borda.
4. D antes/depois de modificar P, incluindo P=0, e leituras intercaladas no mesmo scan.
5. CU/CD com duas bordas simultâneas, apenas uma borda e outro nível alto, ordem invertida e extremos 0/9999; leituras das flags em pontos intermediários quando a IL permite.
6. Várias instruções específicas/BLKs da mesma instância no mesmo scan, salto sobre bloco, retomada e memórias de borda nas transições RUN/STOP/restart.
7. Semântica de preset inválido em execução e permissões/efeitos de escrita em E/D/F.
8. Original TM200CE40T com Counter gráfico S/E/F ligados e exportação/round trip nativo. Isso fecha a lacuna de modelo e de todos os pinos; os nomes XML já observados não devem ser substituídos por enums inventados.

Esses são pontos de aceitação pendentes, não limites físicos demonstrados do PLC e não autorização para transmissão automática a equipamento. A pesquisa conclui contratos documentais e integridade dos dados, sem declarar compatibilidade oficial do compilador.

## Preservação local

O relatório conserva os caminhos temporários usados na pesquisa. Os originais de fluxo foram preservados, sem alteração de bytes, em `research/downloads/public-projects/flow-original-*.smbp`, com manifesto em `tests/public/control-flow-manifest.json`. Os originais de contadores foram preservados em `research/downloads/counter-sources`, com manifesto de identidade em `docs/capabilities/COUNTER-SOURCES.json`. O manual de programação está em `research/downloads/manuals/EIO0000002019.pdf`. Esses dados baixados permanecem fora do Git; os manifestos permitem conferir e recuperar as mesmas versões.

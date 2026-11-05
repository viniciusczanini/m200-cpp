# M200 C++: fluxo nativo, memória indexada e reversibilidade Ladder

Pesquisa em 2026-11-05. Alvo: Schneider TM200CE40T. Trabalho somente de leitura; não foram alterados código, Git, configurações remotas ou PLC. Foram lidos `AGENTS.md`, `docs/PARITY.md`, o catálogo de capacidades e os manuais oficiais locais. A pedido adicional, foram examinados dois projetos publicados diretamente por seus autores no GitHub.

## Resultado para implementação

O perfil nativo possui laços em execução dentro do mesmo scan: saltos para trás e `FOR/ENDFOR`. Unrolling de limites constantes é uma otimização possível, mas não expressa o conjunto nativo: contador, início, fim e passo de `FOR` podem vir de `%MW`, e `JMP/JMPC/JMPCN` permitem repetição condicionada por estado mutável. Há elementos gráficos oficiais para saltos, chamadas, condicionais e laços. A falta atual de serialização SMBP de um elemento é lacuna do exportador, não impossibilidade do PLC. [G pp.61-66; O p.121; P pp.26-27]

Foi encontrado um SMBP original com `ElementType=Jump`, `Descriptor=%L7`, `JMPC %L7`, a declaração `%L0:` em `InstructionLines` e o campo separado `<Label>%L0</Label>`, com Ladder selecionado. Isso fornece um exemplo concreto de serialização de salto/label. Não foram encontrados exemplos gráficos de `FOR/ENDFOR`, salto incondicional ou `JMPCN` na busca realizada. Detalhes e hashes estão abaixo.

## Fontes primárias e perfil

As páginas mencionadas são as impressas no rodapé; nos PDFs examinados correspondem também ao número de página PDF.

| ID | Documento oficial | Edição/hash SHA-256 | Evidência relevante |
|---|---|---|---|
| G | [EIO0000003289, Generic Functions Library Guide](https://www.se.com/us/en/download/document/EIO0000003289/) | EIO0000003289.04, 09/2025; `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595` | pp.14-15, 27-35, 49-54, 60-66, 84-86 |
| O | [EIO0000003281, Operating Guide](https://www.se.com/us/en/download/document/EIO0000003281/) | EIO0000003281.04, 09/2025; `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5` | pp.47-51, 55, 64-70, 121-123, 130, 134-135 |
| P | [EIO0000002019, M100/M200 Programming Guide](https://www.se.com/id/en/download/document/EIO0000002019/) | EIO0000002019.06; `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df` | pp.10, 14-15, 24, 26-28, 322-323, 328 |

G e O foram lidos dos PDFs em `research/downloads/manuals`. P foi obtido do [download oficial Schneider](https://download.schneider-electric.com/files?p_Doc_Ref=EIO0000002019&p_enDocType=User+guide&p_File_Name=EIO0000002019.06_M100_200+Programming+Guide.pdf), salvo em `/tmp/m200-control-flow-programming-guide.pdf`; o hash coincide com o catálogo do projeto. As páginas oficiais foram consultadas para conferir revisões atuais. P p.10 declara atualização para Machine Expert Basic V1.3 e referencia G/O; P p.14 explicita IL, Ladder e Grafcet no M100/M200. O p.16 relaciona M221 na seção Supported Devices: portanto O isoladamente não comprova o perfil M200, mas P faz a ligação explícita. Firmware real, nível funcional e edição exata instalada do editor ainda precisam ser identificados.

## Saltos, labels e retorno

| Recurso | Semântica oficial | Regras/implicação |
|---|---|---|
| `JMP %Li` | Salto incondicional. | Pode ir para montante ou jusante; repetição a montante prolonga o scan e pode disparar watchdog. |
| `JMPC %Li` | Salta quando resultado booleano precedente é 1. | É o acumulador IL no ponto da instrução, não uma condição reavaliada implicitamente. |
| `JMPCN %Li` | Salta quando resultado booleano precedente é 0. | Não inverter por suposição o significado do elemento gráfico. |
| `%Li:` | Define destino. | Apenas antes de `LD`, `LDN`, `LDR`, `LDF` ou `BLK`; definição única no programa. Não presumir escopo independente por POU sem ensaio. |
| `SRn` | Chama Free POU SRn se acumulador precedente=1 e retorna ao chamador. | Free POU independente do programa principal; não pode chamar outro SR. O acumulador pode ter sido modificado na volta. |
| `END/ENDC/ENDCN` | Encerra nível atual, incondicionalmente/com acumulador1/com acumulador0. | Em SR/UDF/UDFB retorna ao chamador; em tarefa mestre/periódica/evento encerra a tarefa atual. `ENDT` é específico de transição Grafcet SFC. |

Referências: G pp.60-62, 65-66; O pp.64-65, 69, 130. Não foi encontrado um opcode `RET` genérico nos capítulos consultados. `%RET0` é um objeto de valor retornado da UDF, de tipo Word/Double/Float; não deve ser confundido com instrução de controle. UDF pode chamar UDF sem recursão direta/indireta; UDF não pode chamar SR, enquanto SR pode chamar UDF. [O pp.69-70]

O pp.49-51 exige, para IL/Ladder coerentes:

- Saltos, labels e chamadas SR fora de parênteses booleanos; `JMP`/SR também fora da região entre `MPS` e `MPP`.
- Label/subrotina definidos antes de `LD` ou `BLK`; G p.62 detalha as variantes de `LD` aceitas para labels.
- Saltos/chamadas como última ação de saída do rung. Em particular SR ou `JMPC` antes de outra ação gera advisory em IL, erro Ladder e perde reversibilidade.
- Nenhuma instrução executável após `JMP` ou `END` incondicional no mesmo rung; a continuação precisa de outro rung.
- Destinos definidos e únicos; labels e subrotinas válidos de 0 a 63. O limite publicado é 64 números, não uma reserva arbitrária do compilador.
- Blocos reversíveis usam `BLK`, `OUT_BLK`, `END_BLK`; uma chamada direta funcional em IL não significa que tenha representação Ladder reversível.

A tabela de O p.51 pode considerar um erro de programa ainda reversível (ex.: destino inexistente); reversibilidade estrutural não significa compilação válida. O pp.48-49 informa que o programa é armazenado internamente como IL e visualizado em IL ou Ladder. G p.14 descreve o procedimento oficial de colar cada rung IL e convertê-lo para Ladder.

## Condicionais e laços gráficos oficiais

G pp.62-65 documenta estruturas de nível funcional >=6.0, criadas offline e com um elemento estrutural por rung:

- `IF0 ... THEN0`, `ELSE0`, `ENDIF0`; `IF`/`ELSE` no início, `ENDIF` sozinho no fim. Os índices correspondentes devem pertencer ao mesmo POU. Região não selecionada é pulada, sem avaliar seus rungs, portanto seus objetos conservam o valor.
- `FOR0` e `ENDFOR0`, com representações gráficas próprias. `FOR` no começo do rung; `ENDFOR` no fim, sem outros elementos no mesmo rung. Ambos têm o mesmo índice e ficam no mesmo POU.
- Assistente FOR: contador `%MWx`; inicial, limite final e passo aceitam `%MWx` ou inteiro -32768..32767; relação `<`, `<=`, `=`, `>=`, `>` ou `<>`.
- O manual publica máximo de elementos como `128 - quantidade de %L declarados` tanto na seção condicional quanto na de laços. Não esclarece no trecho se conta pares/índices ou cada marcador, nem a combinação entre ambas as famílias. Isso não substitui o limite explícito de labels 0..63.

As tabelas e os desenhos das páginas G64-65 e O121 foram renderizados e inspecionados. Os manuais não publicam ali a serialização completa do assistente FOR no SMBP, profundidade máxima de aninhamento de laços, momento de releitura de fim/passo `%MW`, comportamento de passo zero, overflow do contador ou salto que cruza estruturas. Não se deve implementar essas questões como se estivessem especificadas.

Para `while`, `do/while`, `break` e `continue`, lowering em rungs com labels/saltos é uma estratégia derivada da semântica oficial, não novo recurso de hardware. Precisa preservar ordem e todas as iterações no mesmo scan; não inserir uma cota que encerra antecipadamente nem espalhar uma iteração por scan. O código nativo continua sujeito ao watchdog: P p.27 leva a HALTED em estouro da tarefa e em uso sistêmico >80%; P p.328 documenta `%SW11` de 10..500 ms. Testes do compilador podem ter limite de segurança diagnosticado, mas isso não pode simular sucesso nativo após truncar execução.

## Memória indexada, tabelas e aliases

### Endereçamento e limites reais

P p.24 e a definição de faixa 0..n-1 em P p.24 dão ao TM200:

| Espaço | Quantidade/endereço inicial possível | Observação |
|---|---|---|
| `%MW` | 8000 words: 0..7999 | 16 bits cada. |
| `%MD` e `%MF` | 7999 endereços iniciais: 0..7998 | Cada valor usa 2 `%MW`, não bancos independentes. |
| `%KW` | 512: 0..511 | Constantes. |
| `%KD` e `%KF` | 511 iniciais: 0..510 | Cada valor usa 2 `%KW`. |
| `%M` | 1024: 0..1023 | Indexação de bits requer FL>=10.0 (O p.55). |

G p.30 especifica `%MDi` e `%MFi` sobre `%MWi` (16 bits baixos) e `%MW(i+1)` (16 bits altos), inclusive endereços ímpares e sobreposição entre vizinhos. Idem `%KD/%KF` e `%KW`. Não usar o mapa de M340/M580/Control Expert, em que fórmulas e alinhamento podem ser outros. Capacidade bruta contígua de 32 bits, sem outras reservas, é 4000 elementos; 7999 são inícios possíveis sobrepostos.

G pp.33-35 define indexação como endereço base mais conteúdo de um `%MW`. Exemplo oficial: `%MW108[%MW2]` com `%MW2=12` acessa `%MW120`. São listados `%MW`, `%KW`, `%MD`, `%KD`, `%MF`, `%KF` e `%M` indexados; constantes não são graváveis. `%MWi[%PARAMj]` só é válido em rung da UDF/UDFB que define o parâmetro. A tabela omite o sinal `%` em alguns índices MW; exemplos de instruções p.52 usam `%MWi[%MWj]`.

O texto geral implica soma direta do offset também para MD/MF, sem multiplicação implícita por 2; entretanto não fornece um exemplo numérico de MD/MF indexado. Implementar arrays tipados com offset físico `2*indice` é a inferência coerente com a unidade word e aliases, e deve entrar no ensaio diferencial no editor/PLC. Para evitar confusão: o stride das tabelas de 32 bits está confirmado independentemente e explicitamente por G p.85: `%MD30:4` contém `%MD30,%MD32,%MD34,%MD36`.

### Overflow e alocação fazem parte da semântica

G p.34: endereço+índice abaixo de zero ou acima do maior word referenciado diretamente na aplicação gera `%S20=1` e atribui índice efetivo 0 ao objeto. Isso aponta ao objeto base, não necessariamente ao endereço global 0; o texto não diz que a variável `%MW` do índice é sobrescrita. O programa deve ler/realizar tratamento e limpar `%S20` explicitamente após corrigir o índice. P p.323 confirma a flag e a limpeza pelo programa, mas descreve o limite de forma menos específica, como tamanho máximo do objeto.

O pp.47-48 oferece alocação automática até maior endereço usado ou associado a símbolo, e manual por número de objetos. Há incerteza de interação entre o limite descrito em G, alocação manual e último word de um MD/MF. Ensaiar cada modo; não substituir a regra por somente `0<=endereço<8000`. Para arrays exclusivamente indexados, o exportador deve reservar/declarar a região e verificar o que o editor realmente reconhece como limite. Reservas atuais do compilador não são limites do controlador.

Para equivalência nativa, uma API de acesso indexado deve permitir offset negativo quando o endereço final ainda for válido na zona e preservar `%S20`/fallback. Uma API de array com limites próprios pode ser adicional, mas sua política de erro não pode tomar o lugar da semântica nativa.

### Contextos de instrução e representação Ladder

- Atribuição indexada é suportada em origem e destino para MW/MD/MF. Exemplo G p.53: `[%MW0[%MW10]:=%KW0[%MW20]]`. Operações/atribuições são blocos gráficos Operation; comparações são Comparison. [G pp.49-53; O pp.122-123]
- A tabela de comparação G p.49 lista indexados no operando 2, mas não no 1. Não assumir simetria. Uma leitura explícita para temporário direto pode permitir a comparação, preservando ordem, alias e flags; para floats, inverter relação deve respeitar NaN.
- Aritmética inteira G p.54 aceita MW indexado a partir de FL5.0; `%MWi[%PARAMj]` nessa tabela requer FL10.0. A linha de double words não lista MD indexado. O suporte em atribuição não autoriza o operando em toda instrução: fazer lowering com load/store explícitos onde necessário, sem ampliar silenciosamente o conjunto nativo.
- Blocos Operation devem ficar em série, não em paralelo, e não podem iniciar o rung na primeira coluna. Expressões multioperando consomem 20 MW para mestre e mais20 para periódica; não podem ser usadas em tarefa de evento. [O pp.122-123]

### Tabelas não limitam todo array a 255 elementos

G pp.31-33 e 84-86: tabelas são regiões adjacentes do mesmo tipo; `%MWi:L`, `%MDi:L`, `%MFi:L`, e equivalentes constantes. O máximo documentado de L é255; estes trechos não explicitam um L=0 válido. Operações entre duas tabelas requerem mesmo comprimento/tipo. Tabela destino pode receber escalar para preencher ou outra tabela para copiar. O comportamento de cópia de regiões sobrepostas não é especificado ali.

O limite255 é do operando tabela de uma operação, não da memória indexável total. Array maior pode usar acessos escalares indexados ou operações segmentadas, desde que ordem e sobreposição sejam preservadas. Para região tipada contígua de comprimento L, a verificação derivada é `base + stride*L - 1 <= ultimo_word`, stride1 para MW e2 para MD/MF, além da alocação efetiva e dos outros usos da mesma memória.

## SMBP original: evidência de gráfico e label

### Exemplar gráfico confirmado no arquivo

Autor/repositório: [brymon68/cs_8803_7, Project 1/PLC+Vulnerabilities.smbp](https://github.com/brymon68/cs_8803_7/blob/2cacf9fd8b059a0d87a0fe6105fbf9fa586b5c4f/Project%201/PLC%2BVulnerabilities.smbp). Commit `2cacf9fd8b059a0d87a0fe6105fbf9fa586b5c4f`; Git blob `2b9591e6798a053a33be05aa035b34945fe4dfd6`; bytes104852; SHA-256 `fa31ac8cba4424f3069b089f20b016935e75f314991efcd040e42ceea81bdd1f`. Cópia RAW exata: `/tmp/m200-control-flow-original-1.smbp`. ProjectVersion1.6.0.0, FL7, modelo TM221M16R/G: evidência de formato do editor, não conformance CE40T.

No rung0:

```xml
<LadderEntity>
  <ElementType>Jump</ElementType>
  <Descriptor>%L7</Descriptor>
  <Row>1</Row>
  <Column>10</Column>
  <ChosenConnection>Left</ChosenConnection>
</LadderEntity>
```

O mesmo rung possui `%L0:` como primeira InstructionLine (linha109), `LD %I0.4`, `ST %Q0.4`, `JMPC %L7` (linha121), e `<Label>%L0</Label>` (linha127), `<IsLadderSelected>true</IsLadderSelected>` (linha128). O elemento Jump está nas linhas99-105; o alvo possui InstructionLine `%L7:` na linha683 e `<Label>%L7</Label>` na linha697.

Conclusão concreta: declaração IL usa dois-pontos; campo Label separado não usa dois-pontos; Descriptor do salto identifica o destino, também sem dois-pontos. O label não é um LadderEntity separado neste arquivo. `ElementType=Jump` neste exemplar corresponde a `JMPC`, não prova que o XML tenha o mnemonic escrito no ElementType. A declaração IL e o campo Label precisam permanecer coerentes no exportador e no caminho inverso.

Uma implementação que use a forma comprovada `Jump/JMPC` com condição booleana normal/negada e `LD1` para ramo incondicional é uma possibilidade de lowering; equivalência semântica e resultado gráfico precisam ser validados, pois a pesquisa não encontrou o enum próprio de `JMPCN`/`JMP`. Não inventar `JumpN` ou outra string por analogia.

### Exemplar de laço real em IL

[didim99/TSTU, Lab-08-M221-delivery.smbp](https://github.com/didim99/TSTU/blob/ea8c59ca97fc99d07cc979a2fcb78113c322cf2c/labwork/mps/Lab-08-M221-delivery.smbp), commit `ea8c59ca97fc99d07cc979a2fcb78113c322cf2c`; Git blob `2e93a0a44e66cbb6b1b50181bce7f50ce69784f6`; bytes94335; SHA-256 `4ea44184fd796888498b39561f60ff8ae4c4458447b9328896376431c1afe110`. Cópia RAW `/tmp/m200-control-flow-original-0.smbp`. ProjectVersion2.6.0.0, FL17, TM221M16R/G.

Rung3 contém `%L0:`, `LD %M0`, `AND [%MW10>0]`, `[INC %MW1]`, `[%MW10:=SHR(%MW10,1)]`, `JMPC %L0` (linhas93-113), Label=%L0 (119). Tem `LadderElements` vazio e `IsLadderSelected=false`: confirma laço nativo serializado e redundância do label, mas não prova seu gráfico.

Consulta GitHub Code Search `extension:smbp JMPC` encontrou esses dois arquivos e outro laboratório do mesmo autor. As consultas `extension:smbp JMPCN`, `extension:smbp "JMP "`, `extension:smbp FOR0`, `extension:smbp ENDFOR` deram zero resultados no índice consultado. Isso é limite da amostra/busca, não inexistência dessas formas.

## Trabalho de validação que permanece

1. Gerar projeto mínimo com a forma Jump/Label observada; abrir, compilar, alternar IL/Ladder, salvar e reabrir no editor do perfil CE40T. Comparar bytes/estrutura salvos; não contar XML bem formado ou round trip próprio como aceitação oficial.
2. Produzir no editor um `FOR/ENDFOR` com contador/fim/passo MW e extrair seu SMBP; confirmar nestings, zero iterações, passo negativo/zero, overflow, e mutação de fim/passo/counter dentro do corpo.
3. Ensaiar MW/MD/MF indexados com offsets0,1,2,-1 e nos limites; observar aliases, maior referência direta versus alocação manual, último word, `%S20`, destino efetivo após overflow e limpeza da flag.
4. Ensaiar laços com leitura/escrita sobrepostas, break/continue/return, chamadas e flags em cada iteração. Preservar scan e interrupções nativas; não aumentar cobertura declarada com unrolling de casos constantes.
5. No caminho inverso, reconstruir CFG de labels/saltos do programa real e C++ equivalente. Não depender de uma cópia do C++ em metadados. Limites reais de labels/recursos devem ser contabilizados com o overhead do compilador; esgotamento artificial é lacuna da ferramenta.

Não foram executados editor Windows, simulador oficial ou hardware. Todos os resultados acima são evidência documental ou exame de arquivos originais, com as inferências e incertezas identificadas.

## Preservação local

O relatório conserva os caminhos temporários usados na pesquisa. Os originais de fluxo foram preservados, sem alteração de bytes, em `research/downloads/public-projects/flow-original-*.smbp`, com manifesto em `tests/public/control-flow-manifest.json`. Os originais de contadores foram preservados em `research/downloads/counter-sources`, com manifesto de identidade em `docs/capabilities/COUNTER-SOURCES.json`. O manual de programação está em `research/downloads/manuals/EIO0000002019.pdf`. Esses dados baixados permanecem fora do Git; os manifestos permitem conferir e recuperar as mesmas versões.

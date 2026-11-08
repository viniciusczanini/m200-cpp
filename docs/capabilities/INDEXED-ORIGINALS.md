# Originais SMBP: memória indexada, Operation/Comparison e alocação

Pesquisa de leitura em 2026-11-05 para o perfil **TM200CE40T**. Foram lidos `AGENTS.md` e `docs/capabilities/CONTROL-FLOW-RESEARCH.md`. Nenhum arquivo de produção, CPU do projeto, Git, configuração remota ou PLC foi modificado. Não foram executados programas baixados, editor, simulador, build nem hardware.

**Resultado:** há dois originais públicos do autor didim99 com `%MW20[%MW10]` em instrução executável. Ambos conservam `LadderElements` vazio e `IsLadderSelected=false`, portanto comprovam IL indexado, sem comprovar seu XML gráfico. Outros originais comprovam os campos gráficos de MW/MD/MF diretos. Não foi encontrado gráfico indexado, `%MD/%MF/%M` indexado, tratamento executável de `%S20` nem `<Allocation>Automatic</Allocation>` na amostra examinada. Esses são limites desta busca, não limites do PLC.

## Identidade e origem dos arquivos

Manifesto recuperável: `/tmp/m200-indexed-sources/manifest.json`. Originais sem alteração de bytes, metadados e provas extraídas: mesmo diretório e `evidence.json`. Cada URL RAW está fixada em commit. Para todos os seis SMBP, foram conferidos tamanho, SHA-256 e a igualdade de `SHA1("blob " + tamanho_decimal + NUL + bytes)` com o Git blob publicado pela API do GitHub. PDFs Schneider têm tamanho/hash, sem fingir possuir Git blob.

O `ProjectVersion` abaixo é o campo do arquivo, não uma identificação inferida da versão comercial instalada. `ManagementLevel` é o token literal: **não foi decodificado automaticamente como FL17/FL18**. É preciso estabelecer o mapeamento no editor antes de afirmar o nível funcional selecionado. Todos os projetos são de modelos diferentes do alvo; inclusive **TM221CE40T não é TM200CE40T**.

| ID | Original do autor, fixado em commit | CPU original | ProjectVersion | ManagementLevel literal |
|---|---|---|---|---|
| I1 | [didim99/TSTU: labwork/mps/Lab-07-M221-autoOperator.smbp](https://github.com/didim99/TSTU/blob/ea8c59ca97fc99d07cc979a2fcb78113c322cf2c/labwork/mps/Lab-07-M221-autoOperator.smbp) | `TM221ME16R/G` | `2.6.0.0` | `FunctLevelMan17_0` |
| I2 | [didim99/TSTU: labwork/mps/Lab-07-M221-autoOperator-2.smbp](https://github.com/didim99/TSTU/blob/ea8c59ca97fc99d07cc979a2fcb78113c322cf2c/labwork/mps/Lab-07-M221-autoOperator-2.smbp) | `TM221ME16R/G` | `2.6.0.0` | `FunctLevelMan17_0` |
| F | [afafirmansyah/automatic-tank-gauging: Program.smbp](https://github.com/afafirmansyah/automatic-tank-gauging/blob/0a32c0f49051d84e5c341dbcf5d9cb7160446c62/Program.smbp) | `TM221CE16R` | `2.6.0.0` | `FunctLevelMan17_0` |
| D | [juanaguirre09/SCADA-PICK-AND-PLACE-XYZ: pick_place_SCADA.smbp](https://github.com/juanaguirre09/SCADA-PICK-AND-PLACE-XYZ/blob/4c70c82e9bbc12fcef15e90b603b3cd802c4dc01/pick_place_SCADA.smbp) | `TM221C16R` | `2.7.0.0` | `FunctLevelMan18_0` |
| A | [ph0wn/writeups: 2026/ghost-ship-cannons/setup/CTF_Challenge_Cannon.smbp](https://github.com/ph0wn/writeups/blob/40a9692518f7c4f367df3904c090f37641704069/2026/ghost-ship-cannons/setup/CTF_Challenge_Cannon.smbp) | `TM221CE16T` | `2.9.0.0` | `FunctLevelMan14_0` |
| T | [hitmansniper90/portfolio: station de pompage automatisée/3 Pompes permutation temporelle.smbp](https://github.com/hitmansniper90/portfolio/blob/31ea348f51f88794940289f64dd149fe1ac08f4e/station%20de%20pompage%20automatis%C3%A9e/3%20Pompes%20permutation%20temporelle.smbp) | `TM221CE40T` | `2.8.0.0` | `FunctLevelMan18_0` |

| ID | Bytes | SHA-256 | Git blob conferido |
|---|---:|---|---|
| I1 | 114221 | `a4307729f0864133e414517ef49c37e6648f29d7403a8f9737e2f7367461a738` | `425372b07a34946b6363b78bd15a5fbf8727cc98` |
| I2 | 113982 | `948a843946d40458a7dbbeb31d7538019226c29c74230891b3adfb07282737ed` | `75dec363d7b21e24afd96ff0ad50e15395b5cb72` |
| F | 152754 | `659c71a7b01f29fcdc55b8c30d2e4a425ce71cafa97bd3aebf4a4006da2d8e6c` | `86d5fdba310676419efd636d7d3c8d0802e326e6` |
| D | 326939 | `7431d3410ef71f2216b16b8c7cf086d21326abb289ff7191400128712a46fab9` | `431069dd14a7ff090d06cde10f2520426fe651b6` |
| A | 166429 | `a7763020ea0a170963bdf75ef84d92e572bf90b4d8ed83acaa245f42ad434157` | `f24105319afa06de426bec86fde91323df9db5d4` |
| T | 231654 | `3f30b1cabd03220c518afa4c0f5b800ca29f1d905e126ad421bffc8a2d5be3d7` | `6815b2794dfa9a6e91466bd46ea407bc40c711a7` |

## Provas positivas e alcance

**I1/I2, indexação executável.** I1 contém `[ %TM1.P := %MW20[%MW10] ]` nas linhas533 e553; I2 nas linhas518 e538. São duas leituras indexadas da tabela de tempos para o preset do timer, em rungs que calculam `%MW10`. Os rungs correspondentes têm `<LadderElements />` e `<IsLadderSelected>false</IsLadderSelected>`. I1 ainda possui o endereço indexado na tabela de animação, linha779; isso é evidência auxiliar e não substitui a ocorrência executável. Não há escrita em destino indexado nem comparação indexada nesses originais.

**F, float direto com gráfico.** No rung ordinal0, o campo `OperationExpression` é `%MF10 := INT_TO_REAL(%MW0)`, Row1/Column9/ChosenConnection=`Left` (linha79); a IL associada inclui a mesma atribuição entre colchetes, com espaços adicionais. No rung ordinal4, `ComparisonExpression` é `%MF18 >= %MF28`, Row0/Column2/ChosenConnection=`Left, Right` (linha517), com IL `LD [ %MF18 >= %MF28 ]`. Ambos estão com Ladder selecionado. O mesmo projeto tem `%MW0 := %IW1.0` como Operation na linha18, Row0/Column9/`Left`, e Coil `%M0` no rung4, Row1/Column10/`Left`. Este último comprova bit direto, não indexado.

**D, double word direto com gráfico.** No rung ordinal4: `OperationExpression=%MD18 := %MD32`, Row0/Column9/ChosenConnection=`Left, Right` (linha973), IL `LD 1` seguida de `[ %MD18 := %MD32 ]`. No rung ordinal8: `ComparisonExpression=%MD32 > 0`, Row0/Column3/`Left, Right` (linha1465), com IL `AND [ %MD32 > 0 ]` na sequência booleana. Ladder selecionado nos dois. Os operadores `<`/`>` no texto XML são escapados conforme XML; isso não muda a expressão lógica.

**T, testemunha adicional MD e distinção do alvo.** Original CPU=`TM221CE40T`, não CE40T da família M200. O rung ordinal10 contém `%MD10 := %MD10 + 1`, Operation Row0/Column9/`Left` (linha1400), e rungs6/11/16 contêm comparações MD em colunas3/5/7, com ramificações distintas. Demonstra que posição/conexão pertencem ao desenho concreto; não há uma única posição universal de Comparison.

A forma estrutural constatada nos originais é `LadderEntity/ElementType=Operation` com filho `OperationExpression`, ou `ElementType=Comparison` com `ComparisonExpression`; Row, Column e ChosenConnection são irmãos desses campos. Não há prova de um novo enum “IndexedOperation”. A combinação de sintaxe indexada documentada com `OperationExpression` pode fundamentar uma implementação em validação, mas não equivale a um original gráfico indexado aceito pelo editor.

## Manual, Automatic e %S20

**Manual explícito.** I1 linhas789-797 (I2/F/D/T também):

```xml
<MemoryBitsMemoryAllocation>
  <Allocation>Manual</Allocation>
  <ForcedCount>512</ForcedCount>
</MemoryBitsMemoryAllocation>
<MemoryWordsMemoryAllocation>
  <Allocation>Manual</Allocation>
  <ForcedCount>2000</ForcedCount>
</MemoryWordsMemoryAllocation>
```

`ForcedCount` é contagem serializada, não prova de um limite físico do TM200CE40T. As reservas do original não devem substituir o mapa do alvo.

**Automatic não demonstrado por enum explícito.** A tem `<MemoryBitsMemoryAllocation />` e `<MemoryWordsMemoryAllocation />` (linha2126 para words), sem `Allocation` e sem `ForcedCount`. Este é um exemplar de configuração omitida/default. Interpretá-lo como automático é hipótese até conferir o default do serializador ou abrir/salvar no editor; o relatório não transforma ausência de campo em prova. Não foi encontrado `<Allocation>Automatic</Allocation>` nos 99 XML válidos examinados.

O [Operating Guide Schneider EIO0000003281.04](https://www.se.com/us/en/download/document/EIO0000003281/), pp.47-48, documenta ambos os modos: Automatic aloca do offset0 até a maior referência usada ou simbolizada; seu exemplo `%MW20` aloca21 palavras. Manual reserva a quantidade configurada. O manual não publica nesse trecho qual valor XML omitido corresponde a cada modo. Página48 foi renderizada e inspecionada; cópia em `allocation-p48.png`.

**%S20: declaração não é tratamento.** Nos seis originais retidos, `%S20` aparece em `SystemBits/MemoryBit/Address`, acompanhado de símbolo/comentário do catálogo (por exemplo I1 linha953). Não foi encontrado `%S20` em InstructionLine nem nos campos de LadderEntity de qualquer um dos 99 XML válidos. Logo, nenhum deles comprova teste, correção ou reset executável da flag.

O [Generic Functions Library Guide Schneider EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/), pp.34-35, define base+conteúdo de `%MW` como endereço indexado. Publica MW/MD/MF/M e constantes apropriadas; em overflow (endereço negativo ou acima do maior word diretamente referenciado), `%S20` fica1 e o objeto usa índice efetivo0. A aplicação deve examinar a flag e limpá-la depois de corrigir o índice; o texto não diz para sobrescrever o word do índice. Página34 foi renderizada e inspecionada (`indexing-p34.png`). O [M100/M200 Programming Guide Schneider EIO0000002019.06](https://www.se.com/id/en/download/document/EIO0000002019/), p.323, confirma a flag para a família do alvo e o reset pelo programa. A interação de Manual com o maior endereço direto permanece para ensaio, como já registrado em CONTROL-FLOW-RESEARCH.md.

O Operating Guide p.55 exige nível funcional10.0 para bits indexados. Isso não autoriza deduzir o nível real a partir do sufixo numérico de `FunctLevelMan17_0` no XML. Não foi localizado original `%Mbase[%MWidx]` nesta amostra.

## Limites, reprodução e próximo ensaio

A busca usou GitHub Code Search/API com `extension:smbp` e refinamentos MW/MD/MF/Automatic, seguida de download RAW em commits fixos e análise XML. As duas páginas foram capturadas enquanto a contagem/ordem do índice variava (107 e111 resultados em chamadas distintas); portanto não constituem censo completo. Após deduplicação por Git blob foram101 candidatos,99 XML SMBP válidos e2 arquivos de assinatura truncados de outro projeto, descartados como prova PLC. Foram preservados somente os seis originais relevantes; os JSON de busca e `search-summary.json` registram o escopo. As primeiras consultas via `gh search code` deram falsos negativos por composição da consulta; as contagens acima vêm de `gh api search/code` e dos bytes examinados, não dessas consultas.

Nenhum arquivo estrangeiro foi renomeado como TM200CE40T nem reescrito para aparentar esse perfil. XML bem formado, consistência IL/gráfico dos exemplos e hashes não são aceitação oficial Schneider. Ainda falta gerar no Machine Expert Basic do perfil CE40T uma atribuição/uma comparação indexada e alocações Automatic/Manual; salvar, abrir, compilar e alternar IL/Ladder, conservando `%S20` e os limites. Essa lacuna gráfica não reduz o objetivo de equivalência do compilador e não é evidência de impossibilidade no PLC.

## Preservação no projeto

Os seis originais relevantes estão em `research/downloads/indexed-sources`, sem modificar bytes/CPU. Identidade e URLs fixadas estão em `docs/capabilities/INDEXED-SOURCES.json`; o diretório de downloads não entra no Git. Os caminhos /tmp acima registram o local original da pesquisa. Não se atribui aprovação runtime aos rungs com timer dinâmico ainda não implementado.

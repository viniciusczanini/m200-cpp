# Resultado local — 2026-11-05

Estado: protótipo experimental. O usuário autorizou desenvolver e testar localmente agora; Windows com software oficial e CLP será disponibilizado no futuro por SSH.

## Verificações executadas

- `make check`: **45 testes, zero falhas**.
- `uvx ruff check m200 tests m200c`: passou.
- `git diff --check`: passou.
- `make examples`: geração do exemplo e comparação do latch em 64 frames passou.
- Comparação do teste automatizado: C++ original, executor IL e C++ reconstruído concordaram em **200 frames pseudoaleatórios reproduzíveis**.
- Ciclo adicional do exemplo de clock: C++ → SMBP com fixture sintética → leitura da IL real → C++ → nova compilação; **64 frames** concordaram. A cópia `.configuration.smbp` permaneceu byte a byte igual ao projeto de entrada.

Esses resultados não significam aceitação no editor da Schneider, precisão física de tempo ou equivalência universal para C++/SMBP.

## Revisão independente

Uma revisão de código independente do commit inicial `83b1503` encontrou cinco problemas importantes. Todos receberam reprodução RED antes da correção e a suíte completa voltou a passar:

1. Declarações expandidas por macros escapavam do filtro de origem. Corrigido normalizando a localização de expansão antes de validar declarações. Testes: `test_macro_expanded_declarations_cannot_hide_executable_code` e `test_normal_macro_definitions_are_validated_as_cpp`.
2. Alguns contêineres de configuração e nomes reais `DiscretInput` não eram examinados. Corrigido com validação de campos e defaults inativos, recusando funções desconhecidas/ativas. Teste: `test_unknown_active_configuration_and_real_io_entry_names_fail_closed`.
3. Contêineres/campos XML duplicados podiam esconder instruções. Corrigido com cardinalidade por esquema do subconjunto, incluindo propriedades de timers e gráficos. Testes: `test_duplicate_xml_singletons_cannot_hide_program_data` e `test_unmodeled_xml_attributes_are_rejected`.
4. Um arquivo manual com nome de artefato conhecido podia ser removido sem constar no manifesto anterior. Corrigido exigindo propriedade pelo manifesto, além de conferir conteúdo. Teste: `test_rebuild_does_not_delete_a_file_absent_from_old_manifest`.
5. Descompilar sobre o próprio projeto podia apagar a entrada e contaminar a cópia de configuração. Corrigido recusando sobreposição de caminhos/aliases e saídas existentes, lendo a entrada antes da escrita e preparando ambos os resultados. Teste: `test_decompile_rejects_source_output_and_sidecar_aliases`.

Não houve uma segunda revisão independente; as correções foram verificadas pelos testes de regressão e pela suíte completa. Não ficaram achados menores relatados pelo revisor.

## Decisões e limites mantidos

- **Desenvolvimento antes do Windows:** autorizado pelo usuário. A geração experimental avança, mas a compatibilidade oficial permanece pendente. Custo: ainda não há um projeto comprovado no editor ou no CLP.
- **Subconjunto booleano:** aritmética inteira, loops e demais recursos ainda não implementados são recusados. Custo: programas que o hardware talvez suporte precisam esperar extensão do frontend.
- **Template exato:** usar um projeto autêntico TM200CE40T. A fixture sintética só testa o parser. Custo: o perfil/defaults reais ainda precisarão ser ajustados e validados quando houver editor.
- **Base XML de timer de 10 ms:** exportação é recusada porque sua enumeração não foi estabelecida por um exemplo inspecionado. Custo: alguns programas com mais de seis timers de resolução fina só têm IL/modelo local nesta versão.
- **XML ambíguo ou desconhecido:** rejeitado independentemente de o editor oficial aceitar, ignorar ou executar aquela forma. Custo: importação mais restrita que a oferta completa da Schneider.
- **Instâncias inteiramente não usadas:** permitidas; a regra de uma atualização incondicional vale para instâncias utilizadas. Custo: declarações não utilizadas ainda podem reservar recursos. A documentação foi alinhada ao comportamento.
- **Alocação conservadora:** esgotamento ou índice de timer inviável gera erro; não há promessa de alocação ótima. Custo: um programa pode precisar ser simplificado mesmo que uma futura otimização o fizesse caber.
- **Comparação nativa/IL:** ambos implementam um modelo local de tempo. Ela detecta divergências de tradução, mas não estabelece tempo real do CLP. Custo: precisão, fase, jitter, STOP/RUN, retenção, interface elétrica e operação com cargas aguardam testes físicos/oficiais.

A revisão deliberadamente não julgou firmware/nível funcional, conectividade real do Ladder, enumerações/defaults de todas as versões, comportamento físico ou recursos explicitamente fora do subconjunto. Esses limites não foram convertidos em alegações de compatibilidade.

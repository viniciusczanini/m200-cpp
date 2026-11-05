# Linguagem, fluxo e blocos para equivalência do TM200CE40T

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute sequencialmente com testes RED/GREEN e revisão independente da alteração integrada.

**Goal:** ampliar a linguagem e os blocos nativos até cumprir o contrato de equivalência, mantendo explícita a diferença entre implementação local e aceitação oficial.

**Architecture:** continuar no frontend Clang e no modelo nativo, sem tradução textual de C++ e sem inserir lógica opaca. Cada recurso deve atravessar C++, IR/IL, simulação, reversão e projeto quando seu formato estiver comprovado. Formatos sem evidência permanecem lacunas do backend, nunca justificativa para reduzir a meta.

**Tech Stack:** Python stdlib, Clang C++17, SDK C++, unittest, projetos SMBP originais e manuais Schneider.

**Spec:** `docs/PARITY.md` e `docs/superpowers/specs/2026-11-05-m200-cpp-design.md`.

## Global Constraints

- Alvo TM200CE40T. Não modificar o modelo de arquivos de outros controladores para fingir compatibilidade.
- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- Qualquer algoritmo nativo aceito no perfil deve ter expressão suportada em C++; limitações provisórias não reduzem a meta.
- Evidência documental não promove automaticamente um recurso a implementado.

## Review Focus

- Escritas/leitura de arrays devem manter alias e ordem; inicializadores parciais precisam zerar os elementos restantes como C++.
- Fluxo de controle não pode executar operações de ramos inativos, repartir laços entre scans ou alterar o alvo de break/continue em laços aninhados.
- Reexecução de um corpo no mesmo scan deve manter semântica dos blocos nativos, não usar a regra provisória de uma chamada estática para negar algoritmos suportados.
- Limites de endereço, labels, instruções e memória devem contabilizar os temporários; recusas por implementação devem ser identificadas como tal.
- O caminho inverso e a serialização devem recuperar o programa executável real; metadados com C++ original não são evidência de equivalência.

## Task 1: arrays de capacidade fixa

**Files:** `m200/frontend.py`, `tests/test_arrays.py`, `README.md`.

**Interfaces:** `Frontend.declaration`, `Frontend.expr`, resolução de lvalue em atribuições; elementos são os operandos bool/Number já existentes. Nenhuma nova instrução nativa é necessária para índices constantes.

- [x] Escrever testes com expectativas independentes para arrays bool/i16/i32/f32, globais persistentes e locais reinicializados, inicializadores parciais, alias entre elementos e escrita condicional.
- [x] Executar a nova suíte e observar falha por falta do recurso.
- [x] Implementar arrays fixos com resolução de elemento e validação de capacidade/índice/tipo, recusando explicitamente casos ainda não implementados.
- [x] Executar testes de ida e volta, C++ nativo e SMBP sintético; testar fronteiras/erros sem alterar os originais.
- [x] Rodar a suíte completa, documentar cobertura exata e registrar commit.

## Task 2: laços e fluxo nativo

**Files:** `m200/frontend.py`, novo módulo de fluxo se necessário, `m200/model.py`, `m200/il.py`, `m200/reverse.py`, `m200/project.py`, `m200/config.py`, `tests/test_control_flow.py`.

**Interfaces:** preservar `Program` e API CLI; representar labels/saltos explicitamente, com resolução e validação antes de execução. C++ `while`/`for`/`do`, `break` e `continue` devem manter execução no mesmo scan. O modelo de teste deve limitar execução infinita com erro explícito, sem alegar prova de WCET físico.

- [x] Conferir contratos nativos de labels/saltos, limites e reversibilidade gráfica em fontes primárias e projetos originais.
- [x] Escrever e executar testes RED de zero/múltiplas iterações, aninhamento, break/continue, guardas e sequência; incluir laço não terminante e destinos inválidos.
- [x] Implementar lowering, VM, reversão e emissão comprovada; recuperar C++ real com controle equivalente.
- [x] Confrontar com C++ nativo e oráculos independentes; testar serialização e recusas de formatos sem evidência.
- [x] Rodar suíte completa e registrar commit/resultados/lacunas.

## Task 3: contadores nativos %C

**Files:** módulo de contador, SDK, frontend/lowering/modelo/IL/VM/reversão/projeto/configuração; suíte específica.

**Interfaces:** API deve expor as entradas nativas e os estados/propriedades, preservar identidade explícita de instância e respeitar configuração/limites comprovados.

- [ ] Conferir CU/CD/R/S, simultaneidade/bordas/rollover, D/E/F, preset/value, IL e XML em fontes primárias; guardar incertezas.
- [ ] Escrever e observar RED com tabela manual de comportamento e erros de configuração, identidade e limite.
- [ ] Implementar todo caminho comprovado sem stubs de sucesso.
- [ ] Executar referência independente, ida e volta e stress reproduzível; suíte completa e commit.

## Continuação obrigatória do objetivo

As três tarefas acima são a próxima sequência executável, não o escopo final. O objetivo permanece ativo até fechar também: indexação dinâmica e tabelas/strings; funções/subrotinas e blocos do usuário; alocação/reuso sem reservas artificiais; flags numéricos e recuperação; mapa completo de objetos; retenção/lifecycle/tarefas/eventos/Grafcet; demais blocos C/FC/HSC/registradores/drum/SBR/SC/RTC/PID; pulsos/movimento/I/O imediato; expansões/perfis/configuração; Modbus dinâmico/servidor/scanner/EXCH/MSG e variantes de canais; backend gráfico completo e validação externa. Cada grupo requer plano específico ancorado no inventário, testes e evidência. Não concluir o objetivo por terminar somente esta sequência.

# Expansão da cobertura do TM200CE40T

Autorizada pelo usuário: testar intensamente e cobrir todos os recursos do modelo.
A execução é local; editor Windows e PLC estarão disponíveis no futuro.

1. Inventariar hardware, objetos, instruções, tipos, tarefas e configuração nas fontes oficiais. Registrar limites, versão funcional, conflitos entre documentos e evidência de cada recurso.
2. Reproduzir e corrigir falhas encontradas pelo teste adversarial, antes de ampliar o frontend.
3. Acrescentar tipos numéricos com operações explícitas da biblioteca (sem herdar promoções/overflow indefinido de C++), memória compartilhada MW/MD/MF, IL, execução e caminho inverso. Testar limites, tipos e equivalência com execução C++ independente.
4. Transformar o inventário em catálogo consultável, com estados separados para frontend, IL, reversão, XML, simulação e validação oficial. Recurso inventariado não significa implementado. Toda lacuna deve aparecer.
5. Estressar frontend, VM, parser e recompilação com sementes reproduzíveis e fronteiras dos recursos. Revisar as mudanças e corrigir falhas com regressões.
6. Documentar o que passou localmente e os passos que dependem do Windows/editor/PLC. Não afirmar biblioteca completa ou compatibilidade oficial antes da evidência correspondente.

Não criar stubs que retornem sucesso para periféricos não simulados. Não adivinhar enums ou configurações XML para aumentar artificialmente a cobertura. A conclusão da biblioteca completa exige continuar sobre as lacunas explícitas; esta etapa entrega o máximo verificável no ambiente disponível.

## Resultado desta etapa

1. Primeira auditoria cruzada consolidada: 250 registros e 13 conflitos, com fontes/páginas/hashes. O inventário pode crescer com novas evidências; não é uma prova de exaustividade.
2. Falhas adversariais e da revisão corrigidas, com reproduções que falharam antes dos consertos.
3. Subconjunto numérico implementado: três tipos, 47 intrínsecos, memória compartilhada, comparações, guardas, IL/VM/reversão e XML Operation/Comparison. Biblioteca completa permanece aberta.
4. Catálogo consultável pela CLI, sem promover estados a partir de documentação. Lista separada da biblioteca atual.
5. Verificação final: 91 testes locais; 37.716 scans de estresse; exemplos; lint e diff. Roteiros e resultados preservados.
6. Lacunas explícitas em docs/capabilities/README.md e roteiro externo atualizado. Acesso futuro ao editor/PLC é necessário para cumprir a garantia final; não foi declarado compatível oficialmente.

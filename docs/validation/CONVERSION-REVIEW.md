# Revisão independente de conversões — 2026-11-06

Baseline bd5bcf3. Revisor conversion_review, contexto novo e sem editar.
Contrato em `../capabilities/CONVERSIONS.md`, plano de 2026-11-06. Meta integral
mantida; não há aceitação no editor nem execução física comprovadas.

A revisão encontrou dois P2 reproduzíveis:

1. O despacho por nome de OPS capturava helpers globais com nomes dos novos
   intrínsecos. Um helper bool int_to_bcd(bool) válido antes da etapa passava
   a falhar por tipo i16. A reprodução confirmou o erro. O frontend passou a
   exigir a qualificação plc:: para todos os intrínsecos numéricos. O teste
   cobre os seis novos nomes e add_i16 globais, juntamente com APIs qualificadas.
2. A tabela G60 permite MW/KW (e imediatos em CONCATW), mas o parser aceitava
   propriedades de bloco diretamente em DWORD/CONCATW. comm_error() do Modbus
   também podia produzir essa forma pela biblioteca. Os testes confirmaram a
   aceitação raw indevida e ausência de snapshot no C++ gerado. O parser agora
   recusa essas fontes diretas; o lowering copia propriedades para MW antes da
   instrução. O caso válido de BTI/ITB com propriedades de bloco foi preservado.

Ambos receberam testes RED→GREEN. O teste Modbus usa update inativo e configuração
Serial1/RTU/master explícita no template de ensaio, sem tráfego ou sucesso
fabricado. Percorre SDK/VM/JSON/normalização, exportação e C++ do XML real até
novo XML. Testes de tipos/canais e do fluxo nativo continuam separados.

O revisor apontou P3 sobre força do teste de alias: as fontes inicialmente
ficavam na posição final, permitindo um mutante sem captura. Como captura dos
dois argumentos é requisito explícito do Review Focus, a cobertura foi tratada
como necessária nesta etapa. Foi acrescentado MD2:=CONCATW(MW3,MW2), com MW2=1
e MW3=2, esperando 65538; escrita prematura produziria 131074. Nenhum defeito
foi atribuído ao VM atual, que já captura ambos os operandos.

O revisor executou 12 testes focados em 3,736 s antes das correções. O autor
executou os 16 testes ampliados em 6,838 s após a correção. A rodada integral e
seus hashes ficam em `CONVERSION-LOCAL-RESULTS.json`; esses reruns focados não
entram na contagem final de scans.

Não foram encerradas as lacunas de extensão de sinal física de DWORD,
recuperação de BCD inválido, outros bancos/expressões, nível funcional/perfil,
editor ou PLC. Não há achado menor deliberadamente deixado sem tratamento.

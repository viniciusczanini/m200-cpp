# Validação

- Meta final: equivalência funcional com o perfil oficial do TM200CE40T,
  conforme docs/PARITY.md. Qualquer algoritmo nativo aceito nesse perfil deve
  ter expressão suportada em C++; limitações provisórias não reduzem a meta.
- Distinguir lacuna da ferramenta de impossibilidade ou limite real do PLC.

- Todos os testes e builds são locais. Não criar CI/GitHub Actions.
- A compatibilidade da ferramenta deve ser validada no Machine Expert Basic e no TM200CE40T.
- Não afirmar compatibilidade oficial a partir de XML, testes próprios ou round trip.
- Construções/instruções desconhecidas falham explicitamente.
- Não transmitir programas, alterar firmware ou acionar cargas automaticamente.

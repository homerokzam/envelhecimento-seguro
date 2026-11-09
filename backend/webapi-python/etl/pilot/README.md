# Referência do piloto SIH/SUS — 2024

Consulta realizada no [TABNET oficial](https://tabnet.datasus.gov.br/cgi/deftohtm.exe?sih/cnv/fruf.def) em 08/11/2026.

- Tabela: Morbidade Hospitalar do SUS por Causas Externas, por local de residência, Brasil por região e UF.
- Linha: Unidade da Federação. Coluna: Não ativa.
- Períodos: os 12 meses de processamento de 2024.
- Grupo de Causas: W00–W19 Quedas. Faixa Etária 1: 60 a 69, 70 a 79 e 80 anos e mais. Demais filtros: todas as categorias.
- Conteúdo: Internações, Valor total, Dias permanência e Óbitos. A coluna `valor_aprovado` usa **Valor total**, pois o ETL soma `VAL_TOT`.
- BR é a linha TOTAL; DF é a linha 53 Distrito Federal; SP é a linha 35 São Paulo.

O critério de caso do ETL (diagnóstico principal S00–T98 + W00–W19 em campo secundário) é o da tabela de causas externas do TABNET; contar W00–W19 em qualquer campo inflava as internações em ~5% e os óbitos em 12–35%.

O piloto compara os totais calculados do RD às referências do CSV. Só a diferença em internações decide a aprovação, com a tolerância definida no código. A presença das referências não garante que os dados extraídos conciliem.

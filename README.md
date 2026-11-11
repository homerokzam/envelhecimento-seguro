# Envelhecimento Seguro

Painéis de apoio à pesquisa sobre internações por quedas em pessoas de 60 anos ou mais, com dados reais do SIH/SUS. O projeto roda localmente, sem banco de dados ou contêineres.

## Executar

Requisitos: SDK .NET 10, [uv](https://docs.astral.sh/uv/) com Python 3.14 e Node compatível com o Vite 7 (20.19+ ou 22.12+).

```sh
npm --prefix frontend/webapp ci
(cd backend/webapi-python && uv sync --extra etl --python 3.14)
dotnet run --project aspire/EnvelhecimentoSeguro.AppHost
```

Só `npm run dev` **não basta**: o Vite apenas serve a interface e repassa `/api` para o .NET, que repassa para o Python. Sem as três camadas aparece "Não foi possível conectar ao serviço de análise". Suba tudo pelo Aspire (acima).

Sem base local, o painel fica vazio. Para uma **amostra real e pequena** (2023 e 2024, DF, GO e AP, ~72 arquivos, minutos; o Brasil fica parcial):

```sh
(cd backend/webapi-python && .venv/bin/python -m etl build --sample)   # ou --years 2023,2024 --ufs DF,GO,AP,SP
```

No painel do Aspire, abra o endpoint de `webapp`. O AppHost usa `backend/webapi-python/.venv` (criado pelo `uv sync`) quando existe; senão cai no `python3.14` do PATH, que precisaria ter PySUS e pandas. `PYTHON_EXECUTABLE` força outro interpretador. A API de consulta em si só usa a biblioteca padrão; o PySUS só é exigido no download.

## Arquitetura

```text
React (antd, Plotly) → /api (proxy do Vite) → Web API C#/.NET 10 → API Python 3.14
                                                                        ↓
                                              data/versions/<versão>/{dataset.csv, manifest.json}
```

- O AppHost inicia os três processos. Só o serviço Python acessa o SUS, e apenas quando alguém pede o download. O navegador nunca chama o SUS nem o Python diretamente.
- O .NET repassa `GET /api/dashboard`, `GET /api/export.csv`, `GET /api/dataset/status` e `POST /api/dataset/update`.
- O painel sempre lê uma **versão congelada** da base. Cada carga gera uma nova versão e a troca é atômica; ficam a versão ativa e a anterior.
- Frontend em TypeScript: antd (interface), Plotly (`plotly.js` + `react-plotly.js`, carregado sob demanda), zustand (estado dos filtros), TanStack Query + axios (dados do servidor).

## Dados reais (SIH/SUS, DATASUS)

Fontes originais: Ministério da Saúde/DATASUS, Sistema de Informações Hospitalares do SUS (SIH/SUS, arquivos RD, FTP `ftp.datasus.gov.br`) e projeção populacional MS/SEIDIGI/DEMAS (IBGE) pelo TABNET. O PySUS é só a ferramenta de acesso.

Sem base carregada, o painel mostra "Nenhuma base carregada" e o botão **Baixar dados do SUS**. O download nunca começa sozinho: a carga completa são cerca de 3.564 arquivos mensais por UF (2015–2025, o período do estudo), leva horas e ocupa alguns GB em `backend/webapi-python/data/cache`. O botão **Atualizar dados** processa o que falta e rebaixa os 6 meses mais recentes (o SIH reprocessa meses recentes). Se uma carga falha, a versão anterior continua ativa. Pela linha de comando: `cd backend/webapi-python && python -m etl build [--refresh]`.

Definição (conforme o planejamento da pesquisa):

- **Caso:** AIH tipo 1 (`IDENT=1`) cujo diagnóstico principal (`DIAG_PRINC`) é uma lesão (CID-10 S00–T98) e que traz a causa externa W00–W19 em campo secundário (`DIAG_SECUN`, `DIAGSEC1–9`). É o mesmo critério da tabela de causas externas do TABNET, por isso o piloto concilia. Internações por outro motivo com a queda só como informação adicional não entram e são contadas nas exclusões (`queda_sem_lesao_principal`).
- **Recorte:** 60 anos ou mais (60–69, 70–79, 80+), UF de **residência** (`MUNIC_RES`), ano de **processamento** (`ANO_CMPT`), só anos completos.
- **População:** projeção IBGE/Ministério da Saúde, edição 2024 (TABNET `projpop2024uf`), por UF, sexo e faixa 60–69, 70–79 e 80+. O ETL consulta o TABNET sozinho, uma vez por ano e sexo, e guarda o resultado em `data/cache/population_tabnet_2024.json`. Alternativa manual: informe um CSV em `POPULATION_CSV` (UTF-8, `year,uf,sex,age,population`, idade simples 0–90; 90 = 90+), que tem prioridade sobre o TABNET.
- **Perfil clínico e hospitalar:** além do estrato ano × UF × faixa × sexo, a carga grava `profile.csv` (formato longo: `year,uf,age,sex,dim,value` + internações, óbitos, dias e valor) com dez dimensões: tipo de lesão (S/T no principal), tipo de queda (W00–W19), mês e dia da semana da internação (`DT_INTER`), caráter (`CAR_INT`), tipo de procedimento (`PROC_REA`), UTI (`UTI_MES_TO`), motivo de saída (`COBRANCA`), natureza jurídica do hospital (`NAT_JUR`) e raça/cor (`RACA_COR`). Em cada estrato os valores de cada dimensão somam exatamente a base principal (validado ao carregar). `municipios.csv` traz o total por município de residência (nomes do IBGE), sem taxa, pois a projeção não tem população municipal. Bases anteriores a isso não têm os dois arquivos e mostram o aviso para atualizar.
- **Sexo ignorado:** entra em "Ambos" nas contagens e na taxa total, sem população no denominador; o total aparece em nota e no CSV exportado.
- **Exclusões** (idade ignorada, residência no exterior ou inválida) são contadas por ano no `manifest.json` e exibidas nas notas do painel.
- **Rastreabilidade:** o `manifest.json` guarda versão, data, versão do PySUS, edição da população, definição de caso, exclusões, resultado do piloto e hash do CSV; ele é repetido no cabeçalho (`#`) do CSV exportado e no rodapé dos gráficos em PNG.

### Piloto de conciliação com o TABNET

Antes de publicar qualquer versão, o ETL compara o RD de 2024 (Brasil, DF e SP) com valores do TABNET. Preencha `backend/webapi-python/etl/pilot/tabnet_2024.csv`:

```csv
escopo,internacoes,obitos,dias_permanencia,valor_aprovado
BR,0,0,0,0
DF,0,0,0,0
SP,0,0,0,0
```

Consulta no TABNET: Morbidade hospitalar do SUS → Causas externas, por local de residência → categoria "Quedas", 60 anos ou mais, 2024. Diferença superior a 1% em internações bloqueia a publicação; o relatório fica em `data/pilot_report.json`. A faixa "Quedas" do TABNET corresponde a W00–W19 como causa externa de uma internação por lesão (conferido com os arquivos RD do DF de 2024).

## Verificar

```sh
dotnet build EnvelhecimentoSeguro.slnx
npm --prefix frontend/webapp run build
(cd backend/webapi-python && python3.14 -m unittest -v)
```

Os dados sintéticos existem só como fixture dos testes (`analytics/fixtures.py`) e nunca são carregados pela API. Filtros inválidos (inclusive ano inicial maior que o final) retornam HTTP 400. Os registros representam eventos hospitalares, não pessoas únicas nem saúde mental após a alta.

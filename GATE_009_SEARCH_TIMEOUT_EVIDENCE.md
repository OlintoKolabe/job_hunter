# Gate 9 — timeout do Caçador, 23/10/2026

## Falha observada e reproduzível

- Captura real da UI autenticada: `Busca parcial` e `signal timed out`.
- `src/Opportunities.jsx` esperava `await requestJson('/api/search-jobs')`
  antes de iniciar o catálogo e usava `AbortSignal.timeout(30000)` para cada
  tentativa. Assim, duas tentativas de 30s podiam impedir toda a listagem.
- `app.py /api/search-jobs` executava `collect(...)`, depois Himalayas,
  Remotive e RemoteOK em sequência, depois enriquecimento, filtros e Neon.
- Consultas públicas reais, somente leitura, papéis `Product Manager, Product
  Owner`, país BR: 25 consultas de coletores, 872 anúncios, 4 fontes com erro,
  **24,12 s** só na coleta inicial. Himalayas retornou 37 anúncios em **7,08 s**
  quando medido separadamente. Ambas antecediam os acessos ao banco.
- Mesmo conjunto de fontes executado em concorrência com quatro workers,
  sem reduzir anúncios: **16,82 s**; 872 + 37 + 9 + 99 anúncios das quatro
  tarefas, respectivamente. Não é comparação de percentis/produção.
- Radix inHire: lista com 111 anúncios em 6,64 s; oito detalhes públicos
  reais em 7,21 s, oito respostas completas, zero falhas; a busca original
  podia adicionar essas consultas antes do Neon.

## Intervenções delimitadas

1. Retirar a dependência temporal da UI entre primeiro agregador e varredura
   do catálogo: falhas do primeiro não cancelam os demais.
2. Reutilizar quatro coletores existentes em concorrência, sem fontes novas.
3. Adiar detalhes inHire quando a etapa precedente tiver consumido a janela
   de tempo, sem converter desconhecido em elegível.
4. Preservar e tentar novamente, no máximo uma vez, até oito lotes falhos;
   não esconder falhas remanescentes nem duplicar URLs exibidas.
5. Medir tempos reais por requisição na UI e no header/log HTTP, além dos
   contadores de metadados já publicados na branch.
6. Executar testes legados, novos contratos, build e busca real autenticada
   no canário antes de homologação humana.

## Limites e pendências

- A coleta pública de fontes e os detalhes inHire foram medidos fora do Neon.
  Não representam latência p95 da API autenticada no Render.
- Se o primeiro agregador demorar mais que 30s, sua fonte falha de forma
  identificada; o catálogo independente continua e conserva resultados.
- Os lotes recuperados são idempotentes na listagem por URL; as métricas
  brutas por lote podem repetir anúncios já recebidos, como informado na UI.
- O Gate 7 exige abrir a UI real, buscar por múltiplas fontes e confirmar
  ausência de novo `signal timed out` como erro que encerra a busca.
- Não há inclusão de IA, tabelas, dependências, algoritmos de nota, CV,
  candidatura automática, Vercel ou GitHub Actions.
# Canary end-to-end correction (2026-10-23, UTC)

The authenticated Render canary build `8c858d7` exposed a remaining regression:
the first `/api/catalog/scan` request returned HTTP 200 in **27,695 ms**;
the second returned HTTP 200 in **51,104 ms**, after the browser had
aborted its 30,000 ms request and marked the batch failed. The initial
`/api/search-jobs` request likewise timed out client-side. Those are live
Render logs for the user-selected `Product Manager, Product Owner`, BR,
remote, seven-day search, not invented fixtures.

Code inspection found that `collect(..., "all")` in the initial route
repeated catalog-board collection while `/api/catalog/scan` was already
scanning those same boards. The original initial collection locally
required 24.12 seconds **before** remote feed and database operations.
Separate real provider checks returned Workable 31 ads from four terms
in 5.19 seconds and Jobgether zero from four terms in 5.59 seconds.
The initial route now queries only those two keyword-search providers plus
the three existing public remote feeds; catalog boards remain exclusively
in their existing catalog scanner, with no source removed. The browser
allows 70 seconds, exceeding the measured 51.104 seconds, before declaring
a batch unavailable; successful batches are not replayed.

Human acceptance remains contingent on observing a complete or explicitly
partial search on the new canary build; no single smoke test can certify
every provider at every moment.


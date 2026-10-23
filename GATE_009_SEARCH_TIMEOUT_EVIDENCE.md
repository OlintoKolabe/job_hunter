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

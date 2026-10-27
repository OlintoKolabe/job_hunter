# Baseline e rollback — Quickin/inHire (27/10/2026)

## Estado protegido

- Repositório: `OlintoKolabe/job_hunter`.
- Branch de produção principal: `main`.
- SHA de referência confirmado por `git ls-remote`: `53712d72bf8d4ef8ee10e05ad2f014c6b716710b`.
- Referência imutável operacional (não mover): `rollback/main-reference-quickin-inhire-20261027` apontando ao SHA acima.
- Branch operacional Render na captura: `feat/phase1-web-foundation`, SHA `89fefe5fb7ee8fdfbb57429bfec679576d9ff3cb`; **é diferente da main**, portanto comparar separadamente antes do deploy.
- Desenvolvimento isolado: `fix/quickin-inhire-p0-p2-20261027` derivado da main.

## Evidência Gate 9

- Neon `jh_catalog_checks`: Quickin 27 quadros, 0 aprovados, 0 vagas; inHire 103 quadros, 101 aprovados, 3154 anúncios brutos (snapshot das últimas coletas, não vagas elegíveis).
- BotCity `https://jobs.quickin.io/botcity/jobs`: 11 anúncios públicos; `account_id` recuperado do objeto `site` no payload HTML; API pública com o ID real responde `docs:11,total:11,limit:30,page:1,pages:1`. Coletor anterior usava slug como `account_id` e procurava `jobs/data/results`, ignorando `docs`.
- InHire BRQ: endpoint público retornou 71 anúncios, correspondentes aos 71 registrados.
- inHire `grupotaking` e `mtrix`: resposta pública válida e `jobsPage: []`; erro de interpretação de ausência de vagas, não falha de API.

## Gate de publicação

1. Atualizar testes reproduzindo os contratos de resposta reais, primeiro vermelhos e depois verdes.
2. Validar catálogo real × extração × classificação e JDs sem interferir nos filtros e perfis.
3. Testar regressões de busca, isolamento de perfis, CV/ATS, histórico, lint/compilação de frontend sem GitHub Actions nem Vercel.
4. Conferir apenas diff de Quickin/inHire e documentação; rejeitar mock, modificações no banco e alterações em escopo adjacente.
5. Expor canário de versão completa baseado na main, validar por usuário, comparar SHAs novamente e somente então considerar merge e sincronização operacional Render.

## Procedimento de recuperação

No caso de regressão, **não** resetar/regravar a main silenciosamente. Suspender a promoção e usar a referência exata acima como base de uma reversão aprovada, verificando previamente commits concorrentes na main e a versão efetivamente implantada no Render. Não restaurar dados de produção como parte de rollback de código.

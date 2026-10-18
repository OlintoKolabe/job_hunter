# Job Hunter — Fase 1 (web)
Primeira entrega visual: login, painel React e verificação real do Neon. **Sem busca de vagas, sem geração de CV, sem candidaturas automáticas.**

## Infraestrutura
- Render web service **Free**, runtime Python
- Neon PostgreSQL em projeto separado **Free**
- Branch de implantação: `feat/phase1-web-foundation`
- Build: `npm install && npm run build && pip install -r requirements.txt`
- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`

## Variáveis privadas no Render
- `APP_SECRET`: cadeia aleatória forte (assinatura da sessão)
- `APP_PASSWORD`: senha exclusiva para acesso ao painel
- `DATABASE_URL`: connection string privada do Neon (SSL)
Nunca coloque segredos no repositório público.

## Homologação
1. Abrir link e verificar login; senha inválida deve falhar.
2. Senha válida abre painel; verificar responsividade e logout.
3. Cartão Neon deve informar `Conexão confirmada` somente após `SELECT 1`.
4. Vagas históricas são apenas referência ao CSV fornecido; importação ainda não foi feita.
5. Nenhuma função de busca, CV ou candidatura foi introduzida.

## Gate
Escopo autorizado: arquivos de frontend e servidor estritamente necessários para UI + autenticação + healthcheck Neon. O validador de escopo existente precisa ter seu fluxo de contratos corrigido em tarefa separada; a criação de `scope/active.json` contradiz a regra atual que impede mudar esse mesmo arquivo. Nenhuma GitHub Action foi adicionada.


## Marco de rollback antes do merge do Bloco 3 (17/10/2026)
- Repositório: `OlintoKolabe/job_hunter`.
- `main` antes do merge: `93d092e2a10297f3eb580d02f4552f7fee91f12a`.
- Referência imutável do conteúdo original: commit acima.
- Branch de recuperação: `rollback/main-pre-bloco3-20261017`, criada a partir daquele commit **antes** de alterar a `main`.
- Origem do merge: `feat/phase1-web-foundation` (inclui alterações da branch `fix/phase3-generalization-gate`).
- Atenção: a `main` anterior não continha o Job Hunter atual; o merge inclui todas as mudanças acumuladas da branch de implantação, não somente o último ajuste de busca.
- Para restaurar, primeiro conferir diferenças entre o commit acima e a `main` atual, então criar PR de reversão/reaplicação do snapshot original ou realizar reset controlado da `main` para aquele commit com autorização explícita. Não efetuar rollback automaticamente: o reset destrutivo pode descartar alterações feitas após este marco.
- Serviço Render: a branch de deploy é `feat/phase1-web-foundation`. Merge na `main` **não** altera automaticamente o serviço Render.
- Política: GitHub Actions e Vercel proibidos; nenhuma alteração na `main` sem autorização.

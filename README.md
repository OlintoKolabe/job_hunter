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

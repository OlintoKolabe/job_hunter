# Integração do histórico do Caçador (somente leitura)

## Base e autenticação

- Produção: `https://olinto-job-hunter.onrender.com`
- Em uma sessão autenticada no navegador, emitir o token exclusivo do perfil por `POST /api/integrations/history-token`. Essa é a única operação de configuração inicial; **não** é uma exportação.
- A resposta contém `token`, `token_type: Bearer`, `scope: history:read` e `expires_in_seconds: 2592000` (30 dias).
- Salvar o token apenas no gerenciador de segredos do agente que fará as candidaturas. Nunca colocar o token no repositório, no prompt ou nos logs.
- O token é restrito a um perfil, expira após 30 dias e é invalidado quando a versão de sessão muda (por exemplo, após alteração de senha).
- Cada consulta exige `Authorization: Bearer <token>`; cookie de sessão, senha e token de CV não concedem acesso a esta rota.

## Consulta online

`GET https://olinto-job-hunter.onrender.com/api/integrations/history?limit=250&state=all`

Filtros:
- `state=all|applied|discarded`, padrão `all`.
- `limit=1..500`, padrão `250`.
- `before_id=<id>` para a próxima página, sempre usando o `next_before_id` recebido. O histórico é consultado no banco atual **em toda requisição**, sem exportação ou cache.

Exemplo de corpo (valores fictícios):

```json
{
  "schema_version": 1,
  "profile": "7",
  "generated_at": "2026-10-31T15:30:00+00:00",
  "state_filter": "all",
  "total_remaining": 2,
  "items": [
    {
      "id": 123,
      "url": "https://jobs.example/123",
      "normalized_url": "jobs.example/123",
      "company": "Empresa Exemplo",
      "title": "Product Manager",
      "state": "applied",
      "original_state": "Candidatado",
      "date": "2026-10-30",
      "source": "Greenhouse",
      "reason": ""
    }
  ],
  "next_before_id": null
}
```

O campo `state` é `applied`, `discarded` ou `other`, preservando o valor original em `original_state`. Em modo multiusuário, `profile` identifica exclusivamente o perfil do token.

## Fluxo do agente externo

1. Antes de iniciar **cada busca**, consultar todas as páginas da API.
2. Antes de executar **cada candidatura**, consultar novamente o histórico.
3. Comparar principalmente `normalized_url`, depois o URL original. Uma vaga com `applied` ou `discarded` não deve ser candidatada.
4. Em caso de HTTP 401, renovar o token no navegador autenticado; em HTTP 5xx/timeout, interromper candidaturas até recuperar o histórico, para não duplicar ações.
5. Como esta API é somente leitura, o outro agente não consegue marcar uma nova candidatura no Caçador: as decisões feitas fora dele devem ser registradas na interface do Caçador para passarem a constar do histórico.

A API não automatiza candidaturas nem acessa o LinkedIn. Ela compartilha o histórico atual para que outro sistema consulte os bloqueios de duplicidade.

## Instrução de configuração inicial no navegador

Com o Caçador aberto e autenticado, executar no console do navegador:

```js
const response = await fetch("/api/integrations/history-token", {method: "POST", credentials: "same-origin"});
if (!response.ok) throw Error("Não foi possível emitir o token: " + response.status);
const {token, expires_in_seconds} = await response.json();
// Armazene token diretamente no cofre de segredos do agente externo.
// Não cole o valor em chat, issues, repositórios ou arquivos versionados.
console.log("Token emitido; validade em segundos:", expires_in_seconds);
```

Para copiar o token ao cofre de segredos sem exibi-lo no console, use `await navigator.clipboard.writeText(token)` na sessão do próprio navegador e apague o conteúdo da área de transferência após a configuração.

## Teste sem revelar o segredo

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $CACADOR_HISTORY_TOKEN" \
  "https://olinto-job-hunter.onrender.com/api/integrations/history?limit=1"
```

O servidor devolve `Cache-Control: no-store`. A credencial nunca é enviada para endpoints de terceiros.

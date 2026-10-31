# API de integração do Aplicador de Vagas — Caçador

Produção: `https://olinto-job-hunter.onrender.com`

O Caçador realiza as buscas e devolve as vagas com URLs. O Aplicador externo analisa as vagas, gera currículos e realiza candidaturas fora do Caçador. Após uma candidatura confirmada ou um descarte decidido, o Aplicador comunica a decisão de volta ao Caçador. Todas as operações respeitam o perfil do token.

## Autenticação inicial (uma única configuração por token)

Com uma sessão de usuário autenticada no navegador:

`POST https://olinto-job-hunter.onrender.com/api/integrations/applicator-token`

A resposta tem `token`, `token_type: Bearer`, `scopes` e `expires_in_seconds: 2592000` (30 dias). Escopos: `history:read`, `jobs:search`, `jobs:disposition`. O token anterior `/api/integrations/history-token` **continua sendo somente leitura** e não permite buscar nem registrar decisões.

Em todas as chamadas do Aplicador:

```http
Authorization: Bearer <TOKEN_DO_APLICADOR>
```

Guarde a credencial no gerenciador de segredos do Aplicador, por exemplo `CACADOR_APPLICATOR_TOKEN`. Não escreva o valor em código, chat, logs nem arquivos versionados. A alteração de senha/versão de sessão invalida os tokens anteriores.

## 1. Buscar vagas pelo motor do Caçador

```http
POST https://olinto-job-hunter.onrender.com/api/integrations/jobs/search?country=BR&mode=remote&days=7&source=all&sort=newest
Authorization: Bearer <TOKEN_DO_APLICADOR>
```

O endpoint utiliza **exatamente o mesmo mecanismo** da busca de vagas da interface do Caçador, inclusive as fontes, os filtros e a exclusão das vagas candidatadas/descartadas. Parâmetros são query string e o corpo não é necessário.

- `roles` é opcional: quando omitido, usa os cargos salvos no perfil autenticado. Se informado, deve conter apenas cargos desse perfil.
- `country`: `BR` para Brasil; `mode`: `remote`; `days`: `7` (ajuste conforme a busca desejada).
- `source`: `all` ou uma fonte suportada pelo Caçador.
- A resposta preserva o contrato da busca existente: `items` (vagas confirmadas), `review_items` (vagas ainda não confirmadas) e os metadados/estatísticas de filtros e fontes.
- Cada vaga contém os campos disponibilizados pelo provedor, especialmente `url`, `title`, `company`, `source`, descrição e indicadores de elegibilidade quando presentes.
- O Aplicador deve tratar `review_items` como vagas que exigem verificação adicional antes de candidatar; não descartá-las silenciosamente.

## 2. Consultar o histórico atualizado

```http
GET https://olinto-job-hunter.onrender.com/api/integrations/history?limit=500&state=all
Authorization: Bearer <TOKEN_DO_APLICADOR>
```

Parâmetros `state=all|applied|discarded`, `limit=1..500`, `before_id=<next_before_id>`. Ler todas as páginas até `next_before_id: null`.

Formato da resposta (dados fictícios):

```json
{
  "schema_version": 1,
  "profile": "7",
  "generated_at": "2026-10-31T15:30:00+00:00",
  "state_filter": "all",
  "total_remaining": 1,
  "items": [{
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
  }],
  "next_before_id": null
}
```

A leitura consulta `jh_history` em cada requisição, sem exportação manual ou cache. Os estados são `applied`, `discarded` e `other`.

## 3. Registrar candidatura ou descarte no Caçador

```http
POST https://olinto-job-hunter.onrender.com/api/integrations/jobs/disposition
Authorization: Bearer <TOKEN_DO_APLICADOR>
Content-Type: application/json
```

Corpo para candidatura **concluída e confirmada**:

```json
{
  "url": "https://jobs.example/123",
  "title": "Product Manager",
  "company": "Empresa Exemplo",
  "state": "Candidatado",
  "source": "LinkedIn"
}
```

Para descarte decidido, use `"state": "Descartado"`. Os valores de `state` são sensíveis a maiúsculas; apenas `Candidatado` e `Descartado` são aceitos. URL e cargo são obrigatórios. A rota reutiliza a decisão persistida pelo Caçador, com controle de duplicidade por URL e substituição explícita de estado se necessário.

Resposta: `saved: true`, `state` e indicadores `already_recorded`/`updated` conforme o caso.

**Só marque `Candidatado` depois de confirmar que o envio aconteceu de fato.** Não o faça por tentativa, clique ou formulário iniciado. Não marque `Descartado` sem decisão fundamentada do usuário/sistema. Em caso de resposta ambígua ou timeout, consulte o histórico antes de repetir a chamada.

## Fluxo operacional obrigatório

1. Ler o histórico completo.
2. Buscar vagas no Caçador (sem repetir a busca externamente se não necessário).
3. Analisar `items` e `review_items`, abrir as URLs e decidir quais vagas são elegíveis.
4. Antes da candidatura, **reconsultar o histórico** para evitar duplicidade.
5. Realizar a candidatura fora do Caçador.
6. Confirmado o sucesso, chamar `jobs/disposition` com `Candidatado`. Em caso de descarte decidido, enviar `Descartado`.
7. Em HTTP 401, renovar a credencial; em falha de rede/5xx na leitura do histórico, suspender novas candidaturas até restabelecer a verificação.

O Caçador **não** faz login no LinkedIn nem se candidata automaticamente. O Aplicador executa essas etapas; o Caçador fornece busca e mantém o histórico sincronizado.

## Configuração inicial no navegador

Com o Caçador aberto e autenticado, no console do navegador:

```js
const response = await fetch("/api/integrations/applicator-token", {
  method: "POST",
  credentials: "same-origin"
});
if (!response.ok) throw Error("Emissão falhou: HTTP " + response.status);
const {token, scopes, expires_in_seconds} = await response.json();
await navigator.clipboard.writeText(token);
console.log("Token do Aplicador copiado.", {scopes, expires_in_seconds});
```

Cole a credencial diretamente no gerenciador de segredos do outro sistema; nunca no chat.

## Teste por linha de comando (sem imprimir o token)

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $CACADOR_APPLICATOR_TOKEN" \
  -X POST "https://olinto-job-hunter.onrender.com/api/integrations/jobs/search?country=BR&mode=remote&days=7&source=all"
```

Somente execute a operação de disposição após uma candidatura realmente concluída; não a utilize como teste sem uma vaga de homologação autorizada.

# Gate 9 — Evidência obrigatória antes de qualquer correção

Nenhuma correção pode ser feita por suposição. Cada alteração precisa registrar:

1. Evidência real da falha, proveniente do código, provedor ou banco de dados.
2. Caso mínimo reproduzível e comportamento esperado.
3. Identificação da etapa e da causa no mecanismo existente.
4. Teste que falha antes e passa após a alteração.
5. Verificação das regressões e proteção de escopo.

Dados inconclusivos não são justificativa para declarar uma correção comprovada.

## Amostra de referência (23/10/2026)

- 40 quadros / 1.334 anúncios brutos: Greenhouse 670, inHire 277,
  Ashby 210, Lever 169, BambooHR 8.
- 277/277 inHire sem JD e data na listagem; os 20 detalhes públicos
  consultados tinham descrição e data. O mesmo endpoint de detalhes já
  existia em `jd_enrichment`, mas operava depois dos filtros.
- Himalayas: respostas públicas traziam `locationRestrictions` também como
  strings; o adaptador anterior aceitava apenas dicionários. As buscas
  separadas de Product Manager e Product Owner exibiram conjuntos distintos.
- Quickin: fallback HTML possuía metacaracteres de regex escapados duas vezes;
  o teste reproduzia perda da localização visível no HTML.
- Neon: `jh_history` tinha variações de grafia/capitalização dos estados; a
  UI contava apenas `Candidatado` e `Descartado` exatamente como escritos.
- O backend descartava toda a nota local no `restore_persisted_scores` quando
  não encontrava nota persistida de IA; a nota local não é nota de IA e é
  preservada apenas quando possui score numérico validado.

## Contratos de regressão

- `tests/test_eligibility_enrichment_gate9.py`: dados antecipados, ausência
  de inferência por atualização, limite de chamadas, país multirregional,
  cargo explícito e data epoch.
- `tests/test_public_remote_feeds.py`: duas pesquisas, países como strings,
  deduplicação e localização não comprovada.
- `tests/test_quickin_html_fallback.py`: preservação da cidade/modalidade.
- `tests/test_publication_period.py`: data desconhecida sob janela de 7 dias
  continua pendente, nunca confirmada e nunca pontuada por IA automaticamente.
- `tests/test_opportunity_ui_contracts.py`: confirmações e pendências têm
  rótulos distintos; não se pode esconder silenciosamente as últimas.

Limites: amostra estratificada por provedores, não estimativa da população
inteira. Dados de 20 detalhes inHire não demonstram 20 vagas elegíveis;
nenhum desses anúncios venceu todos os filtros estritos da amostra.

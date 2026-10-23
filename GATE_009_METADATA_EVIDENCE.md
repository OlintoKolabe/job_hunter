# Gate 9 — recuperação de metadados (23/10/2026)

## Escopo congelado

Somente enriquecer evidência estruturada de elegibilidade antes dos filtros já existentes,
expor contagens de entrada/saída na UI e testar a preservação de critérios, histórico,
notas e geração ATS. Sem novas fontes, dependências, serviços, banco ou chamadas de IA.

Arquivos de código permitidos nesta entrega: `eligibility_enrichment.py`, `app.py`,
`src/Opportunities.jsx`, `tests/test_metadata_recovery_gate9.py` e `Dockerfile`
(somente para incluir a nova suíte no gate de build).
Este documento contém a auditoria da mesma alteração.

## Evidências primárias (consultas públicas reais; somente leitura)

1. **120 quadros consecutivos do catálogo**, com 8.205 anúncios de três origens:
   Greenhouse 7.838, Ashby 225, Greenhouse EU 142. Para Brasil/remoto/7 dias,
   apenas três anúncios Greenhouse foram confirmados na amostra. A maior
   exclusão Greenhouse foi por cargo (6.660); 780 por país, 298 por data e
   36 por modalidade. Faltavam JDs em 2.911 anúncios Greenhouse, mas apenas
   quatro anúncios não tinham data. Não há evidência para relaxar o filtro.
2. **Amostra estratificada de até dez quadros por fonte**, 72 quadros e 1.767
   anúncios. Greenhouse: 614 anúncios (519 excluídos por cargo); Ashby:
   309 (261 por cargo); Greenhouse EU: 142 (120 por cargo); inHire:
   168 (168 sem JD e sem data no retorno de listagem, 157 excluídos por cargo);
   Lever: 526 (458 excluídos por cargo, um sem JD); BambooHR: oito.
   Dez quadros Quickin não entregaram vagas parseáveis; falhas 404 ou
   fallback JS desativado foram registradas, sem alegar zero vagas existentes.
3. **inHire real**, empresa Radix: 111 vagas na lista; o endpoint público de
   duas vagas mostrou os campos `lastPublishedAt`, `description`,
   `workplaceType` e `location`. O código de produção só transferia os dois
   primeiros e, portanto, desperdiçava evidência real de modalidade/localização.
4. **Medição antes/depois em Radix** com limite de 16 detalhes:
   17 candidatas ao detalhe, 16 consultas bem-sucedidas, uma adiada;
   111/111 sem data antes e 95/111 sem data depois. Para Brasil/remoto/7 dias,
   uma vaga passou a ser confirmada, de zero para uma; nenhuma elegível foi
   perdida. Outros títulos tiveram publicação antiga ou modalidade híbrida.

Esses números descrevem as amostras consultadas, não a totalidade das vagas
do mercado e nem a totalidade de resultados após o histórico do usuário.

## Intervenção limitada

- Reutilizar exclusivamente o endpoint público de detalhes já integrado para
  inHire; conservar data, JD e agora os campos estruturados de local/modalidade.
- Preservar o teto existente de 16 chamadas por lote e falhar fechado.
- Medir elegíveis antes/depois sobre a mesma lista, por fonte e por lote;
  nenhuma data inferida a partir de `updatedAt` e nenhum país/remoto presumido.
- Mostrar no Caçador uma auditoria visível com fontes e perdas de metadados.
- Manter escore, ATS, histórico, filtros e outras fontes intactos.

## Critérios de aceite

- As seis regressões de metadados passam com remoção de falsos positivos.
- Suítes preexistentes, build da UI e testes do Docker passam.
- O Render canário fica **live** num commit exclusivo de homologação, sem
  alterar a `main`, o Neon ou o serviço de produção.
- A homologação humana usa vagas reais e compara os números na aba
  "Qualidade dos metadados — antes e depois".

## Limites transparentes

A baixa cobertura de Quickin e os grandes volumes excluídos por cargo são
problemas distintos. Alterar esses conectores ou ampliar sinônimos de cargos
sem nova evidência e aprovação extrapolaria o escopo desta correção.

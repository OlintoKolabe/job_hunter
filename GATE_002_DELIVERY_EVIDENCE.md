# GATE 002 — ENTREGA COMPROVADA, SEM TRANSFERÊNCIA DE BLOQUEIOS
Versão: 1.0 · 2026-10-18 · Job Hunter

## Regra
Uma tarefa de desenvolvimento só pode ser apresentada como **entregue** quando seu resultado final tiver sido produzido pelo fluxo real do produto, inspecionado e confrontado com critérios de aceite. Commit, PR, build e teste unitário não substituem homologação técnica do artefato.

## Obrigação de recuperação
Ao encontrar erro técnico, o executor deve diagnosticar a causa e tentar recuperação e rotas alternativas autorizadas antes de encerrar. Não repassar ao usuário atividades de diagnóstico, geração repetitiva de amostras, inspeção de logs ou testes que possam ser executados com as ferramentas disponíveis. A recuperação deve respeitar permissões e limites de segurança; nunca contornar bloqueios de autorização ou pedir acesso a segredos em texto aberto.

## Ciclo obrigatório para currículos
1. Ler um conjunto fixo e diverso de Job Descriptions e sua versão persistida, com origem rastreável.
2. Invocar o mesmo motor de geração usado no fluxo do Caçador, com controle de custo, cache e modo registrado.
3. Gerar o DOCX, reabrir o arquivo e conferir conteúdo, cronologia, evidências e estrutura.
4. Comparar cada saída com seu JD: requisitos centrais cobertos, evidência concreta, afirmações não demonstradas, duplicidades e perdas contra a versão anterior.
5. Registrar pontuação explicável por critério, defeitos, causa no produto e resultado antes/depois.
6. Corrigir a causa dentro do escopo aprovado e repetir **a matriz completa**, não apenas o exemplo que falhou.
7. Reprovar qualquer resultado que dependa de afirmações fabricadas ou que regrida em critérios críticos.

## Evidências mínimas
Publicar a matriz JD × versão × modo × arquivo × notas por critério × resultado, com hashes do JD e DOCX e testes executados. Não inventar notas nem declarar execução sem documentos gerados e lidos.

## Estados
- EM DESENVOLVIMENTO: código alterado, mas fluxo final não validado.
- BLOQUEADO: toda recuperação permitida falhou; registrar evidência técnica e manter não homologado. Não mascarar o estado como entrega.
- HOMOLOGAÇÃO TÉCNICA APROVADA: todos os critérios técnicos comprovados em artefatos reais.
- HOMOLOGAÇÃO DO USUÁRIO: decisão exclusiva do proprietário após entrega tecnicamente aprovada.

## Restrições inegociáveis
- Não fazer merge na main sem autorização expressa.
- Não executar GitHub Actions ou Vercel.
- Não mudar escopo, ranking de vagas, candidaturas ou infraestrutura como efeito colateral.
- Não alterar a segurança nem burlar restrições de acesso.
- Gate é cumulativo com GATE_001; não altera nem revoga aquele contrato.

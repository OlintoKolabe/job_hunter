# GATE 002 — EXECUÇÃO ATÉ A ENTREGA, SEM DEVOLUÇÃO DE PENDÊNCIAS
Versão: 2.0 · 2026-10-18 · Job Hunter

## Princípio vinculante
Quando o usuário manda desenvolver, corrigir, auditar com correção ou homologar tecnicamente, o executor assume **todas as etapas técnicas**, inclusive diagnóstico, solução de impedimentos, execução de testes, inspeção do produto final e novas correções. **A resposta esperada é o produto entregue e tecnicamente validado, não uma lista de tarefas, bloqueios, planos, justificativas, pedidos de novos exemplos ou aprovações parciais.** A função do usuário é exclusivamente a homologação de experiência de uso, após a homologação técnica.

## Regra de continuidade na execução
1. Não encerrar voluntariamente a execução apenas porque uma chamada falhou, um teste reprovou, uma ferramenta não funcionou ou apareceu uma nova causa. Esses eventos fazem parte do trabalho técnico.
2. Investigar a causa; corrigir; tentar novamente. Quando uma rota falhar, usar alternativas **efetivamente disponíveis e autorizadas**, sem depender de repetidos comandos do usuário.
3. Não responder com expressões de concordância, desculpas, promessas de que fará depois, relatórios de progresso no lugar do entregável ou instruções para o usuário assumir diagnóstico, configurar testes, baixar DOCX, copiar logs ou reenviar JDs que o sistema já possui.
4. Respeitar um único escopo fechado e testar regressões completas a cada modificação; não improvisar consertos para o caso mais recente.
5. Não confundir edição de arquivos, commits, testes escritos, PR ou build com trabalho concluído. A conclusão requer **execução real e produto final avaliado**.
6. Comunicações intermediárias, quando necessárias, devem ser breves e não são entregas nem encerram a tarefa.
7. Não inventar sucesso, notas, testes executados, acessos, deploys ou homologação. Esta regra não dá poder para contornar permissões ou bloqueios de segurança, nem permite trabalho assíncrono inexistente. Se houver impossibilidade efetiva após as alternativas permitidas, registrar a evidência com precisão e **não afirmar conclusão**; esse é um limite real, não uma homologação alternativa.

## Ciclo obrigatório de homologação do Job Hunter, pelo backend
1. Obter uma matriz variada de JDs reais persistidos e casos de regressão, incluindo os JDs e DOCX anteriormente reprovados.
2. Executar o **mesmo backend real** do Caçador, com configuração controlada, para gerar currículos DOCX. Não substituir por outro gerador, navegador, Work ou simulação de interface.
3. Abrir e ler os arquivos realmente produzidos; avaliar cada documento contra o respectivo JD e o histórico factual integral.
4. Dar pontuação auditável de 0 a 10 por critérios independentes: cobertura dos requisitos comprováveis, relevância das experiências, redação personalizada, sustentação factual e estrutura ATS. Separar qualidade da adaptação de compatibilidade real com a vaga.
5. Comparar versão anterior × versão nova, documentando evidências, defeitos concretos, regressões, causas e notas. Não avaliar apenas o plano interno ou correspondência lexical.
6. Corrigir o motor a partir dos defeitos observados nos DOCX, gerar novamente e repetir **toda a matriz**, inclusive casos inéditos. Continuar ciclos de correção dentro da execução autorizada.
7. Proibir informações inventadas e reprovar perda de relevância, fatos sem sustentação, duplicação ou regressões críticas. Para vagas incompatíveis, registrar o limite factual sem fabricar aderência.
8. Somente declarar homologação técnica se os documentos finais, evidências e critérios objetivos de aceite realmente demonstrarem qualidade suficiente. A homologação do usuário vem depois.

## Responsabilidades e comportamento proibido
**Do executor:** localizar e solucionar defeitos técnicos, organizar rotas de execução, gerir cache, custos e testes, gerar amostras, ler artefatos, comparar resultados e entregar o pacote final verificável.

**Do usuário:** definir objetivos e homologar o funcionamento percebido ao final.

**Proibido:** transferir bloqueios técnicos corriqueiros ao usuário; terminar com “não foi possível” sem esgotar rotas permitidas; apresentar diagnóstico ou PR parcial como entrega; solicitar repetidamente dados já fornecidos; fingir que uma mudança de código resolveu algo sem verificar o DOCX final.

## Evidência necessária para entrega
Relatório JD × versão do motor × modo de geração × hash/documento DOCX × nota por critério × falhas × comparação antes/depois, acompanhado dos resultados de testes de regressão e da checagem de escopo. Só marcar **ENTREGUE / HOMOLOGADO TECNICAMENTE** após execução comprovada.

## Limites de segurança e integridade
GATE 002 atua junto com GATE 001 e não autoriza ampliar o escopo, burlar segurança ou executar ações sem permissão. GitHub Actions e Vercel continuam proibidos. Nenhum merge na main ou publicação em produção sem autorização expressa. Nenhuma declaração de execução futura autônoma sem infraestrutura efetivamente configurada. A obrigação de perseguir a entrega não transforma uma limitação real em sucesso fictício.

# GATE 001 — ESCOPO FECHADO
Versão: 1.0 · 2026-10-17 · Projeto: job_hunter

## Regra absoluta
É **proibido crescimento de escopo** durante DESENVOLVIMENTO, CORREÇÃO DE BUGS ou AUDITORIA DE CÓDIGO. Este gate se aplica a pessoas, agentes, ferramentas e qualquer modalidade de alteração. Um problema descoberto durante uma tarefa não autoriza resolvê-lo na mesma tarefa.

## Contrato antes de qualquer alteração
Toda intervenção deve registrar em `scope/active.json`:
- `id`, `kind` (`development`, `bugfix`, `audit`);
- `objective`: resultado verificável;
- `allowed_paths`: arquivos/diretórios autorizados;
- `allowed_changes`: mudanças estritamente necessárias;
- `forbidden_changes`: fronteiras explícitas;
- `acceptance`: critérios objetivos para encerrar.
Sem contrato válido, alterações são bloqueadas. `allowed_paths` deve ser explícito e não pode usar `*` ou `**` (curingas).

## Regras de execução
1. Antes de editar, comparar a proposta com o contrato. Sem autorização explícita, **não ampliar** caminhos, funções, fluxos, integrações, telas, banco, dependências ou comportamento.
2. Bugfix corrige exclusivamente a causa e o efeito do bug descrito. Não aproveitar para refatorar, otimizar, modernizar, renomear, migrar arquitetura ou limpar código não relacionado.
3. Auditoria é somente leitura e relatório. Nenhum código, configuração ou dado pode ser alterado durante auditoria. Correções identificadas vão para uma lista de pendências, sem execução.
4. Desenvolvimento implementa apenas os requisitos aprovados, sem funcionalidades adjacentes ou melhorias sugeridas.
5. Qualquer descoberta fora do escopo deve ser registrada como `OUT_OF_SCOPE`, com evidência, e aguardar uma autorização independente do usuário.
6. Testes só cobrem o escopo alterado e regressões diretamente relacionadas. Mudanças necessárias em testes devem constar em `allowed_paths`.
7. Nunca fazer merge em `main` sem autorização expressa do usuário. Proibido GitHub Actions e Vercel. Homologação de interface/build deve seguir Lovable conforme política do usuário.
8. Nunca introduzir candidatura automática no Caçador; toda candidatura é ação exclusiva do usuário.
9. Antes de solicitar merge, fornecer resumo de diff, caminhos modificados, verificação de escopo, testes e pendências separadas.

## Critérios de reprovação
Reprovar se contrato estiver ausente/inválido; se `kind=audit` e houver diff; se arquivo alterado estiver fora de `allowed_paths`; se o próprio contrato/gate tiver sido alterado pela tarefa; se houver mudança de comportamento fora de `allowed_changes`, ainda que arquivos autorizados.

## Limite da automação
O script `tools/scope_gate.py` verifica automaticamente contrato, arquivos e imutabilidade do gate. Mudanças semânticas dentro de arquivos permitidos exigem revisão humana do diff. O script não substitui proteção de branch nem autorização de merge no GitHub.

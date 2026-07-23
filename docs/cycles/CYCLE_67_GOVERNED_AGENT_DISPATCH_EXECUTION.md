# Ciclo 67 - Execucao governada de despachos de agentes

## Objetivo

Consumir a fila duravel criada no ciclo 66 sem permitir que um agendamento execute uma
ferramenta apenas por existir. Cada despacho passa por isolamento de empresa, versao fixa,
permissoes do responsavel, orcamento, schema de argumentos, autonomia, politica de aprovacao,
modo sombra ou canario e trilha operacional antes de qualquer efeito real.

## Garantias

- configuracoes existentes e novas iniciam em modo sombra;
- modo `live` com canario zero continua em sombra;
- a selecao canaria e deterministica e auditavel;
- ferramentas ausentes, desativadas ou sem permissao falham fechadas;
- argumentos sao validados antes da execucao;
- politicas de negacao prevalecem sobre autonomia;
- acoes supervisionadas e de alto risco aguardam aprovacao humana;
- nenhuma credencial ou argumento bruto e gravado na trilha operacional;
- despachos interrompidos nao sao repetidos automaticamente;
- cada execucao fica ligada a um `AgentRun` e a passos resumidos;
- a decisao humana atualiza ferramenta, execucao e despacho vinculados.

## Estados

`ready -> processing -> simulated | awaiting_approval | completed | failed`

`blocked` continua reservado para falhas de prontidao detectadas antes da fila.

## Proximo passo

Adicionar controles visuais completos de modo sombra, percentual canario, argumentos por
ferramenta, reprocessamento manual seguro e reconciliacao de execucoes interrompidas.

## Validacao final do ciclo

- ferramentas internas nao sensiveis podem entrar na fila sem credencial externa artificial;
- ferramentas sensiveis continuam exigindo um vinculo de credencial ativo e pertencente a mesma empresa;
- teste ponta a ponta cria duas empresas sinteticas e comprova agenda, despacho, politica, orcamento, modo sombra, `AgentRun`, trace, auditoria, evento e isolamento multiempresa;
- a simulacao registra somente fingerprints e nao cria uma falsa execucao externa;
- `207` testes da API passaram;
- `20` testes de integracao com PostgreSQL e Redis passaram;
- `6` testes do worker passaram;
- `7` cenarios E2E passaram e `2` cenarios condicionais foram ignorados;
- a auditoria de seguranca nao encontrou segredos nem vulnerabilidades conhecidas nas dependencias de producao.

# Ciclo 73 — Calendário, ausências e passagem de plantão

## Objetivo

Manter as revisões críticas de agentes sob responsabilidade humana mesmo quando
o plantonista principal estiver fora da escala ou temporariamente indisponível.

## Entrega

- dias da semana versionados na política de SLA;
- janela diária interpretada no fuso configurado;
- ausências temporárias com início, fim, motivo e cancelamento auditado;
- passagem de plantão entre aprovadores ativos da mesma empresa;
- aceite ou rejeição permitido somente ao substituto indicado;
- solicitação idempotente por chave exclusiva da empresa;
- substituição considerada pelo roteador apenas depois do aceite;
- expiração automática de solicitações vencidas;
- remoção de ausentes antes da atribuição;
- deduplicação da escala efetiva;
- rotação automática após vencimento da confirmação;
- formulários e histórico responsivos na central administrativa.

## Segurança

Todas as operações exigem `agents.view` ou `agents.configure`, filtram
`company_id`, `agent_id` e `policy_id` e retornam `404` para recursos de outra
empresa. Origem, substituto e ausente devem ser aprovadores ativos do mesmo
tenant. Eventos e auditoria guardam apenas identificadores e estados
operacionais; credenciais, argumentos de ferramentas e resultados não são
registrados.

## Persistência

A migração `20260722_0088` adiciona os dias de plantão e cria as tabelas de
exceções e passagens. As janelas possuem restrições de integridade no banco e a
reversão remove somente os artefatos deste ciclo.

## Evidências

- 208 testes da API aprovados;
- 7 testes do worker aprovados;
- 20 testes de integração aprovados;
- 19 testes da interface aprovados;
- 7 jornadas E2E aprovadas e 2 cenários condicionais ignorados;
- lint Python e TypeScript aprovado;
- tipagem de 223 arquivos produtivos e tipagem da interface aprovadas;
- build de produção aprovado;
- auditoria de segredos e dependências aprovada;
- contratos CI/CD e de desenvolvimento remoto aprovados;
- downgrade e upgrade da migração aprovados, terminando no head `0088`;
- worker restaurado e saudável após a suíte de integração.

Os testes de integração usam o mesmo PostgreSQL local do worker. Para impedir
que o consumidor altere delegações sintéticas durante a asserção, o worker foi
pausado apenas durante essa suíte e restaurado imediatamente depois. A tipagem
opcional incluindo arquivos de teste ainda aponta 20 anotações legadas em quatro
arquivos; o gate produtivo permaneceu verde e essa dívida não foi ocultada.

## Continuidade

O próximo recorte adicionará múltiplos turnos semanais e calendários de feriados,
com validação de sobreposição e cobertura mínima antes da publicação.

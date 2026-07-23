# Ciclo 72 — Plantão e atribuição das revisões de agentes

## Objetivo

Garantir que uma revisão de execução interrompida tenha um responsável humano
identificável, com plantão versionado, confirmação de recebimento, substituição
segura e histórico consultável.

## Entrega

- plantonistas ordenados dentro da política versionada de SLA;
- fuso IANA e janela diária de atuação validados;
- somente aprovadores ativos da mesma empresa podem integrar o plantão;
- atribuição automática no primeiro alerta de SLA;
- confirmação restrita ao responsável atual;
- confirmação idempotente;
- reatribuição manual protegida por `agents.configure`;
- rotação automática ao próximo plantonista quando a confirmação vence;
- fallback para aprovadores da empresa quando o plantão está fora da janela;
- histórico encadeado por `previous_assignment_id`;
- uma única atribuição ativa por revisão;
- auditoria, eventos e notificações sem argumentos, prompts ou credenciais;
- painel responsivo para configurar escala, confirmar e reatribuir.

## Segurança

Toda consulta filtra `company_id` e `agent_id`. O backend responde `404` antes
de revelar recursos de outro tenant e rejeita como `422` usuários que não sejam
aprovadores ativos da empresa. A interface não substitui essas verificações.

## Persistência

A migração `20260722_0087` amplia as políticas e cria
`agent_dispatch_review_assignments`. A migração foi validada em downgrade e
upgrade, terminando no head `0087`.

## Evidências

- API: 208 testes aprovados;
- worker: 7 testes aprovados;
- integração: 20 testes aprovados;
- interface: 19 testes aprovados;
- E2E: 7 aprovados e 2 condicionais ignorados;
- build, lint, tipagem, contratos, health checks e auditoria de segurança
  aprovados.

## Continuidade

O próximo recorte adicionará calendário semanal, exceções de ausência e
passagem de plantão com aceite do substituto, preservando o histórico versionado.

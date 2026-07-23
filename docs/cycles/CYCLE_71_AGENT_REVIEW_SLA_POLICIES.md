# Ciclo 71 — Políticas versionadas de SLA das revisões de agentes

## Objetivo

Permitir que cada empresa configure, publique e substitua o prazo de revisão de
execuções interrompidas por agente, sem compartilhar configuração entre tenants.

## Entrega

- política versionada com estados `draft`, `published` e `retired`;
- somente uma versão publicada por empresa e agente;
- limites de 5 a 10.080 minutos para aviso e até 20.160 para escalonamento;
- escalonamento obrigatoriamente posterior ao aviso inicial;
- configuração protegida por `agents.configure`;
- leitura protegida por `agents.view`;
- worker usando a política publicada e padrão seguro `30/120` quando ausente;
- alerta de aviso e alerta crítico de escalonamento, ambos idempotentes;
- interface administrativa responsiva;
- auditoria de criação e publicação;
- teste de publicação, uso real, repetição idempotente e isolamento multiempresa.

## Segurança

Os alertas contêm somente identificadores operacionais e tempos. Argumentos de
ferramentas, resultados, credenciais, prompts e segredos não são persistidos nas
políticas, eventos ou notificações.

## Continuidade

O próximo recorte é adicionar destinatários e escalas de plantão versionados às
políticas, com confirmação de recebimento e reatribuição auditada.

## Evidências de validação

- API: 208 testes aprovados;
- worker: 7 testes aprovados;
- integração: 20 testes aprovados;
- interface: 19 testes aprovados;
- E2E: 7 aprovados e 2 condicionais ignorados;
- build, tipagem, lint, contratos, health checks e auditoria de segurança
  aprovados;
- migração `0086` validada nos sentidos de atualização e reversão.

# Ciclo 70 - SLA e alertas de revisao de agentes

## Objetivo

Dar visibilidade operacional a execucoes interrompidas que aguardam decisao,
sem expor argumentos, prompts, resultados, credenciais ou dados de clientes.

## Entrega

- resumo por empresa e agente com pendencias, atrasos, encerramentos,
  repeticoes aprovadas, reincidencias e tempo medio de decisao;
- SLA padrao de 30 minutos, aceitando consulta entre 5 e 10080 minutos;
- job Celery executado a cada cinco minutos;
- notificacao para responsaveis autorizados quando uma revisao vence;
- evento `agent.dispatch.review_sla_breached` usado como marcador idempotente;
- painel visual com destaque para itens fora do prazo;
- atualizacao automatica do painel a cada 30 segundos.

## Privacidade e seguranca

- todas as consultas filtram `company_id` e `agent_id`;
- outro tenant recebe 404;
- notificacoes carregam apenas identificadores, atraso e SLA;
- argumentos de ferramentas, resultados e credenciais nao entram em metricas
  ou alertas;
- o job usa bloqueio `skip_locked`;
- a repeticao do job nao duplica eventos nem notificacoes.

## Metricas

- `pending`;
- `overdue`;
- `closed`;
- `approved`;
- `repeat_interruptions`;
- `average_decision_minutes`;
- `oldest_pending_minutes`;
- `retry_rate_percent`.

## Validacao

- revisao envelhecida artificialmente em PostgreSQL;
- primeiro job cria alerta;
- segundo job nao cria duplicata;
- resumo identifica item vencido;
- isolamento entre empresas;
- tarefa Celery delega ao servico de dominio;
- lint, tipos e testes de interface.

## Proximo passo

Adicionar politica configuravel de SLA e escalonamento por empresa, agente e
nivel de risco, com limites seguros e trilha de alteracao.

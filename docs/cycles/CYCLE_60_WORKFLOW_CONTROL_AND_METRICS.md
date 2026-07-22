# Ciclo 60 - Controle e metricas de automacoes

## Objetivo

Permitir cancelamento honesto, compensacao supervisionada e acompanhamento de confiabilidade sem ocultar as limitacoes do motor externo.

## Entregue

- solicitacao cooperativa de cancelamento isolada por empresa;
- cancelamento imediato para execucoes em fila ou aguardando aprovacao;
- verificacao da solicitacao antes e depois da chamada ao motor externo;
- motivo, solicitante e datas de cancelamento auditaveis;
- politica canonica de compensacao manual para falha ou cancelamento;
- pendencia de compensacao reconhecivel por usuario autorizado;
- metricas de sucesso, falha, cancelamento, latencia, eventos e replay;
- painel responsivo no Estudio de Automacoes;
- migracao reversivel `20260722_0079`.

## Limite conhecido

Uma execucao ja entregue ao n8n pode concluir efeitos antes de observar o pedido de cancelamento. A interface informa que se trata de cancelamento cooperativo. Interrupcao remota imediata depende de um contrato assincrono futuro com identificador externo disponivel durante a execucao.

## Seguranca

- toda operacao filtra `company_id`, `workflow_id` e `execution_id`;
- execucoes finalizadas nao podem ser canceladas novamente;
- compensacao automatica permanece proibida;
- reconhecimento da compensacao exige permissao de execucao;
- auditoria nao armazena payload, credencial ou motivo textual.

## Proximo passo exato

Adicionar politicas de retry por bloco, circuit breaker do provider e cancelamento remoto quando o adaptador disponibilizar um identificador de execucao antecipado.

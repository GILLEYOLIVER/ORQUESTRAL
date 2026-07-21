# ADR - Transactional outbox para eventos de dominio

Data: 21 de julho de 2026.

Status: aceito para implementacao incremental.

## Contexto

O Orkestral precisa disparar automacoes, integracoes, analytics e agentes depois de mudancas empresariais. Publicar diretamente em Redis ou outro broker antes do commit pode anunciar uma operacao que foi revertida. Publicar depois do commit sem persistencia pode perder o evento quando o processo falha.

## Decisao

Persistir o evento em `outbox_events` na mesma transacao do dado/auditoria. Um dispatcher Celery reivindica lotes com `FOR UPDATE SKIP LOCKED`, publica envelopes validados em um Redis Stream interno e marca o resultado.

Consumidores registram `event_id` e `consumer_name` em `event_consumptions`. A constraint unica torna o consumo idempotente mesmo quando a entrega e repetida.

## Contrato

- Evento possui ID, tipo, versao, empresa, ator, correlacao, classificacao, data e payload.
- Payload maximo inicial de 32 KiB.
- Chaves com indicios de senha, token, sessao, cookie, segredo ou credencial sao rejeitadas.
- Falhas persistem somente codigo seguro da excecao.
- Oito tentativas sao permitidas antes de `dead_letter`.
- Backoff cresce ate cinco minutos.
- Locks abandonados podem ser retomados apos timeout.
- Redis Stream e o transporte inicial, nao o contrato do dominio.

## Primeiro produtor

Eventos de autorizacao ja persistidos sao espelhados para o outbox por listener SQLAlchemy `after_insert`. O insert usa a mesma conexao e transacao. Detalhes livres da auditoria nao sao copiados; somente identificadores de auditoria, tipo e alvo entram no payload.

## Consequencias positivas

- Commit e criacao do evento sao atomicos.
- Falha do transporte nao perde o evento.
- Multiplos workers podem reivindicar lotes sem processar a mesma linha simultaneamente.
- Consumidores podem se proteger de duplicidade.
- O broker pode ser substituido.

## Consequencias e limites

- Publicacao externa e marcacao no banco nao formam uma unica transacao; entrega pode repetir.
- Consumidores sao obrigatoriamente idempotentes.
- Redis Stream nao e o arquivo historico; PostgreSQL mantem o ledger operacional.
- Agendamento periodico do task precisa ser configurado por ambiente.
- Painel de DLQ e replay sera adicionado em recorte posterior.

## Alternativas descartadas

- Publicar direto na rota: risco de perda/divergencia e acoplamento.
- Usar formato n8n como evento: aprisionamento ao provedor.
- Introduzir Kafka agora: custo operacional prematuro.
- Armazenar payload completo de auditoria: risco desnecessario de dado sensivel.

## Validacao

- Teste de schema rejeita chaves sensiveis e payload excessivo.
- Teste de integracao prova insert atomico a partir da auditoria.
- Dispatcher publica e marca o evento.
- Ledger de consumo aceita a primeira vez e rejeita duplicata.

# Ciclo 83 - CDC de clientes e checkpoints governados

## Objetivo

Este ciclo cria a primeira camada de Change Data Capture do modelo unificado de
clientes. O mecanismo permite que consumidores autorizados acompanhem mudanças
sem receber o payload bruto que originou a alteração.

## Contrato de segurança

- toda linha possui `company_id` e política PostgreSQL RLS;
- a sequência é monotônica e independente por empresa;
- o evento registra somente operação, campos afetados e impressões SHA-256;
- nomes, e-mails, telefones e identificadores externos não são retornados;
- checkpoints somente avançam e são registrados em histórico imutável;
- assinaturas podem ser pausadas sem perda do checkpoint;
- a API exige permissões reais no backend;
- o perfil somente leitura consulta, mas não cria, pausa, retoma ou reconhece;
- respostas nunca incluem tokens, credenciais ou payloads de origem.

## Fluxo

1. A ingestão consolida um registro no perfil 360.
2. O serviço calcula uma impressão digital determinística do registro.
3. Se a mesma origem, perfil e impressão já foram vistos, nada é duplicado.
4. Uma sequência é reservada atomicamente para a empresa.
5. O evento de metadados é armazenado.
6. Um consumidor autorizado lê eventos posteriores ao seu checkpoint.
7. O consumidor reconhece uma sequência processada.
8. O reconhecimento é recusado se retroceder ou ultrapassar o último evento.

## Endpoints

- `GET /crm/customer-data/cdc/summary`
- `GET /crm/customer-data/cdc/events`
- `GET /crm/customer-data/cdc/subscriptions`
- `POST /crm/customer-data/cdc/subscriptions`
- `GET /crm/customer-data/cdc/subscriptions/{id}/events`
- `POST /crm/customer-data/cdc/subscriptions/{id}/acknowledge`
- `POST /crm/customer-data/cdc/subscriptions/{id}/pause`
- `POST /crm/customer-data/cdc/subscriptions/{id}/resume`

## Limite consciente

A retenção desejada é registrada por assinatura neste ciclo. A remoção
automática segura, condicionada ao menor checkpoint ativo, pertence ao próximo
recorte da plataforma de dados para impedir descarte prematuro.


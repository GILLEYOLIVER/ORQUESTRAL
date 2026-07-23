# Ciclo 94 - Entrada omnichannel governada

## Objetivo

Transformar mensagens externas de e-mail, chat, WhatsApp, formulário e portal em
chamados reais, sem expor credenciais e sem permitir mistura de empresas.

## Entrega

- cadastro administrativo de pontos de entrada por canal;
- segredo HMAC exibido apenas na criação ou rotação;
- segredo cifrado no PostgreSQL com AES-GCM e dados associados ao tenant;
- assinatura vinculada ao timestamp e ao corpo exato da mensagem;
- janela antirreplay de cinco minutos;
- `Idempotency-Key` obrigatória para impedir chamados duplicados;
- limite por origem no Redis e limite de tamanho do payload;
- exigência opcional de consentimento;
- criação real de chamado com fila e prioridade configuradas;
- auditoria e evento de domínio sem conteúdo, remetente ou segredo;
- remetente, IP e chave idempotente persistidos somente como HMAC irreversível;
- duas tabelas com Row-Level Security habilitado e forçado;
- painel responsivo para criação, pausa, ativação e rotação dos canais.

## Contrato de chamada

`POST /api/support/ingress/{company_id}/{public_key}`

Cabeçalhos:

- `Content-Type: application/json`
- `Idempotency-Key: identificador-unico-do-provedor`
- `X-Orkestral-Timestamp: epoch-em-segundos`
- `X-Orkestral-Signature: sha256=<hmac>`

A assinatura usa:

```text
HMAC-SHA256(segredo, timestamp + "." + corpo-json-exato)
```

Payload:

```json
{
  "subject": "Dúvida sobre entrega",
  "message": "Meu pedido ainda não chegou.",
  "sender_reference": "cliente@example.com",
  "language_code": "pt-br",
  "consent_granted": true
}
```

## Segurança

O `company_id` na URL não concede acesso. Ele é usado antes da consulta apenas
para aplicar o contexto RLS da transação. A entrada ainda exige uma chave pública
imprevisível, canal ativo, assinatura válida e não expirada e chave idempotente.

As respostas de listagem nunca possuem `encrypted_secret` ou `webhook_secret`.
O segredo em claro existe somente na resposta de criação/rotação e no estado
volátil do componente React.

## Próximo ciclo

Implementar SLAs avançados, escalonamento automático e calendário de atendimento.

# Fase 13 - Notificações e aprovações

## Decisões

- Todas as notificações e aprovações pertencem a uma empresa por `company_id`.
- Notificações internas são o canal padrão; e-mail e WhatsApp exigem preferência explícita do usuário.
- Canais externos usam webhooks reais configurados por ambiente e nunca recebem segredos do sistema.
- A entrega externa é assíncrona, possui até três tentativas e registra o resultado em `delivery_status`.
- O worker processa entregas e lembretes a cada minuto.
- Aprovações mantêm um histórico imutável de ações em `approval_actions`.
- Payloads de workflows pausados são criptografados com o cofre existente e não aparecem na API.

## Pausa de automações

Quando uma definição contém `action.human_approval`, a execução entra em `waiting` antes de chamar o n8n. Uma solicitação é criada para usuários autorizados. Ao aprovar, o payload é descriptografado e a mesma execução continua; ao rejeitar ou expirar, a execução termina como `canceled`.

## Canais

| Canal    | Padrão     | Requisito                                                       |
| -------- | ---------- | --------------------------------------------------------------- |
| Interno  | Ativo      | Sessão autenticada                                              |
| E-mail   | Desativado | Preferência do usuário e `NOTIFICATION_EMAIL_WEBHOOK_URL`       |
| WhatsApp | Desativado | Preferência, destinatário e `NOTIFICATION_WHATSAPP_WEBHOOK_URL` |

Os webhooks recebem identificadores, destinatário, tipo do evento, título, mensagem e metadados não secretos.

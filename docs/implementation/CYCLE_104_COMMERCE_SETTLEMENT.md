# Ciclo 104 - Liquidacao comercial governada

## Entregas

1. Intencoes de pagamento idempotentes por adaptadores `manual` e `sandbox`.
2. Webhooks assinados por HMAC, com deduplicacao e armazenamento somente do hash.
3. Devolucoes com limite por item, recomposicao atomica de estoque e credito.
4. Comissoes calculadas, aprovadas e vinculadas a contas a pagar.

## Garantias

- Numeros de cartao, CVV, tokens de provedor e segredos nao sao aceitos.
- Operacoes externas permanecem pendentes ate confirmacao assinada.
- As seis novas tabelas possuem `company_id`, RLS habilitado e RLS forcado.
- Idempotencia, bloqueio transacional, auditoria e eventos cobrem pontos criticos.
- Devolucoes nao podem exceder a quantidade vendida.
- Beneficiarios de comissao precisam ser membros ativos da empresa.

## Configuracao

Os segredos existem somente no backend:

```text
PAYMENT_WEBHOOK_SECRET_MANUAL=<segredo>
PAYMENT_WEBHOOK_SECRET_SANDBOX=<segredo>
```

O header esperado e `X-Orkestral-Signature: sha256=<hmac>`.

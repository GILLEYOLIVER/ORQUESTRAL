# Contratos operacionais

## `GET /health`

Confirma apenas que o processo HTTP está respondendo. Não consulta dependências.

```json
{
  "status": "ok",
  "service": "Orkestral API",
  "version": "0.4.0",
  "request_id": "9adba59d-bcd1-40d5-bf23-ec10888dc1c0"
}
```

## `GET /ready`

Verifica configuração, PostgreSQL e Redis. Retorna `200` com `ready` ou `503` com `not_ready`. Cada check expõe somente `status` e `latency_ms`.

## Erros

Erros usam `application/problem+json` com `type`, `title`, `status`, `detail`, `instance` e `request_id`. O cabeçalho `X-Request-ID` sempre corresponde ao campo do corpo.

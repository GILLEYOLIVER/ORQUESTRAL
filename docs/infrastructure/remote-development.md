# Ambiente remoto gratuito de desenvolvimento

## Arquitetura escolhida

O ambiente usa um Web Service gratuito no Render, um PostgreSQL gratuito no Neon e um Redis gratuito no Upstash. O frontend compilado e a API executam no mesmo container e domínio. Isso reduz consumo, elimina CORS entre frontend e API e preserva cookies `HttpOnly` e `Secure`.

Redis permanece obrigatório porque autenticação, sessão, limitação de tentativas e rate limiting dependem dele. n8n, worker Celery, armazenamento de objetos e entrega externa de e-mail ficam desativados no modo reduzido.

## Alternativas avaliadas

| Opção            | Adequação                                                                                                      | Decisão                                 |
| ---------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Render Free      | GitHub, TLS, logs, 750 horas/mês por workspace, sem cobrança ao esgotar cota quando não há método de pagamento | Escolhida                               |
| Koyeb Free       | 512 MB e escala a zero, mas exige cartão e limita serviços gratuitos                                           | Rejeitada por risco financeiro maior    |
| Cloudflare Pages | Excelente frontend estático, mas criaria domínio separado e complexidade de cookies/CORS                       | Alternativa futura                      |
| Railway          | Crédito gratuito pequeno e avaliação temporária                                                                | Rejeitada para disponibilidade contínua |

## Provisionamento

1. Crie um projeto gratuito no Neon sem método de pagamento e copie a URL PostgreSQL com TLS.
2. Crie um banco Redis gratuito no Upstash e copie a URL `rediss://`.
3. No Render, crie um Blueprint a partir de `render.yaml` e confirme que o plano indicado é `Free`.
4. Preencha apenas os segredos solicitados. Gere senha administrativa exclusiva e forte.
5. Não cadastre cartão e não faça upgrade automático.
6. Após o primeiro deploy, confirme `/ready`, `/system/version`, `/system/capabilities` e `/login`.
7. Configure o deploy hook como segredo GitHub `RENDER_DEPLOY_HOOK` e a URL como variável `REMOTE_DEVELOPMENT_URL` no environment `development`.

## Controles

- `REMOTE_DEVELOPMENT_ENABLED=true` ativa validações adicionais e `X-Robots-Tag: noindex`.
- O botão local de administrador não aparece remotamente.
- O banner deixa claro que os dados são de teste.
- Automação e conhecimento são removidos da navegação enquanto n8n e storage estiverem desligados.
- O filesystem do Render é efêmero; dados persistentes pertencem ao Neon.

Fontes oficiais consultadas em 19/07/2026: [Render Free](https://render.com/docs/free), [Render compute](https://render.com/docs/compute-plans), [Neon pricing](https://neon.com/pricing), [Upstash Redis pricing](https://upstash.com/pricing/redis), [Koyeb instances](https://www.koyeb.com/docs/reference/instances), [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) e [Railway plans](https://docs.railway.com/pricing/plans).

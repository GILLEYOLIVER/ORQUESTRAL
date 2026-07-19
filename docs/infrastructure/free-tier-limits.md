# Limites gratuitos e prevenção de custos

## Render

- 750 horas mensais gratuitas por workspace para Web Services.
- 512 MB RAM e 0,1 CPU no plano gratuito.
- Suspensão após 15 minutos sem tráfego e cold start aproximado de um minuto.
- Filesystem efêmero.
- Sem método de pagamento, recursos são suspensos quando a cota incluída termina em vez de gerar cobrança.

## Neon

- Plano sem cartão e sem limite de tempo.
- Limites publicados atualmente: 0,5 GB por projeto e 100 CU-hours mensais por projeto.
- Scale-to-zero após inatividade.

## Upstash

- Redis gratuito com 256 MB, 500 mil comandos/mês e 50 GB de banda exibidos no painel em 19/07/2026.

## Estado implantado em 19/07/2026

| Provedor | Recurso                 | Plano confirmado                | Cobrança obrigatória |
| -------- | ----------------------- | ------------------------------- | -------------------- |
| Render   | `orkestral-development` | Free, 512 MB e 0,1 CPU          | Não                  |
| Neon     | `orkestral-development` | Free, 0,5 GB e scale-to-zero    | Não                  |
| Upstash  | `orkestral-development` | Free, custo exibido de US$ 0,00 | Não                  |

Nenhum método de pagamento, upgrade automático ou recurso pago foi ativado. Se a camada gratuita terminar, o ambiente deve ser desligado em vez de aceitar cobrança.

## Política Orkestral

- Não cadastrar cartão no workspace de desenvolvimento.
- Não habilitar upgrade automático.
- Verificar mensalmente uso no dashboard dos três provedores.
- Apagar recursos de teste abandonados.
- Se qualquer provedor alterar seu plano gratuito, interromper o ambiente antes de aceitar cobrança.
- Este ambiente não tem SLA e não atende produção.

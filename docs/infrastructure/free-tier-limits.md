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

- Redis gratuito com 256 MB, 500 mil comandos/mês e 10 GB de banda no plano publicado.

## Política Orkestral

- Não cadastrar cartão no workspace de desenvolvimento.
- Não habilitar upgrade automático.
- Verificar mensalmente uso no dashboard dos três provedores.
- Apagar recursos de teste abandonados.
- Se qualquer provedor alterar seu plano gratuito, interromper o ambiente antes de aceitar cobrança.
- Este ambiente não tem SLA e não atende produção.

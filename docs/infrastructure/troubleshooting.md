# Troubleshooting remoto

## A primeira abertura demora

O Render gratuito suspende o serviço após inatividade. Aguarde até um minuto; a interface usa timeout maior e exibe uma mensagem de inicialização.

## `/ready` retorna 503

Consulte os checks sanitizados e os logs do Render. Valide `DATABASE_URL` e `REDIS_URL`; não publique seus valores em issues ou logs.

## Login falha

Confirme que o seed foi executado e que e-mail/senha correspondem aos segredos do Render. O botão `Acessar como administrador` é intencionalmente exclusivo do ambiente local.

## Automação ou conhecimento não aparecem

Comportamento esperado no modo reduzido. `N8N_ENABLED=false` e `OBJECT_STORAGE_ENABLED=false` removem esses itens. Use o Compose local para testar esses módulos.

## Deploy não conclui

Confira CI, `RENDER_DEPLOY_HOOK`, `REMOTE_DEVELOPMENT_URL` e o SHA em `/system/version`. O workflow falha se o commit publicado não for exatamente o esperado.

## Banco atingiu limite

Exporte os dados, remova massa de teste desnecessária e crie um banco gratuito novo somente se os termos atuais permitirem. Não faça upgrade pago automaticamente.

# Sistema de plugins

A Fase 5 estabelece a fronteira oficial entre o núcleo Orkestral e serviços externos.

## Componentes

- `packages/plugin-sdk`: contrato público, manifesto tipado, runtime e descoberta por entry points.
- `apps/api/app/modules/plugins`: catálogo, ativação por empresa, cofre e adaptadores oficiais.
- `plugins`: metadados e manifesto de cada integração.
- `company_plugins`: ativação e configuração isoladas por tenant.
- `integration_credentials`: credenciais integralmente criptografadas.
- `plugin_connection_tests`: histórico de tentativas, resultado e duração sem segredos.

## Plugins oficiais iniciais

| Código                | Finalidade                              | Autenticação          |
| --------------------- | --------------------------------------- | --------------------- |
| `generic_webhook`     | Receber e enviar eventos HTTP assinados | Segredo opcional      |
| `smtp_email`          | Enviar mensagens por SMTP               | Usuário e senha       |
| `imap_email`          | Ler caixas de e-mail                    | Usuário e senha/token |
| `google_calendar`     | Consultar e manter agendas              | OAuth 2.0             |
| `whatsapp_business`   | Mensagens pelo provedor oficial         | OAuth 2.0             |
| `external_postgresql` | Acessar PostgreSQL externo              | String de conexão     |
| `rest_api`            | Consumir APIs HTTP genéricas            | API key opcional      |

## Cofre e rotação

`ENCRYPTION_KEY` aceita uma lista separada por vírgulas. A primeira chave sempre cifra novos dados e as demais servem apenas para abrir registros antigos.

1. Configure `ENCRYPTION_KEY=nova-chave,chave-anterior` e reinicie a API.
2. Execute `POST /plugins/credentials/rotate` como usuário com `plugins.manage`.
3. Confirme que `failed` é zero.
4. Remova a chave anterior e reinicie novamente.

As credenciais só são descriptografadas durante teste ou uso. A interface recebe apenas nomes de campos mascarados. Criação, teste, revogação, ativação e rotação geram auditoria administrativa.

## Rotas

- `GET /plugins`
- `PATCH /plugins/{plugin_code}`
- `GET|POST /plugins/{plugin_code}/credentials`
- `DELETE /plugins/{plugin_code}/credentials/{credential_id}`
- `POST /plugins/{plugin_code}/credentials/{credential_id}/test`
- `GET /plugins/{plugin_code}/tests`
- `POST /plugins/credentials/rotate`

Falhas inesperadas e timeouts são isolados pelo runtime do SDK e não interrompem o núcleo. Para adicionar um plugin externo, implemente `BasePlugin` e publique o entry point `orkestral.plugins`.

# API do CRM

Todas as rotas exigem o módulo `crm` ativo na empresa selecionada. O `company_id` nunca é aceito do cliente.

| Método   | Rota                         | Permissão exigida     |
| -------- | ---------------------------- | --------------------- |
| `GET`    | `/crm/contacts`              | `crm.contacts.view`   |
| `POST`   | `/crm/contacts`              | `crm.contacts.create` |
| `GET`    | `/crm/contacts/{contact_id}` | `crm.contacts.view`   |
| `PATCH`  | `/crm/contacts/{contact_id}` | `crm.contacts.update` |
| `DELETE` | `/crm/contacts/{contact_id}` | `crm.contacts.delete` |
| `GET`    | `/crm/tags`                  | `crm.contacts.view`   |
| `POST`   | `/crm/tags`                  | `crm.contacts.update` |
| `DELETE` | `/crm/tags/{tag_id}`         | `crm.contacts.update` |

`GET /crm/contacts` suporta `page`, `page_size`, `search`, `status`, `source`, `assigned_user_id`, `tag_id`, `sort_by` e `sort_order`. Exclusões são lógicas e deixam de aparecer em consultas e detalhes.

Criação, alteração e exclusão produzem eventos de auditoria contendo ator, empresa, ação, alvo e nomes dos campos alterados. Dados pessoais, tokens e credenciais não são copiados para a auditoria.

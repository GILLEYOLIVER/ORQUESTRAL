# API de autorização

Todas as rotas exigem um access token válido e uma empresa ativa selecionada. A API deriva a empresa e as permissões da sessão; o cliente não envia `company_id`.

| Método   | Rota                             | Permissão exigida |
| -------- | -------------------------------- | ----------------- |
| `GET`    | `/authorization/permissions`     | `roles.view`      |
| `GET`    | `/authorization/roles`           | `roles.view`      |
| `POST`   | `/authorization/roles`           | `roles.create`    |
| `PATCH`  | `/authorization/roles/{role_id}` | `roles.update`    |
| `DELETE` | `/authorization/roles/{role_id}` | `roles.delete`    |
| `GET`    | `/authorization/audit-events`    | `roles.view`      |
| `GET`    | `/company/users`                 | `users.view`      |
| `POST`   | `/company/invitations`           | `users.create`    |
| `PATCH`  | `/company/users/{user_id}`       | `users.update`    |

Papéis de sistema são imutáveis. Um papel personalizado só pode ser excluído quando não possui usuários vinculados. Códigos inexistentes e permissões globais da plataforma são rejeitados em papéis de empresa.

Alterações são registradas em `authorization_audit_events`, incluindo ator, ação, alvo, campos alterados e data. Corpos de requisição, senhas, tokens e cookies nunca são gravados nessa trilha.

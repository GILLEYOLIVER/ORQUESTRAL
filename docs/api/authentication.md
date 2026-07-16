# Autenticação e tenancy

Todas as respostas propagam `X-Request-ID`; erros usam `ProblemDetails`. O gateway local publica as rotas abaixo com o prefixo `/api`.

| Método | Rota                      | Uso                                                    |
| ------ | ------------------------- | ------------------------------------------------------ |
| `POST` | `/auth/login`             | Valida e-mail/senha e cria sessão revogável            |
| `POST` | `/auth/refresh`           | Rotaciona o refresh token e emite novo access token    |
| `POST` | `/auth/logout`            | Revoga a sessão e remove o cookie                      |
| `GET`  | `/auth/me`                | Retorna usuário, empresas, empresa atual e capacidades |
| `POST` | `/auth/select-company`    | Seleciona somente uma empresa com vínculo ativo        |
| `POST` | `/auth/forgot-password`   | Inicia recuperação sem revelar se o e-mail existe      |
| `POST` | `/auth/reset-password`    | Consome token de uso único e revoga sessões existentes |
| `POST` | `/auth/accept-invitation` | Ativa usuário e vínculo usando convite de uso único    |

Administradores da plataforma usam `GET/POST/PATCH /companies`. Proprietários usam `GET /company/users`, `POST /company/invitations` e `PATCH /company/users/{user_id}`; o `company_id` dessas operações é sempre extraído do contexto autenticado.

## Controles

- senhas armazenadas com Argon2id e política mínima de complexidade;
- access token JWT com validade padrão de 15 minutos e vínculo à sessão;
- refresh token opaco de 30 dias, guardado como HMAC, rotacionado a cada uso;
- cookie HttpOnly, `SameSite=Strict` e `Secure` fora do desenvolvimento;
- limite de tentativas de login por e-mail e endereço IP no Redis;
- tentativas e motivos sanitizados registrados no PostgreSQL;
- tokens de convite e recuperação aparecem na resposta somente no modo de desenvolvimento explicitamente habilitado.

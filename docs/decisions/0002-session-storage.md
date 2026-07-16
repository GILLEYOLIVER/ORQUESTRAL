# ADR 0002 — Armazenamento de sessão

**Status:** aceito

Tokens de acesso JWT de curta duração ficam somente em memória. Tokens de renovação são valores opacos, armazenados no banco apenas como HMAC e enviados em cookies `HttpOnly` e `SameSite=Strict`. O atributo `Secure` é obrigatório em staging e produção.

Cada renovação rotaciona o token opaco. Logout, redefinição de senha e invalidações de segurança revogam sessões no servidor. O access token identifica usuário, sessão e empresa selecionada; a API confirma todos esses vínculos no banco antes de aceitar a requisição.

Não usar `localStorage` ou `sessionStorage` para tokens. Ao recarregar a página, o front-end recupera um novo access token usando apenas o cookie HttpOnly.

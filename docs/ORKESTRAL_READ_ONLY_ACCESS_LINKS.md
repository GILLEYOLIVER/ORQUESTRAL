# Links seguros de acesso somente leitura

## Objetivo

Permitir que um administrador gere um acesso temporário para sócios ou revisores consultarem a empresa sem poder alterar nenhum dado.

## Fluxo

1. Na tela de login, o administrador seleciona **Gerar link de acesso**.
2. O servidor valida novamente e limita tentativas das credenciais administrativas.
3. Uma autorização aleatória de cinco minutos permite escolher apenas usuários das empresas administradas.
4. O administrador escolhe usuário e expiração entre uma hora e trinta dias.
5. O servidor salva somente o hash HMAC do token e registra `read_only_access_link.created`.
6. O segredo é colocado no fragmento `#token=` da URL, que não é enviado em logs HTTP ou cabeçalhos de referência.
7. Ao abrir o link, a interface remove imediatamente o fragmento e troca o token por uma sessão `read_only`.
8. O uso registra `read_only_access_link.used`, a empresa fica fixa e a sessão nunca ultrapassa a expiração do link.

## Garantias de segurança

- O token bruto não é persistido.
- A autorização de geração é curta, de uso único e armazenada no Redis.
- Usuários de outras empresas não aparecem e não podem ser selecionados.
- O JWT e a sessão carregam `access_mode=read_only` e devem coincidir.
- `POST`, `PUT`, `PATCH` e `DELETE` com esse JWT retornam `403` no middleware antes da rota.
- Somente o logout é permitido como operação mutável para encerrar a própria sessão.
- O perfil recebe todas as permissões empresariais para manter a interface administrativa, mas nunca permissões globais de plataforma.
- Criação, uso e tentativas HTTP bloqueadas permanecem auditáveis.

## Operação

- Expiração máxima padrão: 30 dias, configurável por `READ_ONLY_LINK_MAX_DAYS`.
- Autorização administrativa padrão: 5 minutos, configurável por `READ_ONLY_LINK_AUTHORIZATION_MINUTES`.
- A exclusão da empresa remove os links e sessões relacionadas por regras de integridade, evitando rastros após o encerramento do tenant.

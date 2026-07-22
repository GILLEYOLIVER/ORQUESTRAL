# Ciclo 62 - Protecao de acesso e variaveis de ambiente

Data: 22/07/2026

## Objetivo

Reduzir ataques de forca bruta, credential stuffing, abuso de recuperacao de senha, falsificacao de IP por proxy e inicializacao remota com configuracao insegura.

## Controles implementados

- limite geral distribuido por Redis;
- limite mais severo e compartilhado para rotas de autenticacao;
- contadores independentes por conta e IP no login administrativo;
- limite silencioso por conta e IP na recuperacao de senha;
- chaves de rate limit protegidas por HMAC, sem e-mail ou IP em texto claro;
- falha fechada das rotas sensiveis quando Redis estiver indisponivel;
- `Retry-After` e cabecalhos `RateLimit-*` nas respostas `429`;
- IP encaminhado aceito somente de proxy explicitamente confiavel;
- Nginx sobrescreve `X-Forwarded-For`, limita rajadas e conexoes e oculta sua versao;
- ambientes remotos recusam rate limit, HSTS, origem ou validacao JSON desativados;
- ambientes remotos recusam segredos reutilizados, placeholders e keyrings duplicados;
- contratos de ambiente documentam todos os limites;
- scanner de segredos cobre arquivos `.env`, chaves privadas e formatos comuns de tokens.

## Parametros padrao

| Controle | Limite | Janela |
| --- | ---: | ---: |
| API por identidade | 300 | 60 segundos |
| Rotas sensiveis por IP | 20 | 15 minutos |
| Falhas de login por conta | 5 | 15 minutos |
| Falhas de login por IP | 20 | 15 minutos |
| Recuperacoes por conta | 3 | 15 minutos |
| Recuperacoes por IP | 10 | 15 minutos |

Os valores podem ser reduzidos por ambiente. A validacao impede combinacoes em que o limite externo seja menos restritivo do que os limites internos dependentes.

## Limites e riscos restantes

Rate limit nao torna um sistema invulneravel. MFA, WAF/CDN, alertas de anomalia, rotacao operacional de segredos, revisao de permissoes do provedor e resposta a incidentes continuam necessarios antes de producao com clientes reais.

## Referencias

- OWASP Authentication Cheat Sheet;
- OWASP Forgot Password Cheat Sheet;
- OWASP HTTP Security Response Headers Cheat Sheet;
- OWASP Secrets Management Cheat Sheet.

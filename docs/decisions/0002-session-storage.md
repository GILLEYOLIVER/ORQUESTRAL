# ADR 0002 — Armazenamento de sessão

**Status:** aceito

Tokens de acesso futuros ficam somente em memória. Tokens de renovação serão cookies `HttpOnly`, `Secure` e `SameSite` emitidos pelo servidor.

Não usar `localStorage` ou `sessionStorage` para tokens. A Fase 1 contém apenas a abstração em memória e não cria sessão simulada.

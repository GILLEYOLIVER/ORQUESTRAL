# ADR 0003 — Isolamento dos serviços

**Status:** aceito

Somente o gateway Nginx publica portas no perfil base. PostgreSQL, Redis, n8n e armazenamento permanecem em redes internas com o menor conjunto de participantes necessário.

O override de desenvolvimento pode publicar ferramentas administrativas exclusivamente no loopback local.

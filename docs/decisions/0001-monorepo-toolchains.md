# ADR 0001 — Monorepo e toolchains

**Status:** aceito

Usar pnpm workspaces para TypeScript e uv workspaces para Python. Lockfiles são versionados e CI/containers usam as mesmas resoluções.

Isso mantém contratos e componentes próximos das aplicações consumidoras sem misturar toolchains ou criar um framework de build adicional nesta fase.

# ADR 0005 — Contexto multiempresa derivado da sessão

**Status:** aceito

Operações pertencentes a uma empresa não aceitam `company_id` fornecido livremente pelo cliente. O contexto é montado a partir do access token, da sessão ativa, da empresa selecionada e do vínculo ativo em `company_users`.

O contexto expõe `user_id`, `company_id`, `role_ids`, permissões mínimas e indicadores de proprietário/administrador da plataforma. Toda consulta de tenant deve usar esse `company_id`. A estrutura de `role_ids` já existe, porém o contrato configurável de papéis e permissões será criado somente na Fase 3.

Essa decisão evita autorização baseada apenas em dados controlados pelo navegador e permite que o mesmo usuário participe de várias empresas sem misturar dados.

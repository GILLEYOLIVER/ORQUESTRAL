# Núcleo modular

`modules_catalog` descreve capacidades conhecidas e `company_modules` registra ativação e configuração por empresa. Um item no banco não basta para disponibilizar código: o `ModuleRegistry` carrega somente manifests importados pela aplicação e rejeita códigos duplicados.

Cada manifest declara código, nome, versão, permissões, routers FastAPI, menus, esquema de configuração, eventos publicados/consumidos e migrações. Na Fase 4, apenas `crm` está instalado; os demais itens do catálogo têm estado `planned`.

Rotas de módulos usam duas dependências independentes:

1. `require_permission(...)` valida o papel do vínculo atual;
2. `require_active_module(...)` confirma que o módulo está instalado e ativo para a mesma empresa.

A interface consulta `GET /modules` para montar menus, mas essa ocultação é apenas experiência de uso. A API continua sendo a autoridade de acesso.

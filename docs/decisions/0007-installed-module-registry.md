# ADR 0007 — Catálogo no banco e registro instalado no código

## Decisão

Separar o catálogo persistido do registro de módulos instalados. Um módulo só pode ser ativado quando seu código existe em ambos e o manifest foi carregado pelo processo da API.

## Motivos

- impedir que uma alteração isolada no banco exponha rotas inexistentes;
- manter contrato explícito para permissões, menus, eventos e migrações;
- permitir planejamento de módulos sem apresentá-los como funcionais;
- combinar ativação por tenant com autorização granular.

## Consequências

Adicionar um módulo exige manifest e migração de catálogo. Remover um manifest bloqueia novas ativações, mesmo que o registro histórico permaneça no banco.

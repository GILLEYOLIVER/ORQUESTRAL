# ADR 0006 — RBAC com autoridade no servidor

## Decisão

Usar papéis por empresa associados a um catálogo global de permissões com códigos estáveis. Toda rota protegida declara a permissão exigida por meio de uma dependência FastAPI reutilizável. A interface usa os mesmos códigos apenas para navegação e feedback.

## Motivos

- impedir que manipulação do navegador conceda acesso;
- manter o isolamento multiempresa no vínculo autenticado;
- permitir papéis personalizados sem alterar código;
- produzir uma trilha auditável de mudanças de autorização.

## Consequências

As permissões são consultadas no PostgreSQL a cada requisição autenticada, portanto alterações entram em vigor imediatamente, inclusive para access tokens já emitidos. Um cache poderá ser introduzido futuramente, desde que tenha invalidação explícita e preserve essa propriedade.

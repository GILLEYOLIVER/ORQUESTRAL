# ADR 0008 — Banco compartilhado com tenant por coluna

**Status:** aceito

## Decisão

A fase atual usa um único banco e schema compartilhados. Toda entidade pertencente a cliente carrega `company_id`, obtido da sessão conforme ADR 0005, e toda consulta de tenant deve filtrar essa coluna.

## Motivo

Esta opção reduz custo operacional, simplifica migrações e permite validar o produto com rapidez. A decisão é consciente: schema por tenant e banco por tenant aumentariam isolamento, mas também multiplicariam provisionamento, migrações, observabilidade e recuperação.

## Controles obrigatórios

- `company_id` nunca é aceito livremente do navegador;
- chaves e índices compostos devem incluir o tenant quando houver risco de colisão;
- testes de integração devem tentar acesso cruzado por ID;
- jobs, buscas vetoriais, auditoria e exportações mantêm o filtro de tenant;
- RLS no PostgreSQL é aplicado por papéis transacionais conforme o ADR 0010,
  mantendo os filtros da aplicação como primeira barreira.

## Evolução

Clientes com exigência regulatória ou volume excepcional poderão migrar para schema ou banco dedicado atrás da mesma camada de repositório. O gatilho para essa mudança será definido por requisitos contratuais, residência de dados, desempenho ou recuperação independente, não por preferência implícita.

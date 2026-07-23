# Ciclo 81 - Adaptadores, scheduler e health de sincronizacao

## Entrega

- catalogo tipado e versionado de adaptadores;
- capacidades explicitas por transporte;
- prontidao fail-closed;
- health baseado no teste da credencial cifrada;
- fila de despachos sem carga de cliente;
- agenda idempotente por conector e janela;
- worker periodico com limite por lote;
- contexto RLS ativado para uma empresa por vez;
- funcao `SECURITY DEFINER` que revela somente empresas com agenda vencida;
- painel com adaptador e verificacao de prontidao.

## Regra de realidade

O scheduler cria um despacho pendente, mas nao declara que consultou um sistema
externo. A execucao HTTP segura do adaptador REST sera o proximo recorte e
devera incluir protecao SSRF, timeout, limite de resposta, mapeamento tipado e
dead-letter.

## Seguranca

- nenhuma credencial retorna pela API;
- nenhum identificador de worker e persistido em claro;
- a funcao global retorna somente `company_id`;
- consultas de conectores e despachos continuam sob RLS;
- adaptador desconhecido, transporte divergente, credencial ausente ou teste
  falho bloqueiam o despacho.

## Migracao

`20260723_0095` adiciona identidade do adaptador, health, fila de despachos e a
funcao minima de descoberta de empresas com agenda vencida.


## Validacao final executada em 23 de julho de 2026

- 257 testes de API, worker, integracao e seguranca aprovados.
- 19 testes do frontend aprovados e build Vite concluido.
- Ruff aprovado.
- mypy aprovado em 237 arquivos de producao.
- Migracao `20260723_0095` aplicada no PostgreSQL e confirmada no topo do Alembic.
- A funcao `orkestral_due_sync_companies` ficou executavel somente pelo proprietario e por `orkestral_tenant_runtime`.
- Auditoria de segredos, fronteira de variaveis publicas, persistencia de tokens, bundle, identidades do banco, Actions, Bandit e dependencias concluidas sem bloqueios.

# Ciclo 78 - correspondencia, fusao reversivel e linhagem

## Entrega

Este ciclo aprofunda a Fase 5 da plataforma de dados com tres capacidades integradas:

1. regras de correspondencia versionadas, com rascunho, publicacao e arquivamento;
2. fila de possiveis duplicidades com decisao humana, justificativa e reversao;
3. linhagem de campo com fonte, classificacao e fingerprint, sem duplicar o valor sensivel.

## Seguranca

- Todas as tabelas possuem `company_id`, RLS habilitado e RLS forcado.
- A API exige permissao de leitura ou atualizacao do CRM no backend.
- Nenhuma fusao ocorre automaticamente.
- Toda decisao e reversao registra ator, data, justificativa e itens movimentados.
- A linhagem armazena SHA-256 e nunca devolve o valor observado.
- O perfil somente leitura enxerga o painel, mas recebe 403 em mutacoes pelo backend.

## Fluxo operacional

1. O administrador cria uma regra em rascunho.
2. A regra e publicada e substitui a versao anterior sem apagar historico.
3. A analise compara no maximo 500 perfis por execucao e cria apenas sugestoes explicaveis.
4. Uma pessoa aprova ou rejeita cada sugestao.
5. A fusao aprovada registra cada vinculo movimentado.
6. A reversao restaura somente os vinculos pertencentes aquela fusao.

## Criterios de aceitacao

- Regra publicada e unica por empresa.
- Perfis de empresas diferentes nunca sao comparados.
- Decisao repetida e recusada.
- Fusao aprovada pode ser desfeita.
- Valores sensiveis nao sao persistidos na linhagem.
- Contratos OpenAPI incluem todas as rotas.

## Evidencias de validacao

- Backend, worker, integracao e seguranca: 246 testes aprovados com o worker isolado.
- Operacao PostgreSQL: regra publicada, correspondencia detectada, fusao aprovada, linhagem movida, reversao concluida e rollback da sonda confirmado.
- Frontend: 19 testes aprovados e build de producao concluido.
- Qualidade: Ruff e mypy aprovados em 223 arquivos produtivos.
- Banco: downgrade para 20260723_0091 e upgrade para 20260723_0092 validados; 0092 permanece no head.
- Seguranca: RLS, fronteira de segredos, roles PostgreSQL, dependencias e SAST sem bloqueios.
- Contratos: OpenAPI e tipos TypeScript regenerados.

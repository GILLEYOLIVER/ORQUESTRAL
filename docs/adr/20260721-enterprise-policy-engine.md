# ADR - Policy Engine empresarial e contexto de execucao

Data: 21 de julho de 2026.

Status: aceito para adocao incremental.

## Contexto

As permissoes atuais protegem rotas, mas capacidades futuras exigem decisoes por empresa, recurso, campo, risco e ferramenta. Jobs tambem precisam transportar tenant e correlacao sem carregar uma copia potencialmente obsoleta das permissoes.

## Decisao

Criar dois contratos independentes:

- `ExecutionContext`: empresa, ator, correlacao, origem e ambiente para request, job, evento, workflow e agente.
- `PolicyEngine`: avaliacao deterministica de tenant, permissao, campos e risco.

O contexto de job nao transporta permissoes. O worker deve recarregar identidade e politicas quando uma operacao exigir autorizacao atual. Isso evita executar privilegios revogados com snapshots antigos.

Cada avaliacao persistida gera `PolicyDecisionRecord` e o evento `security.policy.evaluated` na mesma transacao.

## Regras iniciais

1. Tenant diferente resulta em negacao, salvo escopo de plataforma explicitamente solicitado e sujeito platform admin.
2. Owner nao ignora permissao exigida.
3. Leitura pode retornar conjunto parcial de campos.
4. Escrita com campo negado bloqueia a operacao inteira.
5. Mutacao de risco alto ou critico exige aprovacao.
6. Negacao cross-tenant nao publica identificador do recurso no evento.
7. Toda decisao possui versao para reproducao futura.

## Consequencias

- Servicos podem explicar por que permitiram, negaram ou pediram aprovacao.
- Field-level security deixa de depender de ocultacao visual.
- Jobs, eventos e agentes compartilham correlacao e tenant.
- A adocao nas rotas sera incremental; o contrato novo nao substitui imediatamente `require_permission`.
- O ledger aumenta volume e exigira retencao/agregacao futura.

## Validacao

- Testes de tenant mismatch, permissao, campo, risco e contexto.
- Integracao prova decisao e evento no mesmo commit.
- Contrato estrutural exige `company_id` no novo ledger.

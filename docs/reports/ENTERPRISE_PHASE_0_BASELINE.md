# Linha de Base Empresarial - Fase 0

Data da analise: 21 de julho de 2026

## Objetivo

Registrar o estado real encontrado antes da evolucao orientada pelo `PROMPT_MESTRE_EVOLUCAO_ORKESTRAL.md`. Este documento distingue recursos existentes, recursos basicos e lacunas empresariais; ele nao atribui equivalencia de mercado sem implementacao e testes.

## Resumo executivo

O Orkestral nao e um prototipo vazio. Ele ja possui uma fundacao SaaS multiempresa funcional, oito modulos de negocio, automacoes canônicas compiladas para n8n, agentes com ferramentas e aprovacao, conhecimento vetorial, plugins com credenciais criptografadas, billing, notificacoes, auditoria e deploy automatizado.

Ao mesmo tempo, ainda nao e uma plataforma empresarial equivalente aos maiores produtos do mercado. As principais lacunas sao estruturais: metadados publicaveis, seguranca por registro/campo, eventos transacionais, runtime versionado de agentes, modelo de cliente 360, marketplace seguro, observabilidade distribuida e cobertura sistematica de isolamento por dominio.

## Arquitetura observada

```text
Nginx
|-- React/Vite
`-- FastAPI
    |-- dominios de negocio
    |-- PostgreSQL + pgvector
    |-- Redis
    |-- MinIO
    |-- n8n por adaptador
    `-- Celery worker/beat
```

### Fronteiras existentes

| Area         | Implementacao observada                                      | Maturidade inicial |
| ------------ | ------------------------------------------------------------ | ------------------ |
| Identidade   | login, sessoes, selecao de empresa, recuperacao e convite    | basico funcional   |
| Autorizacao  | papeis, permissoes e dependencia no back-end                 | basico funcional   |
| Modularidade | catalogo, manifestos, ativacao por empresa                   | basico funcional   |
| CRM          | contatos, etiquetas, pipelines, oportunidades e atividades   | basico funcional   |
| Atendimento  | tickets, interacoes, filas, SLA e satisfacao                 | basico funcional   |
| Projetos     | projetos, tarefas, portfolios, marcos, riscos e dependencias | basico funcional   |
| Marketing    | campanhas, jornadas, metricas, testes e atribuicao           | basico funcional   |
| Estoque      | itens, locais, saldos e movimentos                           | basico funcional   |
| Financeiro   | contas, categorias e lancamentos                             | basico funcional   |
| RH           | departamentos, colaboradores e afastamentos                  | basico funcional   |
| Analytics    | indicadores, metas e medicoes                                | basico funcional   |
| Workflows    | DSL canonica, validacao, versao e compilacao n8n             | basico funcional   |
| Agentes      | provedores, chat, RAG, ferramentas, aprovacao e custo        | basico funcional   |
| Integracoes  | plugins, credenciais, teste e rotacao                        | basico funcional   |
| Billing      | planos, assinatura, limites e uso idempotente                | basico funcional   |
| Auditoria    | eventos de autorizacao e auditoria geral                     | parcial, duplicado |

## Multiempresa e seguranca

### Controles encontrados

- token vinculado a sessao e empresa selecionada;
- membership ativa obrigatoria para usuario comum;
- `RequestContext` com `company_id`, usuario, papel e permissoes;
- filtros por `company_id` nas rotas empresariais analisadas;
- verificacao de modulo ativo por empresa;
- credenciais de plugins vinculadas ao tenant e criptografadas;
- redacao de segredos em logs e auditoria;
- origem, tipo de conteudo, CORS e rate limiting na borda da API;
- verificacao humana para ferramentas sensiveis de agentes.

### Lacunas

- ausencia de RLS como defesa adicional;
- ausencia de politica generica por campo e registro;
- cobertura cross-tenant nao uniforme para todos os dominios;
- dois modelos de auditoria;
- eventos declarados sem garantia transacional;
- politicas de agentes ainda incorporadas parcialmente em ferramentas e rotas;
- classificacao e retencao de dados sem motor central.

## Estado de execucao

Todos os oito containers locais estavam saudaveis. A API respondeu `health=ok`, `ready=ready`, o front-end respondeu HTTP 200 e o Alembic informou `20260720_0027 (head)`.

## Falhas iniciais e resolucao

1. O lint encontrou 11 problemas em mudancas locais; foram corrigidos sem alterar comportamento.
2. O MyPy encontrou quatro acessos nao tipados a `rowcount`; foram substituidos por `RETURNING` explicito.
3. O teste de registro de modulos esperava somente migracoes antigas; o contrato foi atualizado para `0024` a `0027`.
4. Cinco integracoes usaram a porta PostgreSQL errada no primeiro comando local; a execucao foi repetida contra o encaminhamento `15432`, sem revelar a credencial.
5. Os contratos OpenAPI estavam desatualizados; os artefatos versionados foram regenerados.

## Decisao de arquitetura preliminar

Manter o monolito modular. Nao ha evidencia que justifique microsservicos agora. O proximo recorte estrutural deve reduzir risco transversal, e nao adicionar outro modulo isolado.

Prioridade preliminar:

1. testes sistematicos de isolamento e enforcement de permissoes;
2. auditoria unificada;
3. eventos de dominio com transactional outbox;
4. fundacao da plataforma de metadados;
5. politicas e versoes do runtime de agentes.

A prioridade definitiva sera registrada depois da auditoria dos itens 4 a 8 da Ordem Imediata e da pesquisa oficial comparativa.

## Criterio de continuidade

Nenhuma capacidade sera marcada como empresarial apenas por possuir uma tabela ou tela. Cada item exigira dados, migracao, servico, autorizacao, isolamento, auditoria, API, interface quando aplicavel, testes, documentacao e observabilidade conforme a definicao de pronto do Prompt Mestre.

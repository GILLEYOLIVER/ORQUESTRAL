# Ciclo 77 — Identidade canônica e visão 360

## Objetivo

Transformar contatos isolados em perfis empresariais consolidados, rastreáveis
e protegidos, sem duplicar dados sensíveis nem misturar empresas.

## Entrega

- perfil canônico por cliente;
- vários cadastros ligados ao mesmo perfil;
- resolução determinística por e-mail e telefone;
- identidades persistidas por SHA-256 e dica mascarada;
- fonte de dados e modo de obtenção;
- pontuação e pendências de qualidade;
- consentimento histórico por finalidade e canal;
- oportunidades e atividades agregadas;
- API e painel de visão 360;
- auditoria, eventos e RLS desde a criação das tabelas;
- migração reversível `20260723_0091`.

## Continuidade

O próximo recorte adicionará regras versionadas de correspondência, fila de
decisão humana para fusão e desfusão e linhagem por atributo.

## Evidencias de validacao

- Backend, worker, integracao e seguranca: 242 testes aprovados.
- Frontend: 19 testes aprovados e build de producao concluido.
- Qualidade: Ruff e mypy aprovados em 220 arquivos produtivos.
- Banco: downgrade para 20260723_0090 e upgrade para 20260723_0091 validados; 0091 permanece no head.
- Seguranca: auditoria de segredos, fronteira do frontend, roles PostgreSQL, Actions, Node, Bandit e dependencias Python concluida sem bloqueios.
- Contratos: OpenAPI e tipos TypeScript regenerados para os endpoints de visao 360 e consentimentos.

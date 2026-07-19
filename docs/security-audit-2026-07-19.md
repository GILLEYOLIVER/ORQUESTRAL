# Auditoria de seguranca - 2026-07-19

## Escopo

A auditoria do passo 35 cobriu autenticacao, bootstrap, configuracao por ambiente, segredos,
dependencias Python e Node, imagens, workflows e controles operacionais. O ambiente externo nao foi
provisionado e nenhum segredo real foi acessado.

## Evidencias

| Controle                           | Resultado                                                   |
| ---------------------------------- | ----------------------------------------------------------- |
| Segredos versionados               | Nenhum padrao conhecido encontrado                          |
| Dependencias Node de producao      | Nenhuma vulnerabilidade conhecida                           |
| Dependencias Python de producao    | Vulnerabilidades encontradas e versoes corrigidas aplicadas |
| Bandit                             | Nenhum achado medio ou alto                                 |
| Testes de seguranca e multiempresa | Cobertos pela Fase 14 e pelo CI                             |
| Imagens                            | Trivy bloqueante para vulnerabilidades criticas             |
| Configuracao de staging/production | Rejeita placeholders, localhost, CORS inseguro e bootstrap  |

## Achados tratados

### SEC-001 - validacoes removiveis pelo otimizador Python

Severidade baixa. Rotas de acesso local e o bootstrap usavam `assert` depois de validacoes de
configuracao. Os asserts foram substituidos por falhas explicitas e o Ruff passou a proibir `S101`
fora dos testes.

### SEC-002 - auditoria de dependencias e SAST nao centralizada

Severidade media. Os scans existiam de forma parcial na esteira. O workflow `Security audit` agora
executa verificacao de segredos, `pnpm audit`, `pip-audit`, Bandit e Trivy em PRs, `main`, agenda
semanal e execucao manual.

### SEC-003 - referencias mutaveis de GitHub Actions

Severidade media. Actions externas eram referenciadas por tags. Todas foram fixadas por SHA e o
script de auditoria bloqueia novas referencias mutaveis. Dependabot acompanha atualizacoes.

### SEC-004 - dependencias Python vulneraveis

Severidade alta. `cryptography 45.0.7` e `PyJWT 2.10.1` possuiam advisories corrigidos em versoes
posteriores. O lockfile foi atualizado para `cryptography 48.0.1` e `PyJWT 2.13.0`; o `pip-audit`
passou a bloquear recorrencias na esteira.

## Riscos residuais

- Alertas baixos do Bandit em migrations representam literais booleanos de enums, nao senhas.
- O valor vazio de refresh token e um marcador interno antes da rotacao, nao uma credencial.
- A eficacia de backup, alertas, TLS, hooks e rollback depende do provisionamento autorizado de
  staging e production.
- Pentest externo e revisao de conformidade permanecem obrigatorios antes de dados reais.

## Criterio de aceite

O passo 35 esta concluido quando `pnpm security:audit`, CI, testes de seguranca e o workflow Trivy
estiverem verdes. Achados futuros medios, altos ou criticos bloqueiam promocao ate correcao ou aceite
formal de risco.

# Segurança, auditoria e recuperação

## Controles ativos

- Toda operação HTTP mutável gera um `audit_event` sem armazenar o corpo da requisição.
- Campos de senha, token, chave, segredo e credencial são redigidos antes de logs e auditoria.
- Sessões expiram, podem ser listadas e revogadas, e são verificadas no banco a cada acesso.
- Redis limita solicitações por endereço IP e bloqueia tentativas repetidas de login.
- CORS usa origens explícitas; produção aceita somente HTTPS.
- Respostas incluem CSP, proteção contra MIME sniffing, frames, permissões e cache sensível.
- Uploads aceitos pela base de conhecimento passam por limite, MIME, assinatura, conteúdo executável,
  caminhos inseguros e expansão máxima de arquivos compactados.
- Empresas e usuários usam exclusão lógica; eventos de auditoria são imutáveis na API regular.

## Auditoria automatizada

Execute `pnpm security:audit` para verificar segredos versionados, dependências Node e Python,
SAST Python e pinning imutável das GitHub Actions. O workflow `Security audit` repete essas
verificações em pull requests, na `main`, semanalmente e sob demanda, além de executar Trivy no
filesystem. Vulnerabilidades altas ou críticas e achados SAST médios ou altos bloqueiam a entrega.

O Dependabot acompanha npm, Python, Docker e GitHub Actions semanalmente. Atualizações de Actions
devem preservar o SHA completo e registrar a versão legível em comentário.

## Rotação de segredos

1. Gere um segredo aleatório com pelo menos 32 caracteres no gerenciador de segredos autorizado.
2. Troque `JWT_SECRET` pelo valor novo e mantenha o anterior em `JWT_PREVIOUS_SECRETS`.
3. Reinicie a API e aguarde o maior prazo de token de acesso.
4. Remova o segredo anterior e reinicie novamente.
5. Configure a chave nova em `ENCRYPTION_KEY` e mantenha as anteriores temporariamente em
   `ENCRYPTION_PREVIOUS_KEYS`. Novos dados usam somente a chave ativa; memórias, campos e
   relatórios históricos procuram a chave anterior pelo keyring protegido.
6. Execute os exercícios de resposta e verifique relatórios antigos antes de remover uma chave.
7. Para cada agente, inicie um job em `POST /agents/{agent_id}/memory-reencryption-jobs` e
   acompanhe `GET /agents/{agent_id}/memory-reencryption-jobs`. O worker processa lotes com
   checkpoint, isolamento por empresa e bloqueio contra execução duplicada.
8. Aguarde todos os jobs alcançarem `completed`, confirme `failed_count = 0` e execute uma leitura
   controlada sem a chave antiga antes de retirá-la do gerenciador de segredos.
9. Não remova a chave anterior enquanto existir job `pending`, `running` ou `failed`; corrija a
   causa e preserve o keyring para impedir perda definitiva de dados criptografados.
   Jobs falhos podem ser retomados por `POST /agents/{agent_id}/memory-reencryption-jobs/{job_id}/retry`;
   a justificativa é armazenada somente como fingerprint e o processamento continua do checkpoint.
10. Remova chaves anteriores somente depois da recriptografia e da janela de retenção aprovada.
11. Nunca registre valores de segredo em tickets, logs, PRs ou comandos versionados.

## SLO do scheduler de memória

- Cada agenda registra o último heartbeat do worker, o SLO configurado e a quantidade de violações.
- O endpoint de métricas diferencia `waiting`, `healthy`, `overdue` e `disabled`.
- Quando o worker retorna depois de superar o SLO, o responsável recebe alerta crítico e um evento
  interno sem conteúdo de memória.
- Um monitor externo deve consultar as métricas em produção, porque o próprio worker não consegue
  emitir alertas enquanto estiver completamente indisponível.

## Backup

Execute em um host com Docker e acesso exclusivo ao diretório de destino:

```bash
./infrastructure/scripts/backup.sh /caminho/seguro/orkestral-backup
```

O backup inclui todo o cluster PostgreSQL, objetos e dados do n8n, com checksum SHA-256 e
permissões locais restritas. Redis não é preservado porque contém cache e filas recuperáveis.
Criptografe o diretório em repouso e envie-o ao armazenamento externo autorizado.

## Recuperação de desastre

Restaure primeiro em `testing` ou `staging`. A restauração substitui banco e volumes escolhidos,
por isso exige confirmação explícita:

```bash
CONFIRM_RESTORE=YES ./infrastructure/scripts/restore.sh /caminho/seguro/orkestral-backup
```

Depois valide `/health`, `/ready`, autenticação, seleção de empresa, integrações, arquivos e n8n.
Registre data, operador, checksum, duração e resultado do exercício. A meta inicial é backup diário,
RPO de 24 horas e RTO de 4 horas; produção deve ajustar essas metas ao contrato do plano.

## Retenção e exclusão definitiva

Eventos podem ser consultados apenas dentro da empresa com `audit.view`. O expurgo definitivo
exige administrador da plataforma, justificativa e data anterior a `AUDIT_RETENTION_DAYS`; o próprio
expurgo gera um novo evento. Solicitações legais devem ser aprovadas e registradas antes da execução.

## Resposta a incidentes

1. Revogue as sessões afetadas e rotacione os segredos comprometidos.
2. Preserve logs e eventos de auditoria com seus request IDs.
3. Isole integrações e workflows envolvidos sem apagar evidências.
4. Recupere em ambiente separado e compare checksums.
5. Documente causa, alcance, correção e prevenção antes de reabrir o serviço.

# Monitor externo e recuperação assistida da memória

- Monitore `GET /health/agent-memory-scheduler` fora do worker. A resposta é genérica e nunca revela empresa, agente, horários ou quantidade de agendas, mas exige uma assinatura HMAC válida por no máximo cinco minutos.
- Guarde `AGENT_MEMORY_MONITOR_SECRET` e `ORKESTRAL_MONITOR_SECRET` em cofres separados da aplicação e do monitor. Execute `ORKESTRAL_BASE_URL=https://seu-ambiente ORKESTRAL_MONITOR_SECRET=... bash scripts/monitor-agent-memory-worker.sh`; código diferente de zero exige investigação do worker e do Celery Beat.
- Para rotacionar sem indisponibilidade, mova temporariamente o segredo antigo para `AGENT_MEMORY_MONITOR_PREVIOUS_SECRETS`, publique o segredo novo, atualize o monitor e remova o anterior após cinco minutos. Valores repetidos ou inseguros são rejeitados na inicialização.
- Registre a rotação em `AGENT_MEMORY_MONITOR_SECRET_ROTATED_AT`; ambientes remotos recusam inicialização quando a data estiver ausente ou exceder `AGENT_MEMORY_MONITOR_SECRET_MAX_AGE_DAYS`.
- Em produção, configure `ENCRYPTION_KEY_PROVIDER=external`, uma referência exclusiva em `ENCRYPTION_KEY_REFERENCE` e uma referência correspondente para cada item de `ENCRYPTION_PREVIOUS_KEYS`. O banco registra somente a impressão digital da referência, nunca sua URI nem o material da chave.
- Cada job externo exige uma credencial ativa da mesma empresa com o campo `key_reference`. O vínculo fica protegido por HMAC e a API informa apenas sua existência; revogação, expiração ou tentativa de usar credencial de outro tenant bloqueia a operação.
- Cada job de recriptografia recebe um limite imutável de retomadas entre 1 e 10. O banco impede que a contagem ultrapasse esse orçamento.
- Antes de uma retomada, execute o diagnóstico assistido na interface. Ele verifica estado falho, keyring histórico, identificação da chave, snapshot, exclusividade e orçamento sem retornar material secreto.
- Quando a recuperação for impossível ou o orçamento acabar, encerre o job pela interface. Código técnico, autor e horário permanecem auditáveis; a justificativa é preservada somente como HMAC e o job encerrado não pode ser retomado.
- Jobs concluídos, falhos ou encerrados recebem `purge_after` conforme `AGENT_MEMORY_REENCRYPTION_TERMINAL_RETENTION_DAYS`. O worker elimina o registro operacional vencido e mantém somente auditoria e evento agregados, sem ID do job ou material criptográfico.
- Uma retenção legal pendente ou aprovada suspende o expurgo do job. A referência jurídica é protegida por HMAC, a decisão exige outro usuário autorizado e o isolamento por empresa é aplicado em todas as operações.
- Um diagnóstico aprovado expira em 15 minutos. Mudanças no keyring ou em jobs concorrentes bloqueiam a retomada e exigem nova avaliação.
- Nunca cole chaves no motivo, na interface, em logs ou em tickets. Restaure-as exclusivamente no gerenciador de segredos do ambiente.

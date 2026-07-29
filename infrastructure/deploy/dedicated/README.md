# Implantacao empresarial dedicada

Este contrato descreve uma instalação isolada do Orkestral sem acoplamento a
um provedor. Ele complementa o `docker-compose.yml`; não cria infraestrutura
paga nem contém segredos.

## Topologia mínima

- gateway HTTPS e WAF;
- duas ou mais réplicas stateless da API;
- workers separados por fila;
- PostgreSQL gerenciado ou dedicado com backup Point-in-Time;
- Redis com autenticação, TLS e persistência adequada ao uso;
- armazenamento S3 compatível, versionado e cifrado;
- n8n em rede privada;
- cofre de segredos e identidades distintas para migração, API e worker.

## Regras

1. Não publicar PostgreSQL, Redis, n8n ou armazenamento na internet.
2. Executar migrações em job único antes de liberar a nova versão.
3. Usar imagens imutáveis por digest e registrar o commit em `/system/version`.
4. Exigir `DATABASE_ROLE_SEPARATION_REQUIRED=true` e RLS forçada.
5. Manter backups fora da conta ou do cluster principal.
6. Testar restauração em ambiente isolado pelo menos trimestralmente.
7. Definir SLO, RPO e RTO aprovados pelo cliente antes da entrada em produção.
8. Não mover dados reais para sandbox; usar dados sintéticos ou mascarados.

## Promoção

O fluxo é `build -> análise -> backup -> migração -> canário -> health/readiness
-> promoção -> observação`. Falha em qualquer etapa interrompe a promoção. O
rollback da aplicação usa a imagem anterior; rollback de banco só ocorre com
procedimento explícito e backup verificado.

## Segredos obrigatórios

Use o cofre da infraestrutura. Nunca preencha arquivos versionados. No mínimo:

- URLs separadas de migração, API e worker;
- segredo JWT;
- chave de criptografia;
- credenciais Redis e S3;
- credenciais do provedor de identidade;
- chaves de assinatura de webhooks;
- tokens de provedores externos.

Consulte `docs/ORKESTRAL_ENTERPRISE_OPERATIONS.md` para operação e
`docs/ORKESTRAL_DISASTER_RECOVERY.md` para recuperação.

# Gates de entrega do Orkestral

O documento mestre permanece como visão completa. Estes gates evitam tratar a sequência de 15 fases como uma promessa de produção antes das validações necessárias.

## MVP interno

Fundação, autenticação, multiempresa, permissões, CRM básico, plugins essenciais, agentes, conhecimento e workflows suportados. Fluxos com blocos sem adaptador permanecem bloqueados.

## Beta controlado

Testes de isolamento entre empresas, restauração de backup, carga da busca vetorial, compatibilidade n8n e observabilidade sem segredos. Nenhuma simulação local pode operar silenciosamente.

## SaaS comercial

Planos, assinatura, limites transacionais, medição idempotente, notificações, aprovações e suporte operacional. Mudanças de preço e limite exigem histórico e auditoria.

## Produção

CI bloqueante, staging independente, HTTPS, rotação de segredos, restore comprovado, rollback de aplicação e migração, auditoria externa e decisão sobre RLS. Cada gate precisa de evidência automatizada; concluir uma fase de código não promove o ambiente automaticamente.

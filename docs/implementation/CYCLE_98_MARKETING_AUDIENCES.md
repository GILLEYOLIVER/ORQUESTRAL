# Ciclo 98 - Públicos e listas de marketing

## Objetivo

Criar públicos reutilizáveis sem duplicar a segmentação canônica do CRM.

## Entrega

- públicos dinâmicos vinculados a segmentos publicados;
- listas estáticas para curadoria manual;
- sincronização idempotente com bloqueio concorrente;
- exclusão de perfis com restrição ativa;
- consentimento de marketing obrigatório;
- isolamento por `company_id` no serviço e por RLS forçada no PostgreSQL;
- auditoria de criação, sincronização e alteração de membros;
- interface responsiva em português;
- nenhum envio externo executado nesta etapa.

## Segurança

O backend valida empresa, permissão e tipo do público em todas as operações. A
sincronização nunca inclui contatos sem consentimento válido nem perfis com
restrição ativa. As duas tabelas possuem `ENABLE ROW LEVEL SECURITY` e
`FORCE ROW LEVEL SECURITY`.

## Continuidade

Próximo recorte da Fase 8: consentimento por canal, frequência máxima e janelas
de horário permitidas para campanhas e jornadas.

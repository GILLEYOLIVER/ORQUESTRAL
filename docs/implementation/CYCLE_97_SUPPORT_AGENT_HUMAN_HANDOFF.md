# Ciclo 97 - Agente de atendimento e transferência humana

O suporte agora conecta chamados a agentes ativos e versões publicadas. A
decisão é determinística: risco de SLA ou urgência exige humano; contexto ou
fonte ausente exige informação; somente contexto autorizado e citado permite
recomendar resposta.

O contexto preservado contém apenas IDs das últimas interações e contagem de
citações. Mensagens, prompts, chaves e raciocínio interno não são copiados.

A transferência exige destinatário da mesma empresa e decisão humana explícita.
Somente o aceite altera responsável e status do chamado. Todas as decisões
geram evento operacional sem conteúdo sensível.

As tabelas `support_agent_assist_runs` e `support_human_handoffs` usam RLS
forçada e a migração reversível `20260727_0110`.


# Ciclo 100 - Canais, conteúdo, páginas e formulários

## Entregas

1. Conectores de canal guardam somente referências ao cofre de credenciais.
2. Conteúdo possui versões imutáveis, revisão independente e marcação de IA.
3. Landing pages publicam apenas conteúdo aprovado e coletam formulários mínimos
   com consentimento explícito.

O endpoint público resolve o tenant por um registro global mínimo sem dados do
cliente e ativa o contexto RLS antes de consultar ou gravar dados empresariais.
Valores desconhecidos são descartados, tamanho é limitado, o IP vira HMAC e há
limitação horária por origem.

Próximo ciclo: jornadas versionadas, simulação, A/B, atribuição explicável, ROI
e agente de marketing governado.

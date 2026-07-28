# Ciclo 101 - Jornadas governadas, testes e agentes de marketing

Data: 27 de julho de 2026.

## Entrega

- jornadas possuem simulação sem efeitos externos;
- a simulação registra a definição e seu checksum;
- a publicação aceita somente a mesma definição aprovada;
- cada publicação cria uma versão imutável e auditável;
- e-mail, WhatsApp e SMS exigem conteúdo aprovado e compatível com o canal;
- webhooks ficam bloqueados até existir adaptador governado;
- testes A/B podem registrar amostra, métrica, confiança, regra e fonte;
- agentes publicados podem produzir recomendações baseadas em métricas;
- aprovar uma recomendação não executa alterações: a decisão é apenas auditada;
- todas as novas tabelas possuem isolamento multiempresa com RLS forçado.

## Segurança

O runtime não confia em identificadores de conteúdo vindos do fluxo. O conteúdo
é consultado dentro da empresa corrente e precisa estar aprovado. A publicação
é invalidada quando uma etapa muda depois da simulação. Recomendações de IA
mantêm evidências estruturadas e não possuem acesso direto ao banco nem efeitos
financeiros ou de envio.

## Critério de saída da Fase 8

A base de marketing cobre campanhas, públicos, consentimento, frequência,
janelas de contato, canais, conteúdo versionado, páginas, formulários,
experimentos, atribuição, jornadas simuláveis/publicáveis e recomendações
governadas. Entregas reais por provedores continuam desacopladas e serão
habilitadas somente por conectores com credenciais protegidas.

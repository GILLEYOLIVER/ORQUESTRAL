# Ciclo 89 - Fundação empresarial de vendas

## Objetivo

Criar o início auditável do processo comercial sem duplicar os contatos, funis e
oportunidades já existentes no Orkestral.

## Entregas

- contas empresariais separadas por empresa;
- leads com origem, responsável, situação e pontuação determinística;
- qualificação e desqualificação com justificativa;
- conversão idempotente de lead;
- criação ou reutilização de conta durante a conversão;
- criação de contato, perfil 360 e oportunidade no mesmo fluxo;
- trilha de atividade na oportunidade;
- eventos de domínio sem e-mail ou telefone;
- auditoria sem dados pessoais brutos;
- RLS forçada nas novas tabelas;
- permissões específicas para visualizar, gerenciar, qualificar e converter;
- painel responsivo para prospecção e contas;
- bloqueio visual e no backend para acesso somente leitura.

## Contratos

- `GET /crm/sales/accounts`
- `POST /crm/sales/accounts`
- `GET /crm/sales/leads`
- `POST /crm/sales/leads`
- `PATCH /crm/sales/leads/{lead_id}`
- `POST /crm/sales/leads/{lead_id}/qualification`
- `POST /crm/sales/leads/{lead_id}/conversion`

## Segurança

Toda consulta raiz filtra `company_id`. A conversão valida a empresa do lead,
da conta, do funil e da etapa, além de usar trava de linha para impedir duas
conversões concorrentes. Eventos e auditoria usam apenas identificadores,
situação e pontuação; e-mail e telefone não são publicados.

## Continuidade

O próximo recorte da Fase 6 deve aprofundar produtos, tabelas de preços,
propostas e saúde/previsão explicável das oportunidades.

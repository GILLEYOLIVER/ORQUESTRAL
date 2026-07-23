# Ciclo 93 - habilidades, capacidade e roteamento de atendimento

Data: 23 de julho de 2026.

## Objetivo

Iniciar a Fase 7 com uma distribuição de chamados reproduzível, explicável e
protegida por empresa.

## Entrega

- cadastro de habilidades de atendimento;
- disponibilidade, fila principal, idiomas, canais e capacidade por atendente;
- habilidades obrigatórias por fila;
- recomendação determinística por chamado;
- atribuição explícita separada da simulação;
- explicação da pontuação e da carga;
- histórico operacional, auditoria e evento transacional;
- painel responsivo na Central de suporte.

## Regras da recomendação

Um atendente somente participa quando:

1. pertence ativamente à empresa;
2. está disponível ou ocupado;
3. ainda possui capacidade;
4. aceita o canal do chamado;
5. atende o idioma solicitado;
6. possui todas as habilidades obrigatórias.

A classificação considera disponibilidade, aderência à fila, proficiência e
menor carga. Empates são ordenados de forma estável por carga e nome.

## Segurança

- as quatro tabelas novas possuem RLS habilitada e forçada;
- toda consulta e alteração contém filtro explícito por `company_id`;
- recomendação exige leitura e nunca altera o chamado;
- atribuição exige `support.tickets.update`;
- o perfil Administrador Somente Leitura recebe 403 nas rotas de escrita;
- eventos e auditoria armazenam identificadores e metadados, sem descrição do
  chamado, mensagens, credenciais ou dados pessoais;
- habilidades e usuários de outra empresa são rejeitados.

## API

- `GET /support/routing/configuration`
- `POST /support/routing/skills`
- `PUT /support/routing/agents/{user_id}`
- `PUT /support/routing/queues/{queue_id}`
- `POST /support/routing/tickets/{ticket_id}/recommend`
- `POST /support/routing/tickets/{ticket_id}/assign`

## Migração

`20260723_0106`, reversível para `20260723_0105`.

## Próximo passo

Adicionar canais omnichannel governados, incluindo entrada por e-mail, chat,
WhatsApp, formulário e portal, com idempotência, consentimento e rastreamento.

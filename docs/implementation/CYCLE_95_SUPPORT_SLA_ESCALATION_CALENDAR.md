# Ciclo 95 - SLA, calendário e escalonamento de atendimento

## Alinhamento ao Documento Mestre

Este ciclo implementa o critério de saída da Fase 7:

> SLA dispara escalonamento.

## Entrega

- calendários semanais por empresa, com múltiplos turnos, fuso e feriados;
- políticas ligadas ao SLA, calendário e ação de escalonamento;
- aviso antecipado configurável;
- escalonamento por notificação, prioridade, fila ou usuário;
- worker automático executado a cada minuto;
- execução manual para diagnóstico administrativo;
- histórico imutável e idempotente por ticket, política, etapa e prazo;
- notificações, auditoria e eventos de domínio;
- painel responsivo com situação do calendário, riscos e escalonamentos;
- RLS habilitado e forçado nas três novas tabelas.

## Segurança

- toda consulta e escrita exige `company_id`;
- o worker aplica o papel de tenant antes de processar cada empresa;
- alvos de fila e usuário são validados dentro da mesma empresa;
- o frontend não recebe credenciais, tokens ou configurações internas;
- nenhuma mensagem completa do cliente é gravada no evento de escalonamento;
- ações repetidas são bloqueadas por restrição única no PostgreSQL;
- políticas não ampliam permissões do usuário ou do worker.

## Fluxo

1. administrador cria o calendário;
2. administrador vincula calendário e SLA a uma política;
3. worker verifica chamados ativos a cada minuto;
4. fora do horário, a execução aguarda;
5. dentro do horário, o aviso é enviado antes do prazo;
6. no vencimento, a ação configurada é aplicada;
7. notificação, auditoria e evento são registrados;
8. nova tentativa encontra o evento existente e não repete a ação.

## Próximo recorte

Macros, respostas rápidas, conhecimento citado e satisfação aprofundada.

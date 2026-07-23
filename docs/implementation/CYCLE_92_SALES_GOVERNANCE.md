# Ciclo 92 - Metas, territórios e renovações

## Entregas

- territórios comerciais por empresa;
- atribuição de oportunidades a territórios;
- metas anuais de receita, negócios ganhos e novas contas;
- progresso calculado a partir dos dados transacionais;
- planos de renovação vinculados a contas empresariais;
- máquina de estados progressiva para renovação;
- painel de gestão responsivo;
- auditoria e eventos sem conteúdo de notas;
- RLS forçada nas três tabelas novas.

## Segurança e governança

- território, meta, conta, oportunidade e renovação são sempre validados na
  empresa atual;
- responsáveis precisam possuir vínculo ativo com a empresa;
- uma oportunidade de origem de renovação precisa estar ganha e pertencer à
  mesma conta;
- transições retroativas ou fora da sequência são bloqueadas;
- concluir uma renovação não gera cobrança, nota fiscal ou movimentação
  financeira automática;
- o perfil somente leitura vê a gestão, mas não cria nem avança registros.

## Validação concluída

- migração reversível `20260723_0104 -> 20260723_0105 -> 20260723_0104 -> 20260723_0105`;
- `277` testes do backend aprovados;
- `19` testes do frontend e build de produção aprovados;
- Ruff, MyPy e auditoria de segurança aprovados;
- smoke HTTP criou território e meta, atribuiu oportunidade e avançou uma
  renovação de planejada até renovada;
- tentativa de retroceder a renovação foi bloqueada com `409`;
- acesso anônimo ao painel foi bloqueado com `401`;
- RLS ocultou o território em outra empresa e bloqueou escrita cruzada na
  identidade de runtime do PostgreSQL.

## Conclusão da Fase 6

A Fase 6 passa a oferecer fundação de contas e leads, conversão idempotente,
catálogo, preços, propostas, saúde explicável, previsão, territórios, metas e
renovações. Divisão de receita e comissionamento avançado permanecem como
evolução futura integrada à Fase 9 de receita e comércio.

## Próximo passo

Iniciar a Fase 7 com SLA, filas, habilidades, roteamento e atendimento
omnichannel governado.

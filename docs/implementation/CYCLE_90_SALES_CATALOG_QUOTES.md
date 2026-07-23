# Ciclo 90 - Catálogo comercial, preços e propostas

## Entregas

- tabelas de preços com versão, vigência, moeda e publicação;
- preços vinculados aos produtos reais do estoque;
- propostas vinculadas a oportunidades e contas da mesma empresa;
- snapshot de SKU, descrição e preço para preservar o histórico;
- quantidade mínima, desconto percentual e cálculo decimal determinístico;
- ciclo de vida rascunho, publicada, aceita, rejeitada ou vencida;
- auditoria e eventos sem dados pessoais;
- permissões separadas para consulta, gestão e publicação;
- RLS forçada nas quatro novas tabelas.

## Segurança e consistência

Cada consulta valida `company_id`. Produtos precisam pertencer à mesma empresa,
estar ativos e fazer parte da tabela publicada. A proposta não aceita produtos
duplicados, quantidades abaixo do mínimo ou datas vencidas. O aceite registra
atividade na oportunidade, mas não cria cobrança ou movimentação financeira
automaticamente.

## Validação concluída

- migração reversível `20260723_0103 -> 20260723_0104 -> 20260723_0103 -> 20260723_0104`;
- `267` testes do backend aprovados;
- Ruff e MyPy aprovados nos contratos novos;
- `19` testes do frontend e build de produção aprovados;
- auditoria de segredos, dependências, fronteira do navegador e identidade do banco aprovada;
- fluxo HTTP real aprovado: ativação do estoque, produto, tabela, preço, publicação,
  proposta, publicação e aceite;
- cálculo validado: duas unidades a `R$ 1.250,50`, com desconto de `10%`,
  resultaram em `R$ 2.250,90`;
- oito serviços locais iniciados e `/ready` respondeu com PostgreSQL e Redis saudáveis.

## Próximo passo

Adicionar previsão explicável, saúde da oportunidade e recomendações de
próxima ação.

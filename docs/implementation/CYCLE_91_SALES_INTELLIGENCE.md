# Ciclo 91 - Saúde de oportunidades e previsão comercial

## Objetivo

Transformar o funil em uma ferramenta de decisão explicável, sem depender de
um modelo de inteligência artificial e sem executar ações autônomas.

## Entregas

- pontuação de saúde entre zero e cem;
- classificação saudável, atenção ou crítica;
- receita ponderada pela probabilidade;
- categorias de previsão: em desenvolvimento, melhor cenário e comprometida;
- detecção de atividade atrasada e data de fechamento vencida;
- consideração da situação das propostas comerciais;
- recomendação determinística da próxima ação;
- motivos visíveis para cada avaliação;
- painel responsivo em português;
- consultas protegidas por empresa, módulo e permissão.

## Regras de segurança

- todas as junções repetem o filtro `company_id`;
- oportunidades excluídas e fechadas não entram na previsão;
- a resposta não contém contato, e-mail, telefone, credencial ou token;
- o recurso é somente leitura;
- nenhuma previsão altera dados ou dispara cobrança;
- o perfil de sócio somente leitura pode consultar a previsão sem obter
  capacidade de escrita.

## Validação concluída

- `272` testes do backend aprovados;
- `19` testes do frontend e build de produção aprovados;
- Ruff e MyPy aprovados;
- auditoria de segredos, dependências e fronteira do navegador aprovada;
- endpoint sem autenticação bloqueado com `401`;
- smoke HTTP autenticado calculou uma oportunidade real e retornou motivos e
  próxima ação;
- `/ready` confirmou configuração, PostgreSQL e Redis saudáveis.

## Próximo passo

Concluir a Fase 6 com metas, territórios, renovação e visão gerencial antes de
iniciar a Fase 7 de atendimento empresarial.

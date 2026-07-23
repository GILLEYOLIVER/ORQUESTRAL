# Ciclo 86 - Solicitacoes de privacidade e exclusao de dados

## Objetivo

Completar o ciclo de consentimento existente com um processo governado para
anonimizacao e exclusao de dados pessoais.

## Fluxo

1. registrar a solicitacao e armazenar somente o hash do protocolo;
2. verificar a identidade do solicitante;
3. aprovar ou rejeitar com um codigo controlado;
4. aplicar retencao legal quando houver obrigacao;
5. executar somente com `crm.contacts.delete`;
6. registrar contagens, nunca valores removidos.

## Anonimizacao

Mantem um registro empresarial neutro, mas remove nome, e-mail, telefone,
empresa, cargo, origem, responsavel e identificadores originais. Hashes,
lineagem, ingestao e CDC recebem novas impressoes irreversiveis.

## Exclusao

Executa a mesma limpeza e depois remove fisicamente contatos e perfil. Antes
disso, desvincula suporte, oportunidades, atividades e atribuicoes de marketing,
e remove etiquetas e participacoes em campanhas.

## Retencao legal

Uma solicitacao aprovada com `legal_hold=true` nao pode ser executada. A
liberacao exige nova acao autorizada e permanece na trilha de eventos.

## Seguranca

- duas tabelas novas com RLS;
- nenhuma referencia original ou justificativa livre e persistida;
- transicoes de estado estritas;
- lock transacional por solicitacao;
- execucao bloqueada para perfis somente leitura;
- isolamento por `company_id` em todas as operacoes.


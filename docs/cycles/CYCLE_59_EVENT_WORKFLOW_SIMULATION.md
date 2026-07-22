# Ciclo 59 - Gatilhos de evento e simulacao de automacoes

## Objetivo

Conectar contratos de eventos publicados ao formato canonico das automacoes e permitir que o administrador valide o caminho completo antes de produzir qualquer efeito externo.

## Entregue

- bloco `trigger.domain_event` com tipo, versao e tentativas validados;
- assinatura de evento criada e atualizada automaticamente durante a publicacao;
- desativacao e exclusao segura das assinaturas junto ao ciclo de vida do workflow;
- politica canonica de limite de etapas, tempo e concorrencia;
- timeout e concorrencia aplicados pelo backend;
- simulacao deterministica sem n8n, plugins, mensagens ou alteracao de dados;
- payload de teste validado contra o contrato publicado da empresa;
- trace operacional sem prompt, segredo ou conteudo de credenciais;
- auditoria da simulacao contendo apenas contagens e resultado;
- controles visuais em portugues no Estudio de Automacoes.

## Seguranca

- contratos e assinaturas permanecem isolados por `company_id`;
- a publicacao falha se o contrato exato nao estiver publicado;
- a simulacao bloqueia todos os blocos com efeito externo;
- nenhuma entrada integral e gravada na auditoria;
- conflitos de concorrencia retornam `409` em vez de criar filas falsas;
- timeout retorna falha real e rastreavel.

## Migracao

Nenhuma. A politica faz parte do JSON canonico versionado e assinaturas usam o schema criado no ciclo 58.

## Proximo passo exato

Implementar cancelamento cooperativo, compensacao declarativa e metricas agregadas de sucesso, latencia e reprocessamento por automacao.

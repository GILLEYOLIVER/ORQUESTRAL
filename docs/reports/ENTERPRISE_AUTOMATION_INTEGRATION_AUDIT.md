# Auditoria empresarial de automacao, integracoes e plugins

Data: 21 de julho de 2026.

## Resumo executivo

O Orkestral ja possui uma definicao canonica propria de workflow, versoes, publicacao, validacao, importacao, exportacao, execucoes, rollback e webhooks assinados. Esse desenho evita que a regra de negocio dependa diretamente do formato do n8n e coloca a automacao em Nivel 3.

A plataforma de integracoes e o sistema de plugins estao em Nivel 1 a 2. Existem credenciais criptografadas, manifestos, ativacao por empresa e testes de conexao, mas faltam contratos de conectores executaveis, catalogo de APIs, OAuth completo, politicas, sincronizacao, eventos transacionais, retentativas governadas, DLQ e observabilidade por operacao.

## Catalogo de blocos confirmado

| Categoria | Blocos |
| --- | --- |
| Gatilhos | `trigger.manual`, `trigger.schedule`, `trigger.webhook`, `trigger.message_received`, `trigger.contact_created` |
| Logica | `logic.condition`, `logic.wait`, `logic.loop` |
| Dados | `data.query`, `data.update` |
| Acoes | `action.email`, `action.message`, `action.plugin` |
| Inteligencia | `action.agent`, `action.human_approval` |
| Fluxo | `flow.end` |

Total confirmado: 16 tipos de bloco.

## Ciclo de vida atual do workflow

- Criacao e atualizacao da definicao canonica.
- Validacao de blocos e compatibilidade.
- Importacao e exportacao.
- Sincronizacao com provedor interno.
- Publicacao e snapshot de versao.
- Ativacao e desativacao.
- Execucao manual e por webhook.
- Historico de execucoes.
- Comparacao e restauracao de versoes.
- Duplicacao de fluxo.
- Segredo de webhook criptografado.

## Estado real do motor local

O container n8n esta saudavel, mas a API informa `configured=false` e `available=false` no endpoint de status do motor. Portanto, a infraestrutura esta presente, mas o contrato de configuracao entre API e n8n nao esta ativo no tenant/ambiente consultado. A interface deve continuar informando indisponibilidade, sem simular execucao.

Esse ponto deve ser corrigido por configuracao validada, nao por exposicao da URL ou token do n8n ao cliente.

## Plugins confirmados

| Plugin | Versao | Autenticacao |
| --- | --- | --- |
| `rest_api` | 1.0.0 | API key |
| `imap_email` | 1.0.0 | Usuario e senha |
| `smtp_email` | 1.0.0 | Usuario e senha |
| `google_calendar` | 1.0.0 | OAuth 2.0 |
| `external_postgresql` | 1.0.0 | String de conexao |
| `generic_webhook` | 1.0.0 | Segredo |
| `whatsapp_business` | 1.0.0 | OAuth 2.0 |

O status por empresa varia e nao representa que a integracao esteja operacional; ativacao, credencial valida e teste de conexao precisam ser avaliados separadamente.

## Controles existentes

- Catalogo global e ativacao por empresa.
- Manifesto JSON por plugin.
- Credenciais cifradas em repouso.
- Campos de credencial separados do valor cifrado.
- Expiracao e rotacao.
- Teste de conexao com duracao e resultado.
- Permissoes `plugins.view` e `plugins.manage`.
- Isolamento por `company_id` em credenciais e testes.
- Webhook de workflow com chave publica e segredo cifrado.

## Lacunas prioritarias

| Lacuna | Impacto | Prioridade |
| --- | --- | ---: |
| Transactional outbox | Evento pode divergir da transacao | Critica |
| Consumidor idempotente | Reentrega pode duplicar efeito | Critica |
| DLQ e reprocessamento | Falhas ficam sem recuperacao governada | Critica |
| Timeout/retry/circuit breaker por conector | Integracao externa pode prender recursos | Alta |
| Catalogo de APIs e versoes | Contratos ficam dispersos | Alta |
| OAuth completo e revogacao | Ciclo de credencial incompleto | Alta |
| Rate limit por empresa/conector | Um tenant pode saturar dependencia | Alta |
| Correlation e trace por operacao | Diagnostico entre sistemas limitado | Alta |
| Mapeamento e transformacao versionados | Sincronizacao fragil | Alta |
| Operacoes em lote | Baixa eficiencia para volume | Media |
| Assinatura e integridade de pacote | Risco de supply chain | Alta |
| Isolamento de codigo de plugin | Manifesto nao impede codigo arbitrario futuro | Critica |

## Interfaces-alvo

- `WorkflowEngine`: valida, simula, publica, executa, pausa e cancela.
- `WorkflowPublisher`: converte a definicao canonica para um provedor.
- `AutomationProvider`: encapsula n8n ou outro motor.
- `TriggerRegistry` e `ActionRegistry`: catalogos versionados.
- `ConnectorDefinition`: manifesto, schemas, autenticacao, acoes e gatilhos.
- `ConnectorRuntime`: executa com timeout, idempotencia e politicas.
- `CredentialProvider`: cifra, resolve, renova e revoga segredos.
- `EventBus`: publica eventos versionados sem acoplar broker.
- `OutboxPublisher`: entrega eventos confirmados pela transacao.

## Sequencia recomendada

1. Implementar eventos de dominio e transactional outbox no monolito modular.
2. Criar consumidor idempotente, retentativas e dead-letter queue sobre Celery/Redis.
3. Adaptar execucoes de workflow e plugins para correlation ID e politicas comuns.
4. Corrigir e testar a configuracao API-n8n sem expor o provedor.
5. Formalizar SDK de conectores com manifesto e schemas versionados.
6. Adicionar catalogo de APIs, OAuth, rate limit e observabilidade.

## Criterios de aceitacao do proximo recorte

- Evento e gravado na mesma transacao do dado empresarial.
- Publicacao falha sem perder o evento.
- Reentrega nao duplica efeitos.
- Evento inclui empresa, tipo, versao, correlacao e classificacao.
- Payload nao contem segredo nem dado desnecessario.
- Falha esgotada vai para DLQ e pode ser reprocessada.
- Empresa A nao consulta eventos, execucoes ou credenciais da Empresa B.
- n8n permanece substituivel e invisivel ao usuario final.

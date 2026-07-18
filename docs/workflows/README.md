# Workflows e motor de automação

A Fase 6 usa o n8n como motor interno, sem apresentar seu painel, URLs administrativas ou nomenclatura técnica aos clientes.

## Fronteira central

Todas as chamadas administrativas passam por `modules/workflows/services/n8n_client.py`. O cliente implementa autenticação por `X-N8N-API-KEY`, timeout, retentativas controladas e mensagens sanitizadas.

Operações suportadas:

- criar e atualizar workflows;
- publicar e desativar;
- consultar workflow e execuções;
- disparar o webhook interno de execução.

## Fonte de verdade

- `workflows`: definição segura, versão, empresa, estado local, sincronização e referências externas privadas.
- `workflow_executions`: origem, usuário, entrada/saída resumida, duração, estado e erro.

O identificador da empresa e o identificador interno da execução acompanham toda chamada ao motor.

## Webhooks públicos

O n8n não recebe webhooks públicos diretamente. O produtor chama:

```text
POST /api/webhooks/workflows/{public_key}
X-Orkestral-Signature: sha256=<hmac-do-corpo>
Content-Type: application/json
```

O segredo HMAC é exibido somente na criação ou rotação. A API valida tamanho, rate limit por origem, assinatura, workflow ativo e tenant antes de chamar o webhook privado do motor.

## Definições seguras

Importação aceita apenas blocos liberados, uma única entrada webhook e nenhuma credencial incorporada. O caminho interno é sempre regenerado. Exportações removem referências privadas e usam o formato `orkestral.workflow.v1`.

## Configuração local do n8n

1. Crie o proprietário local da instância.
2. Gere uma API key em **Settings > n8n API**.
3. Configure `N8N_API_KEY` no `.env` local.
4. Recrie o serviço `api`.

A chave deve possuir os escopos mínimos de workflow e execução. O n8n permanece ligado apenas à rede interna e à porta de loopback no perfil local.

Referência oficial de autenticação: <https://docs.n8n.io/api/authentication/>.

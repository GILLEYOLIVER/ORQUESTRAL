# Ciclo 82 - Execucao segura de sincronizacao REST

## Objetivo

Transformar os despachos agendados do ciclo 81 em execucoes reais, observaveis e
seguras, sem permitir acesso a redes internas nem expor credenciais ao navegador.

## Entregas

- Cliente HTTPS com TLS validado e conexao presa ao IP publico resolvido.
- Bloqueio de HTTP, redirecionamentos, userinfo, portas alternativas, redes
  privadas, loopback, link-local, enderecos reservados e destinos locais.
- Limites de cabecalho, corpo, tempo, compressao e quantidade de registros.
- Credenciais descriptografadas apenas dentro do processo worker.
- Claim atomico com expiracao e recuperacao depois de interrupcao.
- Ingestao tipada de ate 100 registros por despacho.
- Retentativa com backoff exponencial e estado terminal `dead_letter`.
- Reenvio administrativo auditado depois da correcao da causa.
- Observabilidade sem corpo de resposta, cursor, chave, token ou identificador
  bruto do worker.
- Teste de conexao da API REST migrado para a mesma fronteira HTTPS segura.

## Contrato da credencial REST

A credencial `rest_api` continua armazenada no cofre de Integracoes e aceita:

- `base_url`: URL HTTPS completa da colecao;
- `api_key`: valor opcional enviado no cabecalho de autenticacao;
- `auth_header`: nome opcional do cabecalho, padrao `Authorization`;
- `headers`: objeto opcional com cabecalhos adicionais seguros;
- `records_path`: caminho dos registros no JSON, padrao `records`;
- `next_cursor_path`: caminho do proximo cursor, padrao `next_cursor`;
- `cursor_parameter`: parametro de consulta do cursor, padrao `cursor`.

O corpo remoto deve ser uma lista ou um objeto contendo a lista indicada por
`records_path`. Cada item segue o contrato:

```json
{
  "source_record_id": "cliente-123",
  "external_id": "123",
  "display_name": "Cliente Exemplo",
  "email": "cliente@example.com",
  "phone": "+5511999999999"
}
```

## Estados da fila

- `pending`: aguardando processamento;
- `claimed`: reservado por um worker por tempo limitado;
- `failed`: falha temporaria aguardando backoff;
- `acknowledged`: resposta validada e processada;
- `dead_letter`: falha permanente ou esgotamento das tentativas;
- `expired`: reservado para politicas futuras de retencao.

## Seguranca

O DNS e validado antes da conexao e o socket TLS conecta diretamente ao IP
publico aprovado, mantendo o hostname original para SNI e validacao do
certificado. Assim, uma segunda resolucao DNS nao pode redirecionar a chamada
para a rede interna.

Somente metadados limitados sao persistidos: status HTTP, tamanho, quantidade
de registros, codigo de erro seguro e fingerprint SHA-256 do resultado.

## Validacao final executada em 23 de julho de 2026

- 269 testes de API, worker, integracao e seguranca aprovados.
- 19 testes do frontend aprovados e build Vite concluido.
- Ruff aprovado.
- mypy aprovado em 240 arquivos de producao.
- Migracao `20260723_0096` validada em upgrade, downgrade e reaplicacao.
- Executor operacional iniciado com sucesso usando o papel do worker.
- Funcoes de descoberta restritas ao proprietario e ao papel
  `orkestral_tenant_runtime`.
- Auditoria de segredos, frontend, banco, Actions, Bandit e dependencias
  concluida sem bloqueios.

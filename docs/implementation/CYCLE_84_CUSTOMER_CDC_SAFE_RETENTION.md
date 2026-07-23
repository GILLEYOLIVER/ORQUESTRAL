# Ciclo 84 - Retencao segura do CDC de clientes

## Garantia principal

O Orkestral nao remove um evento enquanto algum consumidor ativo ainda puder
precisar dele. A fronteira de exclusao combina:

1. o menor checkpoint entre todos os consumidores ativos;
2. o maior prazo de retencao entre todos os consumidores ativos;
3. um limite de exclusao por transacao;
4. um bloqueio transacional por empresa;
5. uma confirmacao literal obrigatoria.

Sem consumidor ativo, a politica falha fechada e nao exclui nada.

## Privacidade

O CDC ja armazena somente metadados e fingerprints. Este ciclo acrescenta a
remocao controlada desses metadados vencidos. O registro da limpeza conserva
somente contagens, fronteira, prazo, executor e horario.

## API

- `GET /crm/customer-data/cdc/retention/preview`
- `POST /crm/customer-data/cdc/retention/purge`

O preview e permitido a quem pode consultar contatos. A remocao exige
`crm.contacts.update` e continua bloqueada para o administrador somente leitura.

## Concorrencia

A transacao utiliza advisory lock por empresa e `FOR UPDATE SKIP LOCKED` nos
eventos candidatos. Isso evita duas limpezas concorrentes da mesma empresa e
mantem lotes curtos.


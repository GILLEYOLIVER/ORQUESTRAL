# ADR - Armazenamento S3 local mantido e fronteira neutra

**Status:** aceito em 30/07/2026

## Contexto

O serviço local anterior compilava uma versão comunitária arquivada do MinIO.
Isso aumentava a superfície de dependências e mantinha o domínio de conhecimento
acoplado diretamente ao cliente do fornecedor.

## Decisão

- Usar `rustfs/rustfs:1.0.0-beta.11-preview.1` somente no ambiente local e de testes.
- Manter o contrato S3 como fronteira portável para provedores externos.
- Centralizar operações em `S3ObjectStorage`.
- Exigir prefixo por empresa, checksum SHA-256, SSE-C quando configurado e
  confirmação de exclusão.
- Preservar o volume MinIO antigo fora do Compose até a validação e retenção
  operacional terminarem.
- Usar um volume RustFS novo porque formatos internos de disco não fazem parte
  do contrato S3 e não devem ser reutilizados diretamente.

## Migração executada

O serviço novo foi iniciado paralelamente. Objetos foram lidos da origem e
gravados no destino pela API S3, preservando a criptografia configurada. A
contagem foi comparada antes da troca. O volume antigo não foi apagado.

## Consequências

- O ambiente local deixa de compilar e executar o servidor comunitário arquivado.
- Backups novos usam `object-storage-rustfs-data.tar.gz`.
- Backups MinIO antigos não devem ser restaurados diretamente no volume RustFS;
  a migração deve ocorrer pela API S3.
- RustFS ainda está em versão beta e não é aprovado automaticamente para
  produção. Produção exige serviço S3 mantido, TLS, versionamento, retenção,
  backup e contrato operacional próprios.

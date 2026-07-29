# Ciclo 108 - Cadeia segura do marketplace

## Entrega

- publicadores confiaveis identificados por chave Ed25519 e fingerprint SHA-256;
- versoes assinadas sobre manifesto canonico, digest, compatibilidade e permissoes;
- instalacao por empresa com historico e rollback auditavel;
- validacao de dependencias, permissao, assinatura e versao antes da ativacao;
- auditoria sem chave privada, segredo ou conteudo do artefato.

## Limite de seguranca

O marketplace nao executa codigo arbitrario enviado por terceiros. A publicacao
registra contratos e digests; runtimes continuam sendo adaptadores revisados e
controlados pelo nucleo do Orkestral.

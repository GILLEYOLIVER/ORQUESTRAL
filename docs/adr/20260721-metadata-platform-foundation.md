# ADR - Fundacao versionada da plataforma de metadados

Data: 21 de julho de 2026.

## Decisao

O Orkestral passa a manter definicoes de entidades e campos em tabelas normalizadas,
sempre vinculadas a `company_id`. Cada alteracao ocorre em uma versao imutavel depois
da publicacao. JSONB fica restrito a configuracoes tipadas de campo e nunca substitui
o contrato principal.

O ciclo de vida inicial e:

1. criar rascunho;
2. substituir campos do rascunho;
3. validar contrato e checksum;
4. publicar explicitamente;
5. criar nova versao a partir da publicada;
6. manter a versao anterior como retirada para rollback futuro.

## Seguranca e governanca

- Todas as consultas filtram empresa e identificador do recurso.
- As rotas exigem `metadata.view`, `metadata.configure` ou `metadata.publish`.
- O Policy Engine registra cada decisao relevante.
- Alteracoes geram auditoria e eventos no outbox da mesma transacao.
- Versoes publicadas nao podem ser editadas.
- Chaves reservadas de infraestrutura sao rejeitadas.
- O schema possui checksum deterministico para integridade e promocao futura.

## Alternativas rejeitadas

- Um unico documento JSON por entidade: simples no inicio, mas fragil para validacao,
  seguranca por campo, migracoes e consultas.
- Tabelas fisicas criadas imediatamente por tenant: alto custo operacional e maior
  superficie para SQL dinamico inseguro.
- Acoplamento ao formato de outro fornecedor: prejudica portabilidade e evolucao.

## Proximos incrementos

- registros personalizados validados pelo schema publicado;
- layouts e visualizacoes versionados;
- permissoes por campo e acao;
- rollback explicito e promocao entre ambientes;
- renderer dinamico no frontend.

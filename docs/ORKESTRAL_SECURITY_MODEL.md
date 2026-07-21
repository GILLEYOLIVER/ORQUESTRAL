# Modelo de seguranca do Orkestral

## Principios

1. Toda autorizacao relevante e aplicada no backend.
2. Toda consulta empresarial resolve e filtra `company_id`.
3. Permissoes sao cumulativas apenas dentro da mesma empresa e nunca atravessam tenants.
4. Negacao de campo remove o valor da resposta; negacao de escrita retorna `403`.
5. Segredos, conteudo protegido e credenciais nao entram em eventos, logs ou auditorias.
6. Proprietarios mantem uma rota de recuperacao administrativa auditavel.

## Camadas de autorizacao

- Sessao: usuario ativo, sessao valida e empresa selecionada.
- Catalogo global: permissao de modulo e operacao, como `metadata.records.update`.
- Politica: risco, escopo de plataforma e permissoes declaradas pelo campo.
- Metadados: regra de entidade, regra de campo, proprietario e compartilhamento explicito.
- Persistencia: filtros de tenant em todas as consultas e constraints relacionais.

Uma camada nunca substitui outra. O acesso somente e concedido quando todas as camadas aplicaveis permitem.

## Seguranca da plataforma de metadados

- Entidades configuradas sem regra correspondente negam acesso por padrao.
- Regra direta do usuario prevalece sobre regras dos papeis vinculados.
- Multiplos papeis concedem a uniao autorizada, respeitando o menor escopo configurado diretamente para o usuario.
- `owned` limita aos registros do usuario.
- `owned_shared` inclui registros recebidos por compartilhamento.
- `all` permite todos os registros da entidade, sempre dentro da empresa atual.
- Compartilhamento de edicao implica leitura; compartilhamento nunca concede exclusao.
- Regras inexistentes preservam compatibilidade com instalações anteriores.

## Auditoria e resposta a incidentes

Alteracoes de politica, compartilhamentos e revogacoes registram ator, empresa, entidade, destinatario e permissao, sem copiar valores do registro. Eventos usam identificadores e contagens para permitir investigacao e automacao segura.

## Evolucao planejada

- testes sistematicos de acesso cruzado em todos os dominios;
- conjuntos de permissoes e grupos compostos;
- explicacao administrativa da decisao de acesso;
- avaliacao controlada de PostgreSQL Row-Level Security;
- SSO, MFA, SCIM, dispositivos e politicas condicionais na fase empresarial de identidade.

# Ciclo 76 — Turnos, feriados e cobertura mínima

## Objetivo

Impedir a publicação de escalas de revisão humana que deixem períodos críticos
sem responsáveis suficientes.

## Entrega

- vários turnos semanais por plantonista;
- turnos adjacentes permitidos e sobreposições detectadas;
- calendário versionado de feriados;
- feriado sem expediente ou com cobertura obrigatória;
- cobertura mínima simultânea por política;
- diagnóstico horário antes da publicação;
- publicação bloqueada quando existe lacuna ou sobreposição;
- roteamento pelo turno realmente ativo no fuso configurado;
- compatibilidade com políticas antigas de turno único;
- auditoria e isolamento multiempresa preservados;
- interface responsiva para montar, validar e publicar a escala.

## Segurança

Os usuários presentes nos turnos precisam ser aprovadores ativos da empresa. A
consulta de diagnóstico exige permissão de visualização e filtra empresa,
agente e política. A publicação repete a validação no backend e não confia no
resultado exibido pelo navegador.

## Persistência

A migração `20260723_0090` adiciona os turnos e feriados como contratos JSON
validados e versionados na política, além da cobertura mínima protegida por
restrição no PostgreSQL. O downgrade remove somente os campos deste ciclo.

## Evidências

- 242 testes de API, worker, integração e segurança aprovados;
- 19 testes da interface aprovados;
- teste positivo de turnos adjacentes e cobertura mínima;
- teste negativo de sobreposição com publicação bloqueada;
- build produtivo, lint e tipagem de 219 arquivos aprovados;
- auditoria sem segredos conhecidos ou vulnerabilidades conhecidas;
- downgrade e upgrade controlados, terminando no `head 0090`;
- oito serviços locais saudáveis;
- `/health`, `/ready` e `/app` aprovados.

## Continuidade

Com a cobertura operacional da Fase 4 concluída, o próximo recorte inicia a
Fase 5 pela identidade canônica e pela visão 360 do cliente.

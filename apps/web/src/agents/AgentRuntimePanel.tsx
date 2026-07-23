import { type FormEvent, useMemo, useState } from "react";

import { useSession } from "../session/context";
import {
  type RuntimeStatus,
  useAgentRuntime,
  useAgentRuntimeActions,
} from "./useAgentRuntime";
import "./agent-runtime.css";

const statusLabels: Record<RuntimeStatus, string> = {
  draft: "Rascunho",
  published: "Publicada",
  paused: "Pausada",
  retired: "Substituída",
};
const blockReasons: Record<string, string> = {
  tool_unavailable: "Ferramenta não habilitada",
  credential_binding_missing: "Credencial ainda não vinculada",
  credential_unavailable: "Credencial expirada ou revogada",
};

function toolKeys(value: string) {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function readableDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value))
    : "Ainda não executada";
}

export function AgentRuntimePanel({ agentId }: { agentId: string | null }) {
  const { me } = useSession();
  const canConfigure = Boolean(me?.permissions.includes("agents.configure"));
  const runtime = useAgentRuntime(agentId, canConfigure);
  const actions = useAgentRuntimeActions(agentId);
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleObjective, setScheduleObjective] = useState("");
  const [scheduleCadence, setScheduleCadence] = useState(60);
  const [scheduleTools, setScheduleTools] = useState("");
  const [triggerName, setTriggerName] = useState("");
  const [triggerEvent, setTriggerEvent] = useState("");
  const [triggerObjective, setTriggerObjective] = useState("");
  const [triggerTools, setTriggerTools] = useState("");
  const [bindingTool, setBindingTool] = useState("");
  const [bindingCredential, setBindingCredential] = useState("");
  const usableCredentials = useMemo(
    () => runtime.credentials.data?.filter((item) => item.usable) ?? [],
    [runtime.credentials.data],
  );

  if (!agentId) {
    return (
      <section className="agent-runtime-panel agent-runtime-empty">
        <p className="eyebrow">AUTONOMIA CONTROLADA</p>
        <h2>Agenda e eventos do agente</h2>
        <p>
          Selecione um agente para configurar quando ele poderá receber
          trabalho.
        </p>
      </section>
    );
  }

  const submitSchedule = (event: FormEvent) => {
    event.preventDefault();
    actions.createSchedule.mutate(
      {
        schedule_key: `agenda-${Date.now()}`,
        name: scheduleName,
        objective: scheduleObjective,
        cadence_minutes: scheduleCadence,
        required_tool_keys: toolKeys(scheduleTools),
      },
      {
        onSuccess: () => {
          setScheduleName("");
          setScheduleObjective("");
          setScheduleTools("");
        },
      },
    );
  };

  const submitTrigger = (event: FormEvent) => {
    event.preventDefault();
    actions.createTrigger.mutate(
      {
        trigger_key: `evento-${Date.now()}`,
        name: triggerName,
        event_type: triggerEvent.trim().toLowerCase(),
        min_event_version: 1,
        max_event_version: null,
        objective: triggerObjective,
        required_tool_keys: toolKeys(triggerTools),
      },
      {
        onSuccess: () => {
          setTriggerName("");
          setTriggerEvent("");
          setTriggerObjective("");
          setTriggerTools("");
        },
      },
    );
  };

  return (
    <section className="agent-runtime-panel">
      <header className="agent-runtime-heading">
        <div>
          <p className="eyebrow">AUTONOMIA CONTROLADA</p>
          <h2>Agenda, eventos e credenciais</h2>
          <p>
            Defina quando o agente recebe tarefas. O worker só libera execuções
            com ferramentas e credenciais válidas.
          </p>
        </div>
        <span className="agent-runtime-safety">
          Segredos nunca são exibidos
        </span>
      </header>

      <div className="agent-runtime-columns">
        <article className="agent-runtime-card">
          <h3>Execuções programadas</h3>
          <div className="agent-runtime-list">
            {(runtime.schedules.data ?? []).map((item) => (
              <div className="agent-runtime-item" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    A cada {item.cadence_minutes} min · versão {item.version}
                  </small>
                  <small>Próxima: {readableDate(item.next_run_at)}</small>
                </div>
                <div className="agent-runtime-actions">
                  <span
                    className={`runtime-status runtime-status-${item.status}`}
                  >
                    {statusLabels[item.status]}
                  </span>
                  {canConfigure && item.status === "draft" ? (
                    <button
                      type="button"
                      onClick={() => actions.publishSchedule.mutate(item.id)}
                    >
                      Publicar
                    </button>
                  ) : null}
                  {canConfigure && item.status === "published" ? (
                    <button
                      type="button"
                      onClick={() => actions.pauseSchedule.mutate(item.id)}
                    >
                      Pausar
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {runtime.schedules.data?.length === 0 ? (
              <p className="agent-runtime-muted">Nenhuma agenda criada.</p>
            ) : null}
          </div>
          {canConfigure ? (
            <form className="agent-runtime-form" onSubmit={submitSchedule}>
              <label>
                Nome
                <input
                  required
                  minLength={2}
                  value={scheduleName}
                  onChange={(event) => setScheduleName(event.target.value)}
                />
              </label>
              <label>
                Objetivo
                <textarea
                  required
                  minLength={5}
                  value={scheduleObjective}
                  onChange={(event) => setScheduleObjective(event.target.value)}
                />
              </label>
              <label>
                Intervalo em minutos
                <input
                  required
                  min={5}
                  max={10080}
                  type="number"
                  value={scheduleCadence}
                  onChange={(event) =>
                    setScheduleCadence(Number(event.target.value))
                  }
                />
              </label>
              <label>
                Ferramentas necessárias, separadas por vírgula
                <input
                  placeholder="crm.contact.view"
                  value={scheduleTools}
                  onChange={(event) => setScheduleTools(event.target.value)}
                />
              </label>
              <button disabled={actions.createSchedule.isPending} type="submit">
                Criar agenda em rascunho
              </button>
            </form>
          ) : (
            <p className="agent-runtime-readonly">
              Somente leitura: agendas visíveis, alterações bloqueadas.
            </p>
          )}
        </article>

        <article className="agent-runtime-card">
          <h3>Gatilhos por evento</h3>
          <div className="agent-runtime-list">
            {(runtime.triggers.data ?? []).map((item) => (
              <div className="agent-runtime-item" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {item.event_type} · versão {item.version}
                  </small>
                </div>
                <div className="agent-runtime-actions">
                  <span
                    className={`runtime-status runtime-status-${item.status}`}
                  >
                    {statusLabels[item.status]}
                  </span>
                  {canConfigure && item.status === "draft" ? (
                    <button
                      type="button"
                      onClick={() => actions.publishTrigger.mutate(item.id)}
                    >
                      Publicar
                    </button>
                  ) : null}
                  {canConfigure && item.status === "published" ? (
                    <button
                      type="button"
                      onClick={() => actions.pauseTrigger.mutate(item.id)}
                    >
                      Pausar
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {runtime.triggers.data?.length === 0 ? (
              <p className="agent-runtime-muted">Nenhum gatilho criado.</p>
            ) : null}
          </div>
          {canConfigure ? (
            <form className="agent-runtime-form" onSubmit={submitTrigger}>
              <label>
                Nome
                <input
                  required
                  minLength={2}
                  value={triggerName}
                  onChange={(event) => setTriggerName(event.target.value)}
                />
              </label>
              <label>
                Evento
                <input
                  required
                  pattern="[a-z][a-z0-9_.-]+"
                  placeholder="lead.created"
                  value={triggerEvent}
                  onChange={(event) => setTriggerEvent(event.target.value)}
                />
              </label>
              <label>
                Objetivo
                <textarea
                  required
                  minLength={5}
                  value={triggerObjective}
                  onChange={(event) => setTriggerObjective(event.target.value)}
                />
              </label>
              <label>
                Ferramentas necessárias, separadas por vírgula
                <input
                  value={triggerTools}
                  onChange={(event) => setTriggerTools(event.target.value)}
                />
              </label>
              <button disabled={actions.createTrigger.isPending} type="submit">
                Criar gatilho em rascunho
              </button>
            </form>
          ) : null}
        </article>
      </div>

      {canConfigure ? (
        <article className="agent-runtime-card agent-runtime-bindings">
          <div>
            <h3>Credenciais por ferramenta</h3>
            <p>
              O vínculo usa somente o identificador da credencial criptografada.
            </p>
          </div>
          <form
            className="agent-runtime-binding-form"
            onSubmit={(event) => {
              event.preventDefault();
              actions.bindCredential.mutate(
                { toolKey: bindingTool, credentialId: bindingCredential },
                {
                  onSuccess: () => {
                    setBindingTool("");
                    setBindingCredential("");
                  },
                },
              );
            }}
          >
            <label>
              Ferramenta
              <input
                required
                placeholder="crm.contact.view"
                value={bindingTool}
                onChange={(event) => setBindingTool(event.target.value)}
              />
            </label>
            <label>
              Credencial
              <select
                required
                value={bindingCredential}
                onChange={(event) => setBindingCredential(event.target.value)}
              >
                <option value="">Selecione</option>
                {usableCredentials.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={
                actions.bindCredential.isPending ||
                usableCredentials.length === 0
              }
              type="submit"
            >
              Vincular com segurança
            </button>
          </form>
          <div className="agent-runtime-binding-list">
            {(runtime.bindings.data ?? []).map((item) => (
              <span key={item.id}>
                <strong>{item.tool_key}</strong> ·{" "}
                {item.enabled ? "ativo" : "inativo"}
              </span>
            ))}
          </div>
          {usableCredentials.length === 0 ? (
            <p className="agent-runtime-muted">
              Crie uma credencial ativa em Integrações para habilitar vínculos.
            </p>
          ) : null}
        </article>
      ) : null}

      <article className="agent-runtime-card">
        <h3>Fila segura recente</h3>
        <div className="agent-runtime-dispatches">
          {(runtime.dispatches.data ?? []).slice(0, 12).map((item) => (
            <div className="agent-runtime-dispatch" key={item.id}>
              <span className={`runtime-dot runtime-dot-${item.status}`} />
              <div>
                <strong>
                  {item.source_type === "schedule" ? "Agenda" : "Evento"} ·{" "}
                  {item.status === "ready" ? "pronto" : "bloqueado"}
                </strong>
                <small>
                  {readableDate(item.scheduled_for)}
                  {item.reason_code
                    ? ` · ${blockReasons[item.reason_code] ?? item.reason_code}`
                    : ""}
                </small>
              </div>
            </div>
          ))}
          {runtime.dispatches.data?.length === 0 ? (
            <p className="agent-runtime-muted">
              Nenhum trabalho recebido até agora.
            </p>
          ) : null}
        </div>
      </article>
    </section>
  );
}

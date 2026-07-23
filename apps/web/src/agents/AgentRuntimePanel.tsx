import { type FormEvent, useMemo, useState } from "react";

import { useSession } from "../session/context";
import {
  type CompanyUserOption,
  type DispatchReview,
  type DispatchReviewAssignment,
  type RuntimeDispatch,
  type RuntimeStatus,
  useAgentRuntime,
  useAgentRuntimeActions,
} from "./useAgentRuntime";
import {
  dispatchSourceLabel,
  requiresDispatchReview,
} from "./dispatchReviewState";
import { parseRuntimeToolArguments } from "./runtimeToolArguments";
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
  execution_interrupted_manual_review:
    "Execução interrompida; revise antes de tentar novamente",
};
const dispatchLabels: Record<string, string> = {
  ready: "Pronto",
  blocked: "Bloqueado",
  processing: "Em execução",
  awaiting_approval: "Aguardando aprovação",
  simulated: "Simulado",
  completed: "Concluído",
  failed: "Falhou",
};
const weekdayLabels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

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

function isoDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function DispatchReviewControls({
  canConfigure,
  canExecute,
  dispatch,
  review,
  assignment,
  companyUsers,
  onAcknowledge,
  onApprove,
  onReassign,
  onReview,
  pending,
}: {
  canConfigure: boolean;
  canExecute: boolean;
  dispatch: RuntimeDispatch;
  review: DispatchReview | undefined;
  assignment: DispatchReviewAssignment | undefined;
  companyUsers: CompanyUserOption[];
  onAcknowledge: (assignmentId: string) => void;
  onApprove: (reviewId: string) => void;
  onReassign: (userId: string, reason: string) => void;
  onReview: (decision: "close" | "retry", reason: string) => void;
  pending: boolean;
}) {
  const [reason, setReason] = useState("");
  const [reassignUserId, setReassignUserId] = useState("");
  const [reassignReason, setReassignReason] = useState("");
  const assignee = companyUsers.find(
    (user) => user.user_id === assignment?.assigned_to_user_id,
  );
  const assignmentControls = assignment ? (
    <div className="dispatch-assignment-controls">
      <p>
        <strong>Responsável:</strong> {assignee?.name ?? "Usuário do plantão"} · {" "}
        {assignment.acknowledged_at ? "recebimento confirmado" : "aguardando confirmação"}
      </p>
      {!assignment.acknowledged_at ? (
        <button
          disabled={!canExecute || pending}
          onClick={() => onAcknowledge(assignment.id)}
          type="button"
        >
          Confirmar recebimento
        </button>
      ) : null}
      {canConfigure ? (
        <div className="dispatch-assignment-reassign">
          <select
            aria-label="Novo responsável"
            onChange={(event) => setReassignUserId(event.target.value)}
            value={reassignUserId}
          >
            <option value="">Selecione outro responsável</option>
            {companyUsers
              .filter(
                (user) =>
                  user.membership_status === "active" &&
                  user.user_id !== assignment.assigned_to_user_id,
              )
              .map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {user.name}
                </option>
              ))}
          </select>
          <input
            aria-label="Motivo da reatribuição"
            onChange={(event) => setReassignReason(event.target.value)}
            placeholder="Motivo da reatribuição"
            value={reassignReason}
          />
          <button
            disabled={!reassignUserId || reassignReason.trim().length < 10 || pending}
            onClick={() => onReassign(reassignUserId, reassignReason)}
            type="button"
          >
            Reatribuir com auditoria
          </button>
        </div>
      ) : null}
    </div>
  ) : null;
  if (!requiresDispatchReview(dispatch)) return null;
  if (review?.status === "closed") {
    return <p className="dispatch-review-state">Revisão encerrada sem repetição.</p>;
  }
  if (review?.status === "approved") {
    return <p className="dispatch-review-state">Nova execução aprovada e enfileirada.</p>;
  }
  if (review?.status === "pending_approval") {
    return (
      <div className="dispatch-review-actions">
        <p className="dispatch-review-state">Repetição preparada; falta aprovação explícita.</p>
        {assignmentControls}
        <button
          disabled={!canExecute || pending}
          onClick={() => onApprove(review.id)}
          type="button"
        >
          Aprovar nova execução
        </button>
        {!canExecute ? <small>Permissão agents.execute necessária.</small> : null}
      </div>
    );
  }
  return (
    <div className="dispatch-review-actions">
      <label>
        Motivo da decisão
        <textarea
          disabled={!canConfigure || pending}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Descreva o que foi verificado antes de decidir."
          rows={2}
          value={reason}
        />
      </label>
      <div className="dispatch-review-buttons">
        <button
          disabled={!canConfigure || pending || reason.trim().length < 10}
          onClick={() => onReview("close", reason)}
          type="button"
        >
          Encerrar sem repetir
        </button>
        <button
          disabled={!canConfigure || pending || reason.trim().length < 10}
          onClick={() => onReview("retry", reason)}
          type="button"
        >
          Preparar repetição
        </button>
      </div>
      {!canConfigure ? <small>Somente administradores podem decidir.</small> : null}
    </div>
  );
}

export function AgentRuntimePanel({ agentId }: { agentId: string | null }) {
  const { me } = useSession();
  const canConfigure = Boolean(me?.permissions.includes("agents.configure"));
  const canExecute = Boolean(me?.permissions.includes("agents.execute"));
  const runtime = useAgentRuntime(agentId, canConfigure);
  const actions = useAgentRuntimeActions(agentId);
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleObjective, setScheduleObjective] = useState("");
  const [scheduleCadence, setScheduleCadence] = useState(60);
  const [scheduleTools, setScheduleTools] = useState("");
  const [scheduleMode, setScheduleMode] = useState<"shadow" | "live">(
    "shadow",
  );
  const [scheduleCanary, setScheduleCanary] = useState(0);
  const [scheduleArguments, setScheduleArguments] = useState("{}");
  const [scheduleArgumentsError, setScheduleArgumentsError] = useState("");
  const [triggerName, setTriggerName] = useState("");
  const [triggerEvent, setTriggerEvent] = useState("");
  const [triggerObjective, setTriggerObjective] = useState("");
  const [triggerTools, setTriggerTools] = useState("");
  const [triggerMode, setTriggerMode] = useState<"shadow" | "live">("shadow");
  const [triggerCanary, setTriggerCanary] = useState(0);
  const [triggerArguments, setTriggerArguments] = useState("{}");
  const [triggerArgumentsError, setTriggerArgumentsError] = useState("");
  const [bindingTool, setBindingTool] = useState("");
  const [bindingCredential, setBindingCredential] = useState("");
  const [reviewPolicyName, setReviewPolicyName] = useState("Política operacional");
  const [reviewSlaMinutes, setReviewSlaMinutes] = useState(30);
  const [reviewEscalationMinutes, setReviewEscalationMinutes] = useState(120);
  const [reviewAcknowledgementMinutes, setReviewAcknowledgementMinutes] = useState(15);
  const [reviewOnCallIds, setReviewOnCallIds] = useState<string[]>([]);
  const [reviewOnCallTimezone, setReviewOnCallTimezone] = useState("UTC");
  const [reviewOnCallStartHour, setReviewOnCallStartHour] = useState(0);
  const [reviewOnCallEndHour, setReviewOnCallEndHour] = useState(24);
  const [reviewOnCallWeekdays, setReviewOnCallWeekdays] = useState<number[]>(
    () => Array.from({ length: 7 }, (_, day) => day),
  );
  const [absenceUserId, setAbsenceUserId] = useState("");
  const [absenceReason, setAbsenceReason] = useState("");
  const [absenceStartsAt, setAbsenceStartsAt] = useState("");
  const [absenceEndsAt, setAbsenceEndsAt] = useState("");
  const [handoffFromUserId, setHandoffFromUserId] = useState("");
  const [handoffToUserId, setHandoffToUserId] = useState("");
  const [handoffReason, setHandoffReason] = useState("");
  const [handoffStartsAt, setHandoffStartsAt] = useState("");
  const [handoffEndsAt, setHandoffEndsAt] = useState("");
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
    const requiredToolKeys = toolKeys(scheduleTools);
    let toolArguments: Record<string, Record<string, unknown>>;
    try {
      toolArguments = parseRuntimeToolArguments(
        scheduleArguments,
        requiredToolKeys,
      );
      setScheduleArgumentsError("");
    } catch (error) {
      setScheduleArgumentsError(
        error instanceof Error ? error.message : "JSON inválido.",
      );
      return;
    }
    actions.createSchedule.mutate(
      {
        schedule_key: `agenda-${Date.now()}`,
        name: scheduleName,
        objective: scheduleObjective,
        cadence_minutes: scheduleCadence,
        required_tool_keys: requiredToolKeys,
        tool_arguments: toolArguments,
        execution_mode: scheduleMode,
        canary_percentage: scheduleMode === "shadow" ? 0 : scheduleCanary,
      },
      {
        onSuccess: () => {
          setScheduleName("");
          setScheduleObjective("");
          setScheduleTools("");
          setScheduleMode("shadow");
          setScheduleCanary(0);
          setScheduleArguments("{}");
        },
      },
    );
  };

  const submitTrigger = (event: FormEvent) => {
    event.preventDefault();
    const requiredToolKeys = toolKeys(triggerTools);
    let toolArguments: Record<string, Record<string, unknown>>;
    try {
      toolArguments = parseRuntimeToolArguments(triggerArguments, requiredToolKeys);
      setTriggerArgumentsError("");
    } catch (error) {
      setTriggerArgumentsError(
        error instanceof Error ? error.message : "JSON inválido.",
      );
      return;
    }
    actions.createTrigger.mutate(
      {
        trigger_key: `evento-${Date.now()}`,
        name: triggerName,
        event_type: triggerEvent.trim().toLowerCase(),
        min_event_version: 1,
        max_event_version: null,
        objective: triggerObjective,
        required_tool_keys: requiredToolKeys,
        tool_arguments: toolArguments,
        execution_mode: triggerMode,
        canary_percentage: triggerMode === "shadow" ? 0 : triggerCanary,
      },
      {
        onSuccess: () => {
          setTriggerName("");
          setTriggerEvent("");
          setTriggerObjective("");
          setTriggerTools("");
          setTriggerMode("shadow");
          setTriggerCanary(0);
          setTriggerArguments("{}");
        },
      },
    );
  };

  const submitReviewPolicy = (event: FormEvent) => {
    event.preventDefault();
    actions.createReviewSLAPolicy.mutate({
      name: reviewPolicyName,
      sla_minutes: reviewSlaMinutes,
      escalation_minutes: reviewEscalationMinutes,
      acknowledgement_minutes: reviewAcknowledgementMinutes,
      on_call_user_ids: reviewOnCallIds,
      on_call_timezone: reviewOnCallTimezone,
      on_call_start_hour: reviewOnCallStartHour,
      on_call_end_hour: reviewOnCallEndHour,
      on_call_weekdays: reviewOnCallWeekdays,
    });
  };

  const submitOnCallException = (event: FormEvent) => {
    event.preventDefault();
    if (!runtime.activeReviewPolicyId) return;
    actions.createOnCallException.mutate(
      {
        policyId: runtime.activeReviewPolicyId,
        userId: absenceUserId,
        reason: absenceReason,
        startsAt: isoDateTime(absenceStartsAt),
        endsAt: isoDateTime(absenceEndsAt),
      },
      {
        onSuccess: () => {
          setAbsenceReason("");
          setAbsenceStartsAt("");
          setAbsenceEndsAt("");
        },
      },
    );
  };

  const submitOnCallHandoff = (event: FormEvent) => {
    event.preventDefault();
    if (!runtime.activeReviewPolicyId) return;
    actions.createOnCallHandoff.mutate(
      {
        policyId: runtime.activeReviewPolicyId,
        fromUserId: handoffFromUserId,
        toUserId: handoffToUserId,
        reason: handoffReason,
        startsAt: isoDateTime(handoffStartsAt),
        endsAt: isoDateTime(handoffEndsAt),
      },
      {
        onSuccess: () => {
          setHandoffReason("");
          setHandoffStartsAt("");
          setHandoffEndsAt("");
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
                  <small>
                    {item.execution_mode === "shadow"
                      ? "Modo sombra, sem efeitos externos"
                      : `Modo ao vivo · canary ${item.canary_percentage}%`}
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
              <label>
                Modo de execução
                <select
                  value={scheduleMode}
                  onChange={(event) =>
                    setScheduleMode(event.target.value as "shadow" | "live")
                  }
                >
                  <option value="shadow">Sombra, somente simular</option>
                  <option value="live">Ao vivo, com canary controlado</option>
                </select>
              </label>
              {scheduleMode === "live" ? (
                <label>
                  Percentual canary ao vivo
                  <input
                    min={0}
                    max={100}
                    type="number"
                    value={scheduleCanary}
                    onChange={(event) =>
                      setScheduleCanary(Number(event.target.value))
                    }
                  />
                </label>
              ) : null}
              <label>
                Argumentos por ferramenta em JSON
                <textarea
                  spellCheck={false}
                  value={scheduleArguments}
                  onChange={(event) => setScheduleArguments(event.target.value)}
                />
                <small>
                  Exemplo: {`{"orkestral.company.summary": {}}`}
                </small>
              </label>
              {scheduleArgumentsError ? (
                <p className="agent-runtime-error" role="alert">
                  {scheduleArgumentsError}
                </p>
              ) : null}
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
                  <small>
                    {item.execution_mode === "shadow"
                      ? "Modo sombra, sem efeitos externos"
                      : `Modo ao vivo · canary ${item.canary_percentage}%`}
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
              <label>
                Modo de execução
                <select
                  value={triggerMode}
                  onChange={(event) =>
                    setTriggerMode(event.target.value as "shadow" | "live")
                  }
                >
                  <option value="shadow">Sombra, somente simular</option>
                  <option value="live">Ao vivo, com canary controlado</option>
                </select>
              </label>
              {triggerMode === "live" ? (
                <label>
                  Percentual canary ao vivo
                  <input
                    min={0}
                    max={100}
                    type="number"
                    value={triggerCanary}
                    onChange={(event) =>
                      setTriggerCanary(Number(event.target.value))
                    }
                  />
                </label>
              ) : null}
              <label>
                Argumentos por ferramenta em JSON
                <textarea
                  spellCheck={false}
                  value={triggerArguments}
                  onChange={(event) => setTriggerArguments(event.target.value)}
                />
              </label>
              {triggerArgumentsError ? (
                <p className="agent-runtime-error" role="alert">
                  {triggerArgumentsError}
                </p>
              ) : null}
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
        <h3>Revisões operacionais</h3>
        <p className="agent-runtime-muted">
          SLA de {runtime.reviewSummary.data?.sla_minutes ?? 30} minutos e
          escalonamento em {runtime.reviewSummary.data?.escalation_minutes ?? 120}
          minutos, sem exibir argumentos ou credenciais.
        </p>
        <div className="dispatch-review-metrics">
          <span>
            <strong>{runtime.reviewSummary.data?.pending ?? 0}</strong>
            Pendentes
          </span>
          <span data-alert={(runtime.reviewSummary.data?.overdue ?? 0) > 0}>
            <strong>{runtime.reviewSummary.data?.overdue ?? 0}</strong>
            Fora do prazo
          </span>
          <span>
            <strong>{runtime.reviewSummary.data?.approved ?? 0}</strong>
            Repetições aprovadas
          </span>
          <span>
            <strong>{runtime.reviewSummary.data?.repeat_interruptions ?? 0}</strong>
            Reincidências
          </span>
        </div>
        {canConfigure ? (
          <div className="dispatch-review-policy">
            <form className="agent-runtime-form" onSubmit={submitReviewPolicy}>
              <label>
                Nome da política
                <input
                  minLength={3}
                  onChange={(event) => setReviewPolicyName(event.target.value)}
                  required
                  value={reviewPolicyName}
                />
              </label>
              <label>
                Avisar após (minutos)
                <input
                  max={10080}
                  min={5}
                  onChange={(event) => setReviewSlaMinutes(Number(event.target.value))}
                  required
                  type="number"
                  value={reviewSlaMinutes}
                />
              </label>
              <label>
                Escalonar após (minutos)
                <input
                  max={20160}
                  min={reviewSlaMinutes + 1}
                  onChange={(event) =>
                    setReviewEscalationMinutes(Number(event.target.value))
                  }
                  required
                  type="number"
                  value={reviewEscalationMinutes}
                />
              </label>
              <label>
                Confirmar recebimento em (minutos)
                <input
                  max={1440}
                  min={1}
                  onChange={(event) =>
                    setReviewAcknowledgementMinutes(Number(event.target.value))
                  }
                  required
                  type="number"
                  value={reviewAcknowledgementMinutes}
                />
              </label>
              <label>
                Fuso do plantão
                <input
                  onChange={(event) => setReviewOnCallTimezone(event.target.value)}
                  required
                  value={reviewOnCallTimezone}
                />
              </label>
              <label>
                Início do plantão (hora)
                <input
                  max={23}
                  min={0}
                  onChange={(event) =>
                    setReviewOnCallStartHour(Number(event.target.value))
                  }
                  required
                  type="number"
                  value={reviewOnCallStartHour}
                />
              </label>
              <label>
                Fim do plantão (hora)
                <input
                  max={24}
                  min={1}
                  onChange={(event) =>
                    setReviewOnCallEndHour(Number(event.target.value))
                  }
                  required
                  type="number"
                  value={reviewOnCallEndHour}
                />
              </label>
              <fieldset className="dispatch-on-call-users">
                <legend>Responsáveis de plantão</legend>
                {(runtime.companyUsers.data ?? [])
                  .filter((user) => user.membership_status === "active")
                  .map((user) => (
                    <label key={user.user_id}>
                      <input
                        checked={reviewOnCallIds.includes(user.user_id)}
                        onChange={(event) =>
                          setReviewOnCallIds((current) =>
                            event.target.checked
                              ? [...current, user.user_id]
                              : current.filter((id) => id !== user.user_id),
                          )
                        }
                        type="checkbox"
                      />
                      {user.name}
                    </label>
                  ))}
              </fieldset>
              <fieldset className="dispatch-on-call-users">
                <legend>Dias da semana</legend>
                {weekdayLabels.map((label, day) => (
                  <label key={label}>
                    <input
                      checked={reviewOnCallWeekdays.includes(day)}
                      onChange={(event) =>
                        setReviewOnCallWeekdays((current) =>
                          event.target.checked
                            ? [...current, day].sort()
                            : current.filter((value) => value !== day),
                        )
                      }
                      type="checkbox"
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              <button
                disabled={
                  actions.createReviewSLAPolicy.isPending ||
                  reviewEscalationMinutes <= reviewSlaMinutes ||
                  reviewOnCallWeekdays.length === 0
                }
                type="submit"
              >
                Criar nova versão
              </button>
            </form>
            <div className="agent-runtime-policy-list">
              {(runtime.reviewPolicies.data ?? []).map((policy) => (
                <div key={policy.id}>
                  <span>
                    <strong>{policy.name}</strong> · versão {policy.version} · {" "}
                    {statusLabels[policy.status]}
                  </span>
                  <small>
                    Aviso {policy.sla_minutes} min · escalonamento {" "}
                    {policy.escalation_minutes} min · confirmação {" "}
                    {policy.acknowledgement_minutes} min · {" "}
                    {policy.on_call_user_ids.length} plantonista(s) · {" "}
                    {policy.on_call_weekdays.map((day) => weekdayLabels[day]).join(", ")}
                  </small>
                  {policy.status === "draft" ? (
                    <button
                      disabled={actions.publishReviewSLAPolicy.isPending}
                      onClick={() => actions.publishReviewSLAPolicy.mutate(policy.id)}
                      type="button"
                    >
                      Publicar política
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            {runtime.activeReviewPolicyId ? (
              <div className="dispatch-on-call-management">
                <form className="agent-runtime-form" onSubmit={submitOnCallException}>
                  <h4>Registrar ausência</h4>
                  <select
                    aria-label="Plantonista ausente"
                    onChange={(event) => setAbsenceUserId(event.target.value)}
                    required
                    value={absenceUserId}
                  >
                    <option value="">Selecione o plantonista</option>
                    {(runtime.companyUsers.data ?? [])
                      .filter((user) =>
                        runtime.reviewPolicies.data
                          ?.find((policy) => policy.id === runtime.activeReviewPolicyId)
                          ?.on_call_user_ids.includes(user.user_id),
                      )
                      .map((user) => (
                        <option key={user.user_id} value={user.user_id}>
                          {user.name}
                        </option>
                      ))}
                  </select>
                  <input
                    onChange={(event) => setAbsenceStartsAt(event.target.value)}
                    required
                    type="datetime-local"
                    value={absenceStartsAt}
                  />
                  <input
                    onChange={(event) => setAbsenceEndsAt(event.target.value)}
                    required
                    type="datetime-local"
                    value={absenceEndsAt}
                  />
                  <input
                    minLength={10}
                    onChange={(event) => setAbsenceReason(event.target.value)}
                    placeholder="Motivo operacional da ausência"
                    required
                    value={absenceReason}
                  />
                  <button disabled={actions.createOnCallException.isPending} type="submit">
                    Registrar ausência
                  </button>
                </form>
                <div className="agent-runtime-policy-list">
                  {(runtime.onCallExceptions.data ?? []).map((exception) => (
                    <div key={exception.id}>
                      <span>
                        <strong>
                          {runtime.companyUsers.data?.find(
                            (user) => user.user_id === exception.user_id,
                          )?.name ?? "Plantonista"}
                        </strong> · {exception.status === "active" ? "ausente" : "cancelada"}
                      </span>
                      <small>
                        {readableDate(exception.starts_at)} até {readableDate(exception.ends_at)}
                      </small>
                      {exception.status === "active" ? (
                        <button
                          disabled={actions.cancelOnCallException.isPending}
                          onClick={() =>
                            actions.cancelOnCallException.mutate({
                              exceptionId: exception.id,
                              policyId: runtime.activeReviewPolicyId!,
                            })
                          }
                          type="button"
                        >
                          Cancelar ausência
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
                <form className="agent-runtime-form" onSubmit={submitOnCallHandoff}>
                  <h4>Passagem de plantão</h4>
                  <select
                    aria-label="Responsável de origem"
                    onChange={(event) => setHandoffFromUserId(event.target.value)}
                    required
                    value={handoffFromUserId}
                  >
                    <option value="">Responsável atual</option>
                    {(runtime.companyUsers.data ?? []).map((user) => (
                      <option key={user.user_id} value={user.user_id}>
                        {user.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Substituto do plantão"
                    onChange={(event) => setHandoffToUserId(event.target.value)}
                    required
                    value={handoffToUserId}
                  >
                    <option value="">Substituto</option>
                    {(runtime.companyUsers.data ?? [])
                      .filter((user) => user.user_id !== handoffFromUserId)
                      .map((user) => (
                        <option key={user.user_id} value={user.user_id}>
                          {user.name}
                        </option>
                      ))}
                  </select>
                  <input
                    onChange={(event) => setHandoffStartsAt(event.target.value)}
                    required
                    type="datetime-local"
                    value={handoffStartsAt}
                  />
                  <input
                    onChange={(event) => setHandoffEndsAt(event.target.value)}
                    required
                    type="datetime-local"
                    value={handoffEndsAt}
                  />
                  <input
                    minLength={10}
                    onChange={(event) => setHandoffReason(event.target.value)}
                    placeholder="Motivo da passagem"
                    required
                    value={handoffReason}
                  />
                  <button disabled={actions.createOnCallHandoff.isPending} type="submit">
                    Solicitar aceite
                  </button>
                </form>
                <div className="agent-runtime-policy-list">
                  {(runtime.onCallHandoffs.data ?? []).map((handoff) => (
                    <div key={handoff.id}>
                      <span>
                        <strong>Passagem de plantão</strong> · {handoff.status}
                      </span>
                      <small>
                        {readableDate(handoff.starts_at)} até {readableDate(handoff.ends_at)}
                      </small>
                      {handoff.status === "pending" && canExecute ? (
                        <span className="dispatch-review-buttons">
                          <button
                            disabled={actions.respondOnCallHandoff.isPending}
                            onClick={() =>
                              actions.respondOnCallHandoff.mutate({
                                decision: "accept",
                                handoffId: handoff.id,
                                policyId: runtime.activeReviewPolicyId!,
                              })
                            }
                            type="button"
                          >
                            Aceitar
                          </button>
                          <button
                            disabled={actions.respondOnCallHandoff.isPending}
                            onClick={() =>
                              actions.respondOnCallHandoff.mutate({
                                decision: "reject",
                                handoffId: handoff.id,
                                policyId: runtime.activeReviewPolicyId!,
                              })
                            }
                            type="button"
                          >
                            Recusar
                          </button>
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </article>

      <article className="agent-runtime-card">
        <h3>Fila segura recente</h3>
        <div className="agent-runtime-dispatches">
          {(runtime.dispatches.data ?? []).slice(0, 12).map((item) => {
            const review = runtime.reviews.data?.find(
              (candidate) => candidate.interrupted_dispatch_id === item.id,
            );
            const assignment = runtime.reviewAssignments.data?.find(
              (candidate) =>
                candidate.review_id === review?.id && candidate.ended_at === null,
            );
            return (
              <div className="agent-runtime-dispatch" key={item.id}>
                <span className={`runtime-dot runtime-dot-${item.status}`} />
                <div>
                  <strong>
                    {dispatchSourceLabel(item.source_type)} ·{" "}
                    {dispatchLabels[item.status] ?? item.status}
                  </strong>
                  <small>
                    {readableDate(item.scheduled_for)}
                    {` · ${item.execution_mode === "shadow" ? "sombra" : "ao vivo"}`}
                    {item.attempt_count > 0
                      ? ` · tentativa ${item.attempt_count}`
                      : ""}
                    {item.reason_code
                      ? ` · ${blockReasons[item.reason_code] ?? item.reason_code}`
                      : ""}
                  </small>
                  <DispatchReviewControls
                    assignment={assignment}
                    canConfigure={canConfigure}
                    canExecute={canExecute}
                    companyUsers={runtime.companyUsers.data ?? []}
                    dispatch={item}
                    onAcknowledge={(assignmentId) =>
                      review &&
                      actions.acknowledgeReviewAssignment.mutate({
                        assignmentId,
                        reviewId: review.id,
                      })
                    }
                    onApprove={(reviewId) =>
                      actions.approveDispatchRetry.mutate({
                        reviewId,
                        idempotencyKey: crypto.randomUUID(),
                      })
                    }
                    onReview={(decision, reason) =>
                      actions.reviewDispatch.mutate({
                        decision,
                        dispatchId: item.id,
                        idempotencyKey: crypto.randomUUID(),
                        reason,
                      })
                    }
                    onReassign={(userId, reassignReason) =>
                      review &&
                      actions.reassignReview.mutate({
                        assignedToUserId: userId,
                        reason: reassignReason,
                        reviewId: review.id,
                      })
                    }
                    pending={
                      actions.reviewDispatch.isPending ||
                      actions.approveDispatchRetry.isPending ||
                      actions.acknowledgeReviewAssignment.isPending ||
                      actions.reassignReview.isPending
                    }
                    review={review}
                  />
                </div>
              </div>
            );
          })}
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

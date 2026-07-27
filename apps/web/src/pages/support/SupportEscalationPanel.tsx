import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlarmClock,
  CalendarDays,
  CheckCircle2,
  ClockAlert,
  Play,
  ShieldAlert,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-escalation.css";

type Calendar = {
  id: string;
  name: string;
  timezone: string;
  is_default: boolean;
  is_active: boolean;
};

type SlaPolicy = {
  id: string;
  name: string;
};

type EscalationPolicy = {
  id: string;
  name: string;
  warning_minutes_before: number;
  action: "notify" | "prioritize" | "reassign_queue" | "reassign_user";
  is_active: boolean;
};

type Summary = {
  active_policies: number;
  due_soon: number;
  breached: number;
  warnings_sent: number;
  escalations_applied: number;
  calendar_open: boolean;
};

type Maintenance = {
  evaluated: number;
  warnings: number;
  escalations: number;
  skipped_outside_calendar: number;
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível configurar o escalonamento.";
}

export function SupportEscalationPanel() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [calendarName, setCalendarName] = useState("Atendimento comercial");
  const [policyName, setPolicyName] = useState("Escalonamento padrão");
  const [calendarId, setCalendarId] = useState("");
  const [slaPolicyId, setSlaPolicyId] = useState("");
  const [warningMinutes, setWarningMinutes] = useState("30");
  const [action, setAction] =
    useState<EscalationPolicy["action"]>("prioritize");
  const [lastRun, setLastRun] = useState<Maintenance | null>(null);

  const calendars = useQuery({
    queryKey: ["support", "escalations", "calendars"],
    queryFn: () =>
      request<Calendar[]>("/support/escalations/calendars"),
  });
  const policies = useQuery({
    queryKey: ["support", "escalations", "policies"],
    queryFn: () =>
      request<EscalationPolicy[]>("/support/escalations/policies"),
  });
  const slaPolicies = useQuery({
    queryKey: ["support", "sla-policies"],
    queryFn: () => request<SlaPolicy[]>("/support/sla-policies"),
  });
  const summary = useQuery({
    queryKey: ["support", "escalations", "summary"],
    queryFn: () => request<Summary>("/support/escalations/summary"),
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["support", "escalations"],
      }),
      queryClient.invalidateQueries({ queryKey: ["support", "dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["support-tickets"] }),
    ]);
  };
  const createCalendar = useMutation({
    mutationFn: () =>
      request<Calendar>("/support/escalations/calendars", {
        method: "POST",
        body: {
          name: calendarName,
          timezone: "America/Sao_Paulo",
          weekly_schedule: {
            mon: [{ start: "09:00", end: "18:00" }],
            tue: [{ start: "09:00", end: "18:00" }],
            wed: [{ start: "09:00", end: "18:00" }],
            thu: [{ start: "09:00", end: "18:00" }],
            fri: [{ start: "09:00", end: "18:00" }],
            sat: [],
            sun: [],
          },
          holidays: [],
          is_default: true,
        },
      }),
    onSuccess: async (result) => {
      setCalendarId(result.id);
      await refresh();
    },
  });
  const createPolicy = useMutation({
    mutationFn: () =>
      request<EscalationPolicy>("/support/escalations/policies", {
        method: "POST",
        body: {
          name: policyName,
          calendar_id: calendarId,
          sla_policy_id: slaPolicyId,
          warning_minutes_before: Math.max(0, Number(warningMinutes)),
          action,
        },
      }),
    onSuccess: refresh,
  });
  const maintain = useMutation({
    mutationFn: () =>
      request<Maintenance>("/support/escalations/maintain", {
        method: "POST",
      }),
    onSuccess: async (result) => {
      setLastRun(result);
      await refresh();
    },
  });
  const mutationError =
    createCalendar.error ?? createPolicy.error ?? maintain.error;

  return (
    <section className="support-escalation">
      <header>
        <div>
          <span className="eyebrow">Compromissos controlados</span>
          <h2>SLA e escalonamento</h2>
          <p>
            Antecipe riscos e aja automaticamente dentro do horário de
            atendimento.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          <AlarmClock size={17} />
          {expanded ? "Recolher SLA" : "Configurar SLA"}
        </Button>
      </header>

      <div className="support-escalation__summary">
        <article>
          <CalendarDays size={19} />
          <span>Calendário</span>
          <strong>{summary.data?.calendar_open ? "Aberto" : "Fechado"}</strong>
        </article>
        <article>
          <ClockAlert size={19} />
          <span>Em risco</span>
          <strong>{summary.data?.due_soon ?? 0}</strong>
        </article>
        <article>
          <ShieldAlert size={19} />
          <span>Escalonados</span>
          <strong>{summary.data?.escalations_applied ?? 0}</strong>
        </article>
      </div>

      {mutationError ? (
        <Alert variant="error">{errorMessage(mutationError)}</Alert>
      ) : null}
      {lastRun ? (
        <Alert variant="info">
          Verificação concluída: {lastRun.evaluated} chamados,{" "}
          {lastRun.warnings} avisos e {lastRun.escalations} escalonamentos.
        </Alert>
      ) : null}

      {expanded ? (
        <div className="support-escalation__body">
          <PermissionGuard all={["support.tickets.update"]}>
            <Card eyebrow="1. Horário de atendimento">
              <label>
                Nome do calendário
                <input
                  onChange={(event) => setCalendarName(event.target.value)}
                  value={calendarName}
                />
              </label>
              <p>Segunda a sexta, das 09h às 18h, horário de São Paulo.</p>
              <Button
                disabled={calendarName.trim().length < 2}
                onClick={() => createCalendar.mutate()}
              >
                <CalendarDays size={17} />
                Criar calendário
              </Button>
            </Card>

            <Card eyebrow="2. Regra de escalonamento">
              <label>
                Nome da política
                <input
                  onChange={(event) => setPolicyName(event.target.value)}
                  value={policyName}
                />
              </label>
              <label>
                Calendário
                <select
                  onChange={(event) => setCalendarId(event.target.value)}
                  value={calendarId}
                >
                  <option value="">Selecione</option>
                  {calendars.data?.map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Política de SLA
                <select
                  onChange={(event) => setSlaPolicyId(event.target.value)}
                  value={slaPolicyId}
                >
                  <option value="">Selecione</option>
                  {slaPolicies.data?.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Avisar quantos minutos antes
                <input
                  min="0"
                  onChange={(event) => setWarningMinutes(event.target.value)}
                  type="number"
                  value={warningMinutes}
                />
              </label>
              <label>
                Ação no vencimento
                <select
                  onChange={(event) =>
                    setAction(event.target.value as EscalationPolicy["action"])
                  }
                  value={action}
                >
                  <option value="notify">Somente notificar</option>
                  <option value="prioritize">Marcar como urgente</option>
                </select>
              </label>
              <Button
                disabled={!calendarId || !slaPolicyId || policyName.length < 2}
                onClick={() => createPolicy.mutate()}
              >
                <CheckCircle2 size={17} />
                Ativar política
              </Button>
            </Card>

            <Card eyebrow="Verificação operacional">
              <strong>
                {policies.data?.filter((policy) => policy.is_active).length ??
                  0}{" "}
                políticas ativas
              </strong>
              <p>
                O worker verifica automaticamente a cada minuto. Esta ação
                permite testar agora.
              </p>
              <Button
                variant="secondary"
                onClick={() => maintain.mutate()}
              >
                <Play size={17} />
                Verificar SLAs agora
              </Button>
            </Card>
          </PermissionGuard>
        </div>
      ) : null}
    </section>
  );
}

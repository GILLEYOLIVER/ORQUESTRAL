import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Gauge,
  History,
  Inbox,
  Plus,
  Star,
  UserRoundX,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-operations.css";

type Dashboard = {
  open_tickets: number;
  unassigned_tickets: number;
  waiting_tickets: number;
  breached_tickets: number;
  due_soon_tickets: number;
  resolved_today: number;
  average_first_response_minutes: number;
  satisfaction_average: number;
  satisfaction_responses: number;
};

type Queue = {
  id: string;
  name: string;
  key: string;
  description: string | null;
  color: string;
  is_default: boolean;
  open_tickets: number;
  unassigned_tickets: number;
  breached_tickets: number;
};

type SLAPolicy = {
  id: string;
  name: string;
  description: string | null;
  targets: Record<string, { first_response: number; resolution: number }>;
  business_hours_only: boolean;
  is_default: boolean;
};

type TicketEvent = {
  id: string;
  event_type: string;
  description: string;
  details: Record<string, unknown>;
  created_at: string;
};

export interface SupportOperationalTicket {
  id: string;
  status: "open" | "in_progress" | "waiting" | "resolved" | "closed";
  priority: "low" | "normal" | "high" | "urgent";
  queue_id: string | null;
  sla_policy_id: string | null;
  first_response_due_at: string | null;
  resolution_due_at: string | null;
  first_responded_at: string | null;
  breached_at: string | null;
  satisfaction_score: number | null;
  satisfaction_comment: string | null;
}

const eventLabels: Record<string, string> = {
  created: "Chamado criado",
  assigned: "Responsável alterado",
  queue_changed: "Fila alterada",
  priority_changed: "Prioridade alterada",
  status_changed: "Status alterado",
  first_response: "Primeira resposta",
  sla_breached: "SLA violado",
  satisfaction_received: "Avaliação recebida",
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação de suporte.";
}

function deadlineLabel(value: string | null) {
  if (!value) return "Ainda não calculado";
  const deadline = new Date(value);
  const minutes = Math.round((deadline.getTime() - Date.now()) / 60_000);
  if (minutes < 0) return `${Math.abs(minutes)} min em atraso`;
  if (minutes < 60) return `${minutes} min restantes`;
  return `${Math.round(minutes / 60)} h restantes`;
}

export function SupportOperationsPanel({
  ticket,
  onTicketUpdated,
}: {
  ticket: SupportOperationalTicket | null;
  onTicketUpdated: (ticket: SupportOperationalTicket) => void;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [showQueueForm, setShowQueueForm] = useState(false);
  const [showSlaForm, setShowSlaForm] = useState(false);
  const [queueName, setQueueName] = useState("");
  const [queueKey, setQueueKey] = useState("");
  const [policyName, setPolicyName] = useState("");
  const [normalResponse, setNormalResponse] = useState("240");
  const [normalResolution, setNormalResolution] = useState("1440");
  const [score, setScore] = useState(5);
  const [satisfactionComment, setSatisfactionComment] = useState("");

  const dashboard = useQuery({
    queryKey: ["support", "dashboard"],
    queryFn: () => request<Dashboard>("/support/dashboard"),
  });
  const queues = useQuery({
    queryKey: ["support", "queues"],
    queryFn: () => request<Queue[]>("/support/queues"),
  });
  const policies = useQuery({
    queryKey: ["support", "sla-policies"],
    queryFn: () => request<SLAPolicy[]>("/support/sla-policies"),
  });
  const events = useQuery({
    queryKey: ["support", "ticket-events", ticket?.id],
    queryFn: () =>
      request<TicketEvent[]>(`/support/tickets/${ticket?.id}/events`),
    enabled: Boolean(ticket),
  });

  const refreshOperations = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["support", "dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["support", "queues"] }),
      queryClient.invalidateQueries({ queryKey: ["support-tickets"] }),
      queryClient.invalidateQueries({
        queryKey: ["support", "ticket-events", ticket?.id],
      }),
    ]);
  };

  const updateTicket = useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      request<SupportOperationalTicket>(
        `/support/tickets/${ticket?.id}/operations`,
        {
          method: "PATCH",
          body: changes,
        },
      ),
    onSuccess: async (updated) => {
      onTicketUpdated(updated);
      await refreshOperations();
    },
  });

  const createQueue = useMutation({
    mutationFn: () =>
      request<Queue>("/support/queues", {
        method: "POST",
        body: {
          name: queueName,
          key: queueKey,
          description: `Fila operacional ${queueName}`,
          color: "#2f6f64",
        },
      }),
    onSuccess: async () => {
      setQueueName("");
      setQueueKey("");
      setShowQueueForm(false);
      await queryClient.invalidateQueries({ queryKey: ["support", "queues"] });
    },
  });

  const createPolicy = useMutation({
    mutationFn: () => {
      const response = Math.max(1, Number(normalResponse));
      const resolution = Math.max(response, Number(normalResolution));
      return request<SLAPolicy>("/support/sla-policies", {
        method: "POST",
        body: {
          name: policyName,
          description: "Política criada no painel operacional.",
          business_hours_only: false,
          targets: {
            low: { first_response: response * 2, resolution: resolution * 2 },
            normal: { first_response: response, resolution },
            high: {
              first_response: Math.max(1, Math.round(response / 4)),
              resolution: Math.max(1, Math.round(resolution / 3)),
            },
            urgent: {
              first_response: Math.max(1, Math.round(response / 12)),
              resolution: Math.max(1, Math.round(resolution / 12)),
            },
          },
        },
      });
    },
    onSuccess: async () => {
      setPolicyName("");
      setShowSlaForm(false);
      await queryClient.invalidateQueries({
        queryKey: ["support", "sla-policies"],
      });
    },
  });

  const satisfaction = useMutation({
    mutationFn: () =>
      request<SupportOperationalTicket>(
        `/support/tickets/${ticket?.id}/satisfaction`,
        {
          method: "POST",
          body: { score, comment: satisfactionComment || null },
        },
      ),
    onSuccess: async (updated) => {
      onTicketUpdated(updated);
      setSatisfactionComment("");
      await refreshOperations();
    },
  });

  const operationError =
    updateTicket.error ||
    createQueue.error ||
    createPolicy.error ||
    satisfaction.error;
  const data = dashboard.data;

  return (
    <section className="support-operations">
      <header>
        <div>
          <span className="eyebrow">Operação e qualidade</span>
          <h2>Painel de atendimento</h2>
          <p>
            Priorize a fila, proteja os prazos e acompanhe a experiência do
            cliente.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          <Gauge size={17} />{" "}
          {expanded ? "Recolher operação" : "Gerenciar operação"}
        </Button>
      </header>

      <div className="support-operation-metrics">
        <article>
          <Inbox size={19} />
          <span>Em aberto</span>
          <strong>{data?.open_tickets ?? 0}</strong>
        </article>
        <article>
          <UserRoundX size={19} />
          <span>Sem responsável</span>
          <strong>{data?.unassigned_tickets ?? 0}</strong>
        </article>
        <article className={(data?.breached_tickets ?? 0) > 0 ? "danger" : ""}>
          <AlertTriangle size={19} />
          <span>SLA violado</span>
          <strong>{data?.breached_tickets ?? 0}</strong>
        </article>
        <article>
          <Clock3 size={19} />
          <span>Primeira resposta</span>
          <strong>{data?.average_first_response_minutes ?? 0} min</strong>
        </article>
        <article>
          <Star size={19} />
          <span>Satisfação</span>
          <strong>{data?.satisfaction_average ?? 0}/5</strong>
        </article>
      </div>

      {expanded ? (
        <div className="support-operations-body">
          {operationError ? (
            <Alert variant="error">{errorMessage(operationError)}</Alert>
          ) : null}
          <div className="support-queue-heading">
            <div>
              <h3>Filas de atendimento</h3>
              <p>Distribua chamados por especialidade ou equipe.</p>
            </div>
            <PermissionGuard all={["support.tickets.create"]}>
              <div className="support-config-actions">
                <button onClick={() => setShowQueueForm((value) => !value)}>
                  <Plus size={15} /> Nova fila
                </button>
                <button onClick={() => setShowSlaForm((value) => !value)}>
                  <Clock3 size={15} /> Nova política SLA
                </button>
              </div>
            </PermissionGuard>
          </div>

          {showQueueForm ? (
            <Card
              className="support-config-form"
              eyebrow="Configuração de fila"
            >
              <label>
                Nome
                <input
                  value={queueName}
                  onChange={(event) => {
                    setQueueName(event.target.value);
                    setQueueKey(
                      event.target.value
                        .toLowerCase()
                        .normalize("NFD")
                        .replace(/[\u0300-\u036f]/g, "")
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, ""),
                    );
                  }}
                />
              </label>
              <label>
                Identificador
                <input
                  value={queueKey}
                  onChange={(event) => setQueueKey(event.target.value)}
                />
              </label>
              <Button
                disabled={queueName.length < 2 || queueKey.length < 2}
                loading={createQueue.isPending}
                onClick={() => createQueue.mutate()}
              >
                Criar fila
              </Button>
            </Card>
          ) : null}

          {showSlaForm ? (
            <Card
              className="support-config-form"
              eyebrow="Metas de atendimento"
            >
              <label>
                Nome da política
                <input
                  value={policyName}
                  onChange={(event) => setPolicyName(event.target.value)}
                />
              </label>
              <label>
                Resposta normal em minutos
                <input
                  type="number"
                  min="1"
                  value={normalResponse}
                  onChange={(event) => setNormalResponse(event.target.value)}
                />
              </label>
              <label>
                Resolução normal em minutos
                <input
                  type="number"
                  min="1"
                  value={normalResolution}
                  onChange={(event) => setNormalResolution(event.target.value)}
                />
              </label>
              <Button
                disabled={policyName.length < 2}
                loading={createPolicy.isPending}
                onClick={() => createPolicy.mutate()}
              >
                Criar política
              </Button>
            </Card>
          ) : null}

          <div className="support-queue-grid">
            {queues.data?.map((queue) => (
              <article
                key={queue.id}
                style={{ "--queue-color": queue.color } as React.CSSProperties}
              >
                <i />
                <div>
                  <strong>{queue.name}</strong>
                  <span>{queue.description || "Fila operacional"}</span>
                </div>
                <dl>
                  <div>
                    <dt>Abertos</dt>
                    <dd>{queue.open_tickets}</dd>
                  </div>
                  <div>
                    <dt>Sem responsável</dt>
                    <dd>{queue.unassigned_tickets}</dd>
                  </div>
                  <div>
                    <dt>Violados</dt>
                    <dd>{queue.breached_tickets}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>

          {ticket ? (
            <div className="support-ticket-operations">
              <Card eyebrow="Chamado selecionado">
                <h3>Controle operacional e SLA</h3>
                <div className="support-ticket-controls">
                  <label>
                    Fila
                    <select
                      value={ticket.queue_id ?? ""}
                      onChange={(event) =>
                        updateTicket.mutate({
                          queue_id: event.target.value || null,
                        })
                      }
                    >
                      <option value="">Fila padrão</option>
                      {queues.data?.map((queue) => (
                        <option key={queue.id} value={queue.id}>
                          {queue.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Política SLA
                    <select
                      value={ticket.sla_policy_id ?? ""}
                      onChange={(event) =>
                        updateTicket.mutate({
                          sla_policy_id: event.target.value || null,
                        })
                      }
                    >
                      <option value="">SLA padrão</option>
                      {policies.data?.map((policy) => (
                        <option key={policy.id} value={policy.id}>
                          {policy.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Prioridade
                    <select
                      value={ticket.priority}
                      onChange={(event) =>
                        updateTicket.mutate({ priority: event.target.value })
                      }
                    >
                      <option value="low">Baixa</option>
                      <option value="normal">Normal</option>
                      <option value="high">Alta</option>
                      <option value="urgent">Urgente</option>
                    </select>
                  </label>
                </div>
                <div className="support-deadlines">
                  <article
                    className={
                      ticket.first_responded_at
                        ? "met"
                        : ticket.breached_at
                          ? "breached"
                          : ""
                    }
                  >
                    <span>Primeira resposta</span>
                    <strong>
                      {ticket.first_responded_at
                        ? "Respondido"
                        : deadlineLabel(ticket.first_response_due_at)}
                    </strong>
                  </article>
                  <article
                    className={
                      ticket.status === "resolved" || ticket.status === "closed"
                        ? "met"
                        : ticket.breached_at
                          ? "breached"
                          : ""
                    }
                  >
                    <span>Resolução</span>
                    <strong>
                      {ticket.status === "resolved" ||
                      ticket.status === "closed"
                        ? "Resolvido"
                        : deadlineLabel(ticket.resolution_due_at)}
                    </strong>
                  </article>
                </div>
              </Card>

              <Card eyebrow="Linha do tempo">
                <div className="support-event-list">
                  {events.data?.length ? (
                    events.data.map((event) => (
                      <article key={event.id}>
                        <History size={16} />
                        <div>
                          <strong>
                            {eventLabels[event.event_type] || event.description}
                          </strong>
                          <span>{event.description}</span>
                          <time>
                            {new Date(event.created_at).toLocaleString("pt-BR")}
                          </time>
                        </div>
                      </article>
                    ))
                  ) : (
                    <p>Nenhuma alteração operacional registrada.</p>
                  )}
                </div>
              </Card>

              {ticket.status === "resolved" || ticket.status === "closed" ? (
                <Card className="support-satisfaction" eyebrow="Voz do cliente">
                  <h3>Avaliação do atendimento</h3>
                  <div className="support-stars">
                    {[1, 2, 3, 4, 5].map((value) => (
                      <button
                        className={value <= score ? "active" : ""}
                        key={value}
                        onClick={() => setScore(value)}
                        aria-label={`${value} estrelas`}
                      >
                        <Star size={22} />
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={satisfactionComment}
                    onChange={(event) =>
                      setSatisfactionComment(event.target.value)
                    }
                    placeholder="Comentário opcional do cliente"
                  />
                  <Button
                    loading={satisfaction.isPending}
                    onClick={() => satisfaction.mutate()}
                  >
                    <CheckCircle2 size={16} /> Registrar avaliação
                  </Button>
                </Card>
              ) : null}
            </div>
          ) : (
            <p className="support-select-hint">
              Selecione um chamado na lista para configurar fila, SLA e
              acompanhar seu histórico.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

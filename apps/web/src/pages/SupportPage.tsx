import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CircleCheck,
  Clock3,
  LifeBuoy,
  MessageSquare,
  Plus,
  Search,
  X,
} from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  SupportOperationsPanel,
  type SupportOperationalTicket,
} from "./support/SupportOperationsPanel";
import { SupportRoutingPanel } from "./support/SupportRoutingPanel";

type TicketStatus = "open" | "in_progress" | "waiting" | "resolved" | "closed";
type TicketPriority = "low" | "normal" | "high" | "urgent";
type TicketChannel = "web" | "email" | "phone" | "whatsapp" | "other";

interface SupportTicket {
  id: string;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  channel: TicketChannel;
  assignee_user_id: string | null;
  required_skill_id: string | null;
  language_code: string | null;
  requester_contact_id: string | null;
  due_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  queue_id: string | null;
  sla_policy_id: string | null;
  first_response_due_at: string | null;
  resolution_due_at: string | null;
  first_responded_at: string | null;
  breached_at: string | null;
  satisfaction_score: number | null;
  satisfaction_comment: string | null;
}

interface SupportInteraction {
  id: string;
  message: string;
  is_internal: boolean;
  created_at: string;
}

const statusLabels: Record<TicketStatus, string> = {
  open: "Aberto",
  in_progress: "Em atendimento",
  waiting: "Aguardando",
  resolved: "Resolvido",
  closed: "Fechado",
};

const priorityLabels: Record<TicketPriority, string> = {
  low: "Baixa",
  normal: "Normal",
  high: "Alta",
  urgent: "Urgente",
};

const channelLabels: Record<TicketChannel, string> = {
  web: "Plataforma",
  email: "E-mail",
  phone: "Telefone",
  whatsapp: "WhatsApp",
  other: "Outro",
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function SupportPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [creating, setCreating] = useState(false);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TicketPriority>("normal");
  const [channel, setChannel] = useState<TicketChannel>("web");
  const [message, setMessage] = useState("");

  const tickets = useQuery({
    queryKey: ["support-tickets", search, statusFilter, priorityFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (statusFilter) params.set("status", statusFilter);
      if (priorityFilter) params.set("priority", priorityFilter);
      return request<SupportTicket[]>(`/support/tickets?${params}`);
    },
  });
  const interactions = useQuery({
    queryKey: ["support-interactions", selected?.id],
    queryFn: () =>
      request<SupportInteraction[]>(
        `/support/tickets/${selected?.id}/interactions`,
      ),
    enabled: Boolean(selected),
  });
  const create = useMutation({
    mutationFn: () =>
      request<SupportTicket>("/support/tickets", {
        method: "POST",
        body: { subject, description, priority, channel },
      }),
    onSuccess: async (ticket) => {
      setSubject("");
      setDescription("");
      setPriority("normal");
      setChannel("web");
      setCreating(false);
      setSelected(ticket);
      await queryClient.invalidateQueries({ queryKey: ["support-tickets"] });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TicketStatus }) =>
      request<SupportTicket>(`/support/tickets/${id}/operations`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: async (ticket) => {
      setSelected(ticket);
      await queryClient.invalidateQueries({ queryKey: ["support-tickets"] });
    },
  });
  const comment = useMutation({
    mutationFn: () =>
      request<SupportInteraction>(`/support/tickets/${selected?.id}/response`, {
        method: "POST",
        body: { message, is_internal: false },
      }),
    onSuccess: async () => {
      setMessage("");
      await queryClient.invalidateQueries({
        queryKey: ["support-interactions", selected?.id],
      });
    },
  });

  const mutationError = create.error ?? update.error ?? comment.error;

  return (
    <div className="management-page crm-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Atendimento organizado</span>
          <h1>Central de suporte</h1>
          <p>
            Acompanhe cada pedido do cliente do primeiro contato ate a solucao.
          </p>
        </div>
        <PermissionGuard all={["support.tickets.create"]}>
          <Button
            onClick={() => {
              setCreating(true);
              setSelected(null);
            }}
          >
            <Plus size={17} /> Novo chamado
          </Button>
        </PermissionGuard>
      </div>

      <SupportOperationsPanel
        ticket={selected}
        onTicketUpdated={(ticket: SupportOperationalTicket) =>
          setSelected((current) =>
            current ? { ...current, ...ticket } : current,
          )
        }
      />
      <SupportRoutingPanel
        ticket={selected}
        onAssigned={(userId) =>
          setSelected((current) =>
            current ? { ...current, assignee_user_id: userId } : current,
          )
        }
      />

      {tickets.isError ? (
        <Alert variant="error">
          {errorMessage(
            tickets.error,
            "Nao foi possivel carregar os chamados.",
          )}
        </Alert>
      ) : null}
      {mutationError ? (
        <Alert variant="error">
          {errorMessage(mutationError, "Nao foi possivel concluir a operacao.")}
        </Alert>
      ) : null}

      <Card className="crm-filters" eyebrow="Pesquisa e filtros">
        <label className="search-field">
          <Search aria-hidden="true" size={17} />
          <input
            aria-label="Pesquisar chamados"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Assunto ou descricao"
            type="search"
            value={search}
          />
        </label>
        <select
          aria-label="Filtrar chamados por status"
          onChange={(event) => setStatusFilter(event.target.value)}
          value={statusFilter}
        >
          <option value="">Todos os status</option>
          {Object.entries(statusLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar chamados por prioridade"
          onChange={(event) => setPriorityFilter(event.target.value)}
          value={priorityFilter}
        >
          <option value="">Todas as prioridades</option>
          {Object.entries(priorityLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Card>

      <div className="crm-layout">
        <Card
          className="crm-list"
          eyebrow={`${tickets.data?.length ?? 0} chamados`}
        >
          {tickets.isLoading ? <p>Carregando chamados...</p> : null}
          {!tickets.isLoading && tickets.data?.length === 0 ? (
            <div className="empty-state">
              <LifeBuoy size={28} />
              <strong>Nenhum chamado encontrado</strong>
              <span>Cadastre o primeiro pedido de atendimento.</span>
            </div>
          ) : null}
          {tickets.data?.map((ticket) => (
            <button
              className={`contact-row ${selected?.id === ticket.id ? "contact-row--active" : ""}`}
              key={ticket.id}
              onClick={() => {
                setSelected(ticket);
                setCreating(false);
              }}
              type="button"
            >
              <span className="contact-avatar">
                {ticket.status === "resolved" || ticket.status === "closed" ? (
                  <CircleCheck size={17} />
                ) : (
                  <Clock3 size={17} />
                )}
              </span>
              <span className="contact-row__body">
                <strong>{ticket.subject}</strong>
                <small>
                  {priorityLabels[ticket.priority]} ·{" "}
                  {channelLabels[ticket.channel]}
                </small>
              </span>
              <span
                className={`status-chip ${
                  ticket.status === "resolved" || ticket.status === "closed"
                    ? "status-chip--active"
                    : "status-chip--inactive"
                }`}
              >
                {statusLabels[ticket.status]}
              </span>
            </button>
          ))}
        </Card>

        <div className="crm-side-panel">
          {creating ? (
            <Card className="crm-editor" eyebrow="Novo chamado">
              <div className="panel-heading">
                <div>
                  <h2>Registrar atendimento</h2>
                  <p>Descreva de forma clara o que o cliente precisa.</p>
                </div>
                <button
                  aria-label="Fechar formulario"
                  className="icon-button"
                  onClick={() => setCreating(false)}
                >
                  <X size={18} />
                </button>
              </div>
              <form
                className="stack-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  create.mutate();
                }}
              >
                <TextField
                  label="Assunto"
                  onChange={(event) => setSubject(event.target.value)}
                  required
                  value={subject}
                />
                <label className="native-field">
                  <span>Descricao</span>
                  <textarea
                    onChange={(event) => setDescription(event.target.value)}
                    required
                    rows={5}
                    value={description}
                  />
                </label>
                <div className="crm-form-grid">
                  <label className="native-field">
                    <span>Prioridade</span>
                    <select
                      onChange={(event) =>
                        setPriority(event.target.value as TicketPriority)
                      }
                      value={priority}
                    >
                      {Object.entries(priorityLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="native-field">
                    <span>Canal</span>
                    <select
                      onChange={(event) =>
                        setChannel(event.target.value as TicketChannel)
                      }
                      value={channel}
                    >
                      {Object.entries(channelLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <Button
                  disabled={
                    subject.trim().length < 3 || description.trim().length < 3
                  }
                  loading={create.isPending}
                  type="submit"
                >
                  Criar chamado
                </Button>
              </form>
            </Card>
          ) : selected ? (
            <Card className="crm-details" eyebrow="Detalhes do chamado">
              <div className="panel-heading">
                <div>
                  <h2>{selected.subject}</h2>
                  <span className="status-chip status-chip--inactive">
                    {priorityLabels[selected.priority]}
                  </span>
                </div>
                <button
                  aria-label="Fechar detalhes"
                  className="icon-button"
                  onClick={() => setSelected(null)}
                >
                  <X size={18} />
                </button>
              </div>
              <p>{selected.description}</p>
              <PermissionGuard all={["support.tickets.update"]}>
                <label className="native-field">
                  <span>Status do chamado</span>
                  <select
                    onChange={(event) =>
                      update.mutate({
                        id: selected.id,
                        status: event.target.value as TicketStatus,
                      })
                    }
                    value={selected.status}
                  >
                    {Object.entries(statusLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </PermissionGuard>
              <div className="contact-facts">
                {interactions.isLoading ? (
                  <span>Carregando historico...</span>
                ) : null}
                {interactions.data?.map((interaction) => (
                  <span key={interaction.id}>
                    <MessageSquare size={16} /> {interaction.message}
                  </span>
                ))}
              </div>
              <PermissionGuard all={["support.tickets.comment"]}>
                <div className="stack-form">
                  <label className="native-field">
                    <span>Nova interacao</span>
                    <textarea
                      onChange={(event) => setMessage(event.target.value)}
                      rows={3}
                      value={message}
                    />
                  </label>
                  <Button
                    disabled={!message.trim()}
                    loading={comment.isPending}
                    onClick={() => comment.mutate()}
                  >
                    Registrar interacao
                  </Button>
                </div>
              </PermissionGuard>
            </Card>
          ) : (
            <Card eyebrow="Fila de atendimento">
              <div className="empty-state">
                <LifeBuoy size={28} />
                <strong>Selecione um chamado</strong>
                <span>O historico e as acoes aparecerao aqui.</span>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

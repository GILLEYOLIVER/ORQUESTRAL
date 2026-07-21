import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BellRing,
  Check,
  CheckCheck,
  Clock3,
  Mail,
  MessageCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import {
  type ApprovalRequest,
  type NotificationItem,
  type NotificationPreference,
  useApprovals,
  useNotificationPreferences,
  useNotifications,
  useNotificationSummary,
} from "../notifications/useNotifications";
import { useSession } from "../session/context";
import "../notifications/notifications.css";

type PreferenceDraft = {
  in_app_enabled: boolean;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  whatsapp_recipient: string;
  reminders_enabled: boolean;
};

const defaultPreference: PreferenceDraft = {
  in_app_enabled: true,
  email_enabled: false,
  whatsapp_enabled: false,
  whatsapp_recipient: "",
  reminders_enabled: true,
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function sourceLabel(source: ApprovalRequest["source_type"]) {
  if (source === "workflow") return "Automação";
  if (source === "agent") return "Agente";
  return "Operação";
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function NotificationsPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const notifications = useNotifications();
  const summary = useNotificationSummary();
  const canViewApprovals = me?.permissions.includes("approvals.view") ?? false;
  const canDecideApprovals =
    me?.permissions.includes("approvals.decide") ?? false;
  const approvals = useApprovals(canViewApprovals);
  const preferences = useNotificationPreferences();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<PreferenceDraft>(defaultPreference);

  const globalPreference = useMemo(
    () => preferences.data?.find((item) => item.event_type === "*"),
    [preferences.data],
  );

  useEffect(() => {
    if (!globalPreference) return;
    setDraft({
      in_app_enabled: globalPreference.in_app_enabled,
      email_enabled: globalPreference.email_enabled,
      whatsapp_enabled: globalPreference.whatsapp_enabled,
      whatsapp_recipient: globalPreference.whatsapp_recipient ?? "",
      reminders_enabled: globalPreference.reminders_enabled,
    });
  }, [globalPreference]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["approvals"] }),
    ]);
  };

  const markRead = useMutation({
    mutationFn: (notificationId: string) =>
      request<NotificationItem>(`/notifications/${notificationId}/read`, {
        method: "POST",
      }),
    onSuccess: refresh,
  });

  const markAllRead = useMutation({
    mutationFn: () => request("/notifications/read-all", { method: "POST" }),
    onSuccess: async () => {
      setFeedback("Todas as notificações foram marcadas como lidas.");
      await refresh();
    },
  });

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: string }) =>
      request<ApprovalRequest>(`/notifications/approvals/${id}/decision`, {
        method: "POST",
        body: { decision },
      }),
    onSuccess: async (approval, variables) => {
      setError(null);
      setFeedback(
        variables.decision === "approved"
          ? approval.status === "pending"
            ? "Seu voto foi registrado. A solicitação continua aguardando o quórum ou a próxima etapa."
            : "A solicitação foi aprovada e a operação pode continuar."
          : "A solicitação foi rejeitada e a operação foi interrompida.",
      );
      await refresh();
    },
    onError: (caught) => {
      setFeedback(null);
      setError(errorMessage(caught, "Não foi possível registrar a decisão."));
    },
  });

  const savePreference = useMutation({
    mutationFn: () =>
      request<NotificationPreference>("/notifications/preferences", {
        method: "PUT",
        body: {
          event_type: "*",
          ...draft,
          whatsapp_recipient: draft.whatsapp_recipient || null,
        },
      }),
    onSuccess: async () => {
      setError(null);
      setFeedback("Preferências de comunicação atualizadas.");
      await queryClient.invalidateQueries({
        queryKey: ["notification-preferences"],
      });
    },
    onError: (caught) => {
      setFeedback(null);
      setError(
        errorMessage(caught, "Não foi possível salvar as preferências."),
      );
    },
  });

  return (
    <div className="attention-page">
      <section className="attention-hero">
        <div>
          <span className="eyebrow eyebrow--light">Central de atenção</span>
          <h1>Decisões humanas no ritmo certo.</h1>
          <p>
            Acompanhe eventos importantes, autorize operações sensíveis e
            escolha como deseja ser avisado.
          </p>
        </div>
        <div className="attention-hero__numbers">
          <article>
            <strong>{summary.data?.unread_count ?? 0}</strong>
            <span>não lidas</span>
          </article>
          <article>
            <strong>{summary.data?.pending_approvals ?? 0}</strong>
            <span>decisões pendentes</span>
          </article>
        </div>
      </section>

      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}

      <section className="attention-grid">
        <Card className="attention-panel attention-panel--approvals">
          <div className="attention-panel__heading">
            <div>
              <span className="eyebrow">Controle humano</span>
              <h2>Aprovações aguardando você</h2>
            </div>
            <ShieldCheck size={24} />
          </div>
          {!canViewApprovals ? (
            <p className="attention-empty">
              Seu papel não possui acesso à fila de aprovações.
            </p>
          ) : approvals.isLoading ? (
            <p className="attention-empty">Carregando decisões…</p>
          ) : approvals.data?.length ? (
            <div className="approval-list">
              {approvals.data.map((approval) => (
                <article className="approval-card" key={approval.id}>
                  <div className="approval-card__meta">
                    <span>{sourceLabel(approval.source_type)}</span>
                    <span>
                      <Clock3 size={13} /> {formatDate(approval.created_at)}
                    </span>
                  </div>
                  <h3>{approval.title}</h3>
                  <p>{approval.description}</p>
                  {typeof approval.context.approval_stage_name === "string" ? (
                    <div className="approval-card__progress">
                      <span>
                        Etapa {String(approval.context.approval_stage_order)} ·{" "}
                        {approval.context.approval_stage_name}
                      </span>
                      <strong>
                        {String(
                          approval.context.approval_stage_approved_votes ?? 0,
                        )}
                        /{String(approval.context.approval_stage_quorum)} votos
                      </strong>
                    </div>
                  ) : null}
                  {canDecideApprovals ? (
                    <div className="approval-card__actions">
                      <Button
                        loading={
                          decide.isPending &&
                          decide.variables?.id === approval.id &&
                          decide.variables.decision === "approved"
                        }
                        onClick={() =>
                          decide.mutate({
                            id: approval.id,
                            decision: "approved",
                          })
                        }
                      >
                        <Check size={16} /> Aprovar
                      </Button>
                      <Button
                        loading={
                          decide.isPending &&
                          decide.variables?.id === approval.id &&
                          decide.variables.decision === "rejected"
                        }
                        onClick={() =>
                          decide.mutate({
                            id: approval.id,
                            decision: "rejected",
                          })
                        }
                        variant="secondary"
                      >
                        <X size={16} /> Rejeitar
                      </Button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="attention-empty">
              <CheckCheck size={28} />
              <p>Nenhuma decisão pendente no momento.</p>
            </div>
          )}
        </Card>

        <Card className="attention-panel attention-panel--notifications">
          <div className="attention-panel__heading">
            <div>
              <span className="eyebrow">Linha do tempo</span>
              <h2>Notificações recentes</h2>
            </div>
            <Button
              disabled={!summary.data?.unread_count}
              loading={markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
              variant="ghost"
            >
              Marcar todas como lidas
            </Button>
          </div>
          {notifications.isLoading ? (
            <p className="attention-empty">Carregando notificações…</p>
          ) : notifications.data?.length ? (
            <div className="notification-list">
              {notifications.data.map((notification) => (
                <article
                  className={`notification-row notification-row--${notification.severity} ${notification.read_at ? "" : "notification-row--unread"}`}
                  key={notification.id}
                >
                  <span className="notification-row__icon">
                    <BellRing size={17} />
                  </span>
                  <div>
                    <div className="notification-row__heading">
                      <strong>{notification.title}</strong>
                      <time>{formatDate(notification.created_at)}</time>
                    </div>
                    <p>{notification.message}</p>
                  </div>
                  {!notification.read_at ? (
                    <button
                      aria-label={`Marcar ${notification.title} como lida`}
                      onClick={() => markRead.mutate(notification.id)}
                      type="button"
                    >
                      <Check size={15} />
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="attention-empty">
              <BellRing size={28} />
              <p>Sua linha do tempo está tranquila.</p>
            </div>
          )}
        </Card>
      </section>

      <Card className="preference-panel">
        <div className="attention-panel__heading">
          <div>
            <span className="eyebrow">Preferências pessoais</span>
            <h2>Como você quer ser avisado</h2>
          </div>
          <span className="preference-panel__note">
            Canais externos nunca são ativados sem sua autorização.
          </span>
        </div>
        <div className="preference-grid">
          <label className="channel-option">
            <input
              checked={draft.in_app_enabled}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  in_app_enabled: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <BellRing size={20} />
            <span>
              <strong>Dentro da Orkestral</strong>
              <small>Central e contador no sino</small>
            </span>
          </label>
          <label className="channel-option">
            <input
              checked={draft.email_enabled}
              disabled={!globalPreference?.email_channel_configured}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  email_enabled: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <Mail size={20} />
            <span>
              <strong>E-mail</strong>
              <small>
                {globalPreference?.email_channel_configured
                  ? "Usa seu e-mail corporativo"
                  : "Canal ainda não configurado"}
              </small>
            </span>
          </label>
          <label className="channel-option channel-option--whatsapp">
            <input
              checked={draft.whatsapp_enabled}
              disabled={!globalPreference?.whatsapp_channel_configured}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  whatsapp_enabled: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <MessageCircle size={20} />
            <span>
              <strong>WhatsApp autorizado</strong>
              <small>
                {globalPreference?.whatsapp_channel_configured
                  ? "Somente para o número informado"
                  : "Canal ainda não configurado"}
              </small>
            </span>
            <input
              aria-label="Número autorizado para WhatsApp"
              disabled={
                !draft.whatsapp_enabled ||
                !globalPreference?.whatsapp_channel_configured
              }
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  whatsapp_recipient: event.target.value,
                }))
              }
              placeholder="+55 11 99999-9999"
              type="tel"
              value={draft.whatsapp_recipient}
            />
          </label>
          <label className="channel-option">
            <input
              checked={draft.reminders_enabled}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  reminders_enabled: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <Clock3 size={20} />
            <span>
              <strong>Lembretes</strong>
              <small>Reforços para decisões ainda pendentes</small>
            </span>
          </label>
        </div>
        <Button
          className="preference-panel__save"
          loading={savePreference.isPending}
          onClick={() => savePreference.mutate()}
        >
          Salvar preferências
        </Button>
      </Card>
    </div>
  );
}

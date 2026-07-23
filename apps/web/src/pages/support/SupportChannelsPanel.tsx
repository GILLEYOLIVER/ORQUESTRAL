import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Copy,
  KeyRound,
  MessageCircleMore,
  PauseCircle,
  Radio,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-channels.css";

type ChannelType = "email" | "chat" | "whatsapp" | "form" | "portal";
type ChannelStatus = "active" | "paused" | "revoked";

type ChannelEndpoint = {
  id: string;
  name: string;
  channel: ChannelType;
  status: ChannelStatus;
  default_priority: "low" | "normal" | "high" | "urgent";
  consent_required: boolean;
  secret_fingerprint: string;
  webhook_path: string;
  last_received_at: string | null;
  created_at: string;
};

type ChannelSecret = ChannelEndpoint & {
  webhook_secret: string;
};

const labels: Record<ChannelType, string> = {
  email: "E-mail",
  chat: "Chat",
  whatsapp: "WhatsApp",
  form: "Formulário",
  portal: "Portal",
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível configurar o canal.";
}

export function SupportChannelsPanel() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState<ChannelType>("whatsapp");
  const [consentRequired, setConsentRequired] = useState(true);
  const [revealed, setRevealed] = useState<ChannelSecret | null>(null);
  const [copied, setCopied] = useState("");

  const endpoints = useQuery({
    queryKey: ["support", "channels"],
    queryFn: () => request<ChannelEndpoint[]>("/support/channels"),
  });
  const activeCount = useMemo(
    () => endpoints.data?.filter((item) => item.status === "active").length ?? 0,
    [endpoints.data],
  );
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["support", "channels"] });
  };
  const create = useMutation({
    mutationFn: () =>
      request<ChannelSecret>("/support/channels", {
        method: "POST",
        body: {
          name,
          channel,
          consent_required: consentRequired,
          default_priority: "normal",
        },
      }),
    onSuccess: async (result) => {
      setRevealed(result);
      setName("");
      await refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({
      endpointId,
      status,
    }: {
      endpointId: string;
      status: ChannelStatus;
    }) =>
      request<ChannelEndpoint>(`/support/channels/${endpointId}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: refresh,
  });
  const rotate = useMutation({
    mutationFn: (endpointId: string) =>
      request<ChannelSecret>(
        `/support/channels/${endpointId}/rotate-secret`,
        { method: "POST" },
      ),
    onSuccess: async (result) => {
      setRevealed(result);
      await refresh();
    },
  });

  const copy = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(""), 1800);
  };
  const fullWebhookUrl = revealed
    ? `${window.location.origin}${revealed.webhook_path}`
    : "";
  const mutationError = create.error ?? update.error ?? rotate.error;

  return (
    <section className="support-channels">
      <header>
        <div>
          <span className="eyebrow">Entrada omnichannel protegida</span>
          <h2>Canais conectados</h2>
          <p>
            Transforme mensagens assinadas em chamados sem expor credenciais.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          <Radio size={17} />
          {expanded ? "Recolher canais" : "Configurar canais"}
        </Button>
      </header>

      <div className="support-channels__summary">
        <article>
          <MessageCircleMore size={19} />
          <span>Configurados</span>
          <strong>{endpoints.data?.length ?? 0}</strong>
        </article>
        <article>
          <CheckCircle2 size={19} />
          <span>Ativos</span>
          <strong>{activeCount}</strong>
        </article>
        <article>
          <ShieldCheck size={19} />
          <span>Proteção</span>
          <strong>HMAC + RLS</strong>
        </article>
      </div>

      {mutationError ? (
        <Alert variant="error">{errorMessage(mutationError)}</Alert>
      ) : null}

      {expanded ? (
        <div className="support-channels__body">
          <PermissionGuard all={["support.tickets.update"]}>
            <Card
              className="support-channels__create"
              eyebrow="Novo ponto de entrada"
            >
              <label>
                Nome do canal
                <input
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex.: WhatsApp comercial"
                  value={name}
                />
              </label>
              <label>
                Origem
                <select
                  onChange={(event) =>
                    setChannel(event.target.value as ChannelType)
                  }
                  value={channel}
                >
                  {Object.entries(labels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="support-channels__check">
                <input
                  checked={consentRequired}
                  onChange={(event) =>
                    setConsentRequired(event.target.checked)
                  }
                  type="checkbox"
                />
                Exigir confirmação de consentimento
              </label>
              <Button
                disabled={name.trim().length < 2 || create.isPending}
                onClick={() => create.mutate()}
              >
                <KeyRound size={17} />
                Gerar endpoint seguro
              </Button>
            </Card>
          </PermissionGuard>

          {revealed ? (
            <Card
              className="support-channels__secret"
              eyebrow="Copie agora"
            >
              <strong>O segredo não será exibido novamente.</strong>
              <label>
                URL assinada
                <div>
                  <code>{fullWebhookUrl}</code>
                  <button
                    aria-label="Copiar URL"
                    onClick={() => copy("url", fullWebhookUrl)}
                    type="button"
                  >
                    {copied === "url" ? (
                      <CheckCircle2 size={17} />
                    ) : (
                      <Copy size={17} />
                    )}
                  </button>
                </div>
              </label>
              <label>
                Segredo HMAC
                <div>
                  <code>{revealed.webhook_secret}</code>
                  <button
                    aria-label="Copiar segredo"
                    onClick={() =>
                      copy("secret", revealed.webhook_secret)
                    }
                    type="button"
                  >
                    {copied === "secret" ? (
                      <CheckCircle2 size={17} />
                    ) : (
                      <Copy size={17} />
                    )}
                  </button>
                </div>
              </label>
              <Button variant="secondary" onClick={() => setRevealed(null)}>
                Já guardei com segurança
              </Button>
            </Card>
          ) : null}

          <div className="support-channels__list">
            {endpoints.data?.map((endpoint) => (
              <article key={endpoint.id}>
                <div>
                  <span>{labels[endpoint.channel]}</span>
                  <strong>{endpoint.name}</strong>
                  <small>
                    Chave {endpoint.secret_fingerprint} ·{" "}
                    {endpoint.last_received_at
                      ? `última entrada ${new Date(
                          endpoint.last_received_at,
                        ).toLocaleString("pt-BR")}`
                      : "aguardando primeira entrada"}
                  </small>
                </div>
                <span data-status={endpoint.status}>
                  {endpoint.status === "active" ? "Ativo" : "Pausado"}
                </span>
                <PermissionGuard all={["support.tickets.update"]}>
                  <div className="support-channels__actions">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        update.mutate({
                          endpointId: endpoint.id,
                          status:
                            endpoint.status === "active"
                              ? "paused"
                              : "active",
                        })
                      }
                    >
                      <PauseCircle size={16} />
                      {endpoint.status === "active" ? "Pausar" : "Ativar"}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => rotate.mutate(endpoint.id)}
                    >
                      <RefreshCw size={16} />
                      Trocar segredo
                    </Button>
                  </div>
                </PermissionGuard>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

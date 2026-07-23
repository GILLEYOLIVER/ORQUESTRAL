import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useMemo, useState } from "react";

import { request } from "../lib/http";

type CdcSummary = {
  latest_sequence: number;
  retained_events: number;
  active_subscriptions: number;
  paused_subscriptions: number;
  maximum_lag: number;
};

type CdcSubscription = {
  id: string;
  name: string;
  consumer_key: string;
  status: "active" | "paused";
  operations: Array<"upserted" | "merged" | "deleted">;
  batch_size: number;
  retention_days: number;
  last_acknowledged_sequence: number;
};

type CdcEvent = {
  id: string;
  sequence_number: number;
  profile_id: string | null;
  operation: "upserted" | "merged" | "deleted";
  changed_fields: string[];
  payload_fingerprint: string;
  occurred_at: string;
};

type CdcEventPage = {
  items: CdcEvent[];
  next_sequence: number | null;
  last_acknowledged_sequence: number | null;
};

const cdcBasePath = "/crm/customer-data/cdc";

function operationLabel(operation: CdcEvent["operation"]) {
  const labels = {
    upserted: "Perfil consolidado",
    merged: "Perfis mesclados",
    deleted: "Perfil removido",
  };
  return labels[operation];
}

export function CustomerCdcPanel({ readOnly }: { readOnly: boolean }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [consumerKey, setConsumerKey] = useState("");
  const [selectedSubscription, setSelectedSubscription] = useState<string | null>(
    null,
  );

  const summaryQuery = useQuery({
    queryKey: ["customer-cdc-summary"],
    queryFn: () => request<CdcSummary>(`${cdcBasePath}/summary`),
  });
  const subscriptionsQuery = useQuery({
    queryKey: ["customer-cdc-subscriptions"],
    queryFn: () => request<CdcSubscription[]>(`${cdcBasePath}/subscriptions`),
  });
  const subscriptions = subscriptionsQuery.data ?? [];
  const activeSubscription = useMemo(
    () =>
      subscriptions.find((subscription) => subscription.id === selectedSubscription) ??
      subscriptions[0] ??
      null,
    [selectedSubscription, subscriptions],
  );
  const eventsQuery = useQuery({
    queryKey: ["customer-cdc-events", activeSubscription?.id],
    queryFn: () =>
      request<CdcEventPage>(
        activeSubscription
          ? `${cdcBasePath}/subscriptions/${activeSubscription.id}/events`
          : `${cdcBasePath}/events?limit=20`,
      ),
    enabled: activeSubscription?.status !== "paused",
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["customer-cdc-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-cdc-subscriptions"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-cdc-events"] }),
    ]);
  };

  const createMutation = useMutation({
    mutationFn: () =>
      request<CdcSubscription>(`${cdcBasePath}/subscriptions`, {
        method: "POST",
        body: {
          name,
          consumer_key: consumerKey,
          operations: ["upserted", "merged", "deleted"],
          batch_size: 50,
          retention_days: 30,
        },
      }),
    onSuccess: async (subscription) => {
      setName("");
      setConsumerKey("");
      setSelectedSubscription(subscription.id);
      await refresh();
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({
      subscription,
      action,
    }: {
      subscription: CdcSubscription;
      action: "pause" | "resume";
    }) =>
      request<CdcSubscription>(
        `${cdcBasePath}/subscriptions/${subscription.id}/${action}`,
        { method: "POST" },
      ),
    onSuccess: refresh,
  });
  const acknowledgeMutation = useMutation({
    mutationFn: ({
      subscription,
      sequence,
    }: {
      subscription: CdcSubscription;
      sequence: number;
    }) =>
      request(`${cdcBasePath}/subscriptions/${subscription.id}/acknowledge`, {
        method: "POST",
        body: { through_sequence: sequence },
      }),
    onSuccess: refresh,
  });

  const eventItems = eventsQuery.data?.items ?? [];
  const latestVisibleSequence =
    eventItems.length > 0 ? eventItems[eventItems.length - 1].sequence_number : null;

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!readOnly && name.trim() && consumerKey.trim()) {
      createMutation.mutate();
    }
  };

  return (
    <section className="customer-cdc-panel" aria-labelledby="customer-cdc-title">
      <div className="customer-cdc-heading">
        <div>
          <span className="eyebrow">SINCRONIZACAO GOVERNADA</span>
          <h2 id="customer-cdc-title">Mudancas e checkpoints</h2>
          <p>
            Acompanhe alteracoes consolidadas sem expor os dados brutos dos
            clientes.
          </p>
        </div>
        <div className="customer-cdc-metrics" aria-label="Resumo do CDC">
          <strong>{summaryQuery.data?.latest_sequence ?? 0}</strong>
          <span>ultima sequencia</span>
          <strong>{summaryQuery.data?.maximum_lag ?? 0}</strong>
          <span>maior atraso</span>
        </div>
      </div>

      <form className="customer-cdc-create" onSubmit={handleCreate}>
        <label>
          Nome do consumidor
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Painel executivo"
            minLength={2}
            maxLength={120}
            disabled={readOnly}
            required
          />
        </label>
        <label>
          Chave tecnica
          <input
            value={consumerKey}
            onChange={(event) =>
              setConsumerKey(
                event.target.value
                  .toLowerCase()
                  .replace(/[^a-z0-9._-]/g, "-")
                  .replace(/^[^a-z]+/, ""),
              )
            }
            placeholder="analytics.executivo"
            pattern="[a-z][a-z0-9._-]*"
            minLength={3}
            maxLength={80}
            disabled={readOnly}
            required
          />
        </label>
        <button type="submit" disabled={readOnly || createMutation.isPending}>
          {createMutation.isPending ? "Criando..." : "Criar assinatura"}
        </button>
      </form>

      {createMutation.isError ? (
        <p className="form-error">Nao foi possivel criar a assinatura.</p>
      ) : null}

      <div className="customer-cdc-layout">
        <div className="customer-cdc-subscriptions">
          <h3>Consumidores</h3>
          {subscriptions.length === 0 ? (
            <p className="empty-message">
              Crie uma assinatura para controlar o ponto processado.
            </p>
          ) : (
            subscriptions.map((subscription) => (
              <button
                className={`customer-cdc-subscription ${
                  activeSubscription?.id === subscription.id ? "is-selected" : ""
                }`}
                key={subscription.id}
                onClick={() => setSelectedSubscription(subscription.id)}
                type="button"
              >
                <span>
                  <strong>{subscription.name}</strong>
                  <small>{subscription.consumer_key}</small>
                </span>
                <span>
                  <b>#{subscription.last_acknowledged_sequence}</b>
                  <small>{subscription.status === "active" ? "Ativa" : "Pausada"}</small>
                </span>
              </button>
            ))
          )}
        </div>

        <div className="customer-cdc-stream">
          <div className="customer-cdc-stream-header">
            <div>
              <h3>Fluxo de mudancas</h3>
              <p>
                Somente metadados autorizados. Nenhum e-mail, telefone ou payload
                aparece aqui.
              </p>
            </div>
            {activeSubscription ? (
              <button
                type="button"
                className="secondary-button"
                disabled={readOnly || statusMutation.isPending}
                onClick={() =>
                  statusMutation.mutate({
                    subscription: activeSubscription,
                    action:
                      activeSubscription.status === "active" ? "pause" : "resume",
                  })
                }
              >
                {activeSubscription.status === "active" ? "Pausar" : "Retomar"}
              </button>
            ) : null}
          </div>

          {eventsQuery.isLoading ? <p>Carregando mudancas...</p> : null}
          {eventsQuery.isError ? (
            <p className="form-error">
              O fluxo esta indisponivel ou a assinatura esta pausada.
            </p>
          ) : null}
          <div className="customer-cdc-events">
            {eventItems.map((item) => (
              <article key={item.id}>
                <span className="customer-cdc-sequence">
                  #{item.sequence_number}
                </span>
                <div>
                  <strong>{operationLabel(item.operation)}</strong>
                  <p>{item.changed_fields.join(", ") || "sem campos publicos"}</p>
                  <small>
                    Integridade {item.payload_fingerprint} ·{" "}
                    {new Date(item.occurred_at).toLocaleString("pt-BR")}
                  </small>
                </div>
              </article>
            ))}
          </div>

          {activeSubscription && latestVisibleSequence ? (
            <button
              type="button"
              disabled={
                readOnly ||
                acknowledgeMutation.isPending ||
                latestVisibleSequence <=
                  activeSubscription.last_acknowledged_sequence
              }
              onClick={() =>
                acknowledgeMutation.mutate({
                  subscription: activeSubscription,
                  sequence: latestVisibleSequence,
                })
              }
            >
              Reconhecer ate #{latestVisibleSequence}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}


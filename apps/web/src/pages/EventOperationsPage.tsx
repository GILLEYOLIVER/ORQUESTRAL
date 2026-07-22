import { type FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiClientError, request } from "../lib/http";
import "../events/event-operations.css";

type Summary = {
  contracts: number;
  subscriptions: number;
  pending_deliveries: number;
  dead_letters: number;
  failed_outbox: number;
};
type Contract = {
  id: string;
  event_type: string;
  version: number;
  status: string;
  classification: string;
  checksum: string;
};
type Subscription = {
  id: string;
  name: string;
  consumer_name: string;
  event_type: string;
  delivery_mode: string;
  active: boolean;
};
type Delivery = {
  id: string;
  event_id: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  last_error_code: string | null;
  replay_count: number;
};
type Outbox = {
  id: string;
  event_type: string;
  event_version: number;
  status: string;
  attempt_count: number;
  last_error_code: string | null;
  causation_id: string | null;
};
type Workflow = { id: string; name: string; status: string };

const initialSchema = JSON.stringify(
  {
    type: "object",
    properties: { record_id: { type: "string" } },
    required: ["record_id"],
    additionalProperties: false,
  },
  null,
  2,
);
const errorMessage = (error: unknown) =>
  error instanceof ApiClientError
    ? error.message
    : "A operação não pode ser concluída.";

function Status({ value }: { value: string }) {
  return (
    <span
      className={`event-ops__badge ${value === "dead_letter" ? "event-ops__badge--danger" : ""}`}
    >
      {value}
    </span>
  );
}

export function EventOperationsPage() {
  const client = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [eventType, setEventType] = useState("contact.created");
  const [version, setVersion] = useState(1);
  const [classification, setClassification] = useState("internal");
  const [schemaText, setSchemaText] = useState(initialSchema);
  const [subscriptionName, setSubscriptionName] = useState(
    "Histórico comercial",
  );
  const [consumerName, setConsumerName] = useState("crm.contact-ledger");
  const [subEventType, setSubEventType] = useState("");
  const [deliveryMode, setDeliveryMode] = useState("ledger");
  const [workflowId, setWorkflowId] = useState("");

  const summary = useQuery({
    queryKey: ["event-summary"],
    queryFn: () => request<Summary>("/events/summary"),
    refetchInterval: 5000,
  });
  const contracts = useQuery({
    queryKey: ["event-contracts"],
    queryFn: () => request<Contract[]>("/events/contracts"),
  });
  const subscriptions = useQuery({
    queryKey: ["event-subscriptions"],
    queryFn: () => request<Subscription[]>("/events/subscriptions"),
  });
  const deliveries = useQuery({
    queryKey: ["event-deliveries"],
    queryFn: () => request<Delivery[]>("/events/deliveries"),
    refetchInterval: 5000,
  });
  const outbox = useQuery({
    queryKey: ["event-outbox"],
    queryFn: () => request<Outbox[]>("/events/outbox"),
    refetchInterval: 5000,
  });
  const workflows = useQuery({
    queryKey: ["workflows"],
    queryFn: () => request<Workflow[]>("/workflows"),
  });
  const publishedTypes = useMemo(
    () => [
      ...new Set(
        (contracts.data ?? [])
          .filter((item) => item.status === "published")
          .map((item) => item.event_type),
      ),
    ],
    [contracts.data],
  );

  const refresh = async () =>
    Promise.all(
      [
        "event-summary",
        "event-contracts",
        "event-subscriptions",
        "event-deliveries",
        "event-outbox",
      ].map((key) => client.invalidateQueries({ queryKey: [key] })),
    );
  const succeed = async (text: string) => {
    setFeedback(text);
    await refresh();
  };

  const createContract = useMutation({
    mutationFn: () =>
      request<Contract>("/events/contracts", {
        method: "POST",
        body: {
          event_type: eventType,
          version,
          classification,
          compatibility_mode: "backward",
          payload_schema: JSON.parse(schemaText) as Record<string, unknown>,
        },
      }),
    onSuccess: () =>
      succeed(
        "Contrato criado em rascunho. Revise e publique para iniciar a validação.",
      ),
    onError: (error) => setFeedback(errorMessage(error)),
  });
  const publish = useMutation({
    mutationFn: (id: string) =>
      request(`/events/contracts/${id}/publish`, { method: "POST" }),
    onSuccess: () =>
      succeed("Contrato publicado. Novos eventos desse tipo serão validados."),
    onError: (error) => setFeedback(errorMessage(error)),
  });
  const createSubscription = useMutation({
    mutationFn: () =>
      request<Subscription>("/events/subscriptions", {
        method: "POST",
        body: {
          name: subscriptionName,
          consumer_name: consumerName,
          event_type: subEventType || publishedTypes[0],
          min_version: 1,
          max_version: null,
          delivery_mode: deliveryMode,
          workflow_id: deliveryMode === "workflow" ? workflowId : null,
          max_attempts: 8,
        },
      }),
    onSuccess: () =>
      succeed("Assinatura criada. Cada evento será consumido uma única vez."),
    onError: (error) => setFeedback(errorMessage(error)),
  });
  const toggle = useMutation({
    mutationFn: (item: Subscription) =>
      request(`/events/subscriptions/${item.id}`, {
        method: "PATCH",
        body: { active: !item.active },
      }),
    onSuccess: refresh,
    onError: (error) => setFeedback(errorMessage(error)),
  });
  const replayDelivery = useMutation({
    mutationFn: (id: string) =>
      request(`/events/deliveries/${id}/replay`, { method: "POST" }),
    onSuccess: () =>
      succeed("Entrega recolocada na fila com a auditoria preservada."),
    onError: (error) => setFeedback(errorMessage(error)),
  });
  const replayOutbox = useMutation({
    mutationFn: (id: string) =>
      request(`/events/outbox/${id}/replay`, { method: "POST" }),
    onSuccess: () =>
      succeed("Novo evento de replay criado sem alterar o original."),
    onError: (error) => setFeedback(errorMessage(error)),
  });

  const submitContract = (event: FormEvent) => {
    event.preventDefault();
    try {
      JSON.parse(schemaText);
      createContract.mutate();
    } catch {
      setFeedback("O schema precisa ser um JSON válido.");
    }
  };
  const metrics = [
    [summary.data?.contracts ?? 0, "Contratos"],
    [summary.data?.subscriptions ?? 0, "Assinaturas"],
    [summary.data?.pending_deliveries ?? 0, "Na fila"],
    [summary.data?.dead_letters ?? 0, "DLQ de entregas"],
    [summary.data?.failed_outbox ?? 0, "Outbox com falha"],
  ] as const;

  return (
    <div className="event-ops">
      <header className="event-ops__hero">
        <span>Operação confiável</span>
        <h1>Eventos que movem a empresa.</h1>
        <p>
          Governe contratos, conecte automações, acompanhe cada entrega e
          recupere falhas sem duplicar trabalho nem perder a trilha de
          auditoria.
        </p>
      </header>
      <section className="event-ops__metrics">
        {metrics.map(([value, label]) => (
          <article className="event-ops__metric" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </article>
        ))}
      </section>
      {feedback ? <div className="event-ops__feedback">{feedback}</div> : null}
      <section className="event-ops__grid">
        <article className="event-ops__panel">
          <span className="event-ops__eyebrow">Contrato versionado</span>
          <h2>Definir um evento empresarial</h2>
          <form className="event-ops__form" onSubmit={submitContract}>
            <label>
              Tipo do evento
              <input
                value={eventType}
                onChange={(event) => setEventType(event.target.value)}
              />
            </label>
            <label>
              Versão
              <input
                min="1"
                type="number"
                value={version}
                onChange={(event) => setVersion(Number(event.target.value))}
              />
            </label>
            <label>
              Classificação
              <select
                value={classification}
                onChange={(event) => setClassification(event.target.value)}
              >
                <option value="internal">Interno</option>
                <option value="confidential">Confidencial</option>
                <option value="restricted">Restrito</option>
                <option value="public">Público</option>
              </select>
            </label>
            <label className="event-ops__full">
              Schema do payload
              <textarea
                value={schemaText}
                onChange={(event) => setSchemaText(event.target.value)}
              />
            </label>
            <button
              className="event-ops__action event-ops__full"
              disabled={createContract.isPending}
              type="submit"
            >
              Criar contrato em rascunho
            </button>
          </form>
        </article>
        <article className="event-ops__panel">
          <span className="event-ops__eyebrow">Consumidor idempotente</span>
          <h2>Assinar evento ou disparar automação</h2>
          <form
            className="event-ops__form"
            onSubmit={(event) => {
              event.preventDefault();
              createSubscription.mutate();
            }}
          >
            <label>
              Nome
              <input
                value={subscriptionName}
                onChange={(event) => setSubscriptionName(event.target.value)}
              />
            </label>
            <label>
              Identificador
              <input
                value={consumerName}
                onChange={(event) => setConsumerName(event.target.value)}
              />
            </label>
            <label>
              Evento
              <select
                value={subEventType}
                onChange={(event) => setSubEventType(event.target.value)}
              >
                <option value="">Selecione</option>
                {publishedTypes.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Destino
              <select
                value={deliveryMode}
                onChange={(event) => setDeliveryMode(event.target.value)}
              >
                <option value="ledger">Somente registrar</option>
                <option value="workflow">Executar automação</option>
              </select>
            </label>
            {deliveryMode === "workflow" ? (
              <label className="event-ops__full">
                Automação ativa
                <select
                  value={workflowId}
                  onChange={(event) => setWorkflowId(event.target.value)}
                >
                  <option value="">Selecione</option>
                  {(workflows.data ?? [])
                    .filter((item) => item.status === "active")
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                </select>
              </label>
            ) : null}
            <button
              className="event-ops__action event-ops__full"
              disabled={
                createSubscription.isPending || publishedTypes.length === 0
              }
              type="submit"
            >
              Criar assinatura
            </button>
          </form>
        </article>
        <article className="event-ops__panel event-ops__panel--wide">
          <span className="event-ops__eyebrow">Governança</span>
          <h2>Contratos e assinaturas</h2>
          <div className="event-ops__list">
            {(contracts.data ?? []).map((item) => (
              <div className="event-ops__row" key={item.id}>
                <div>
                  <strong>{item.event_type}</strong>
                  <small>{item.checksum.slice(0, 12)}...</small>
                </div>
                <span>v{item.version}</span>
                <span>{item.classification}</span>
                <Status value={item.status} />
                {item.status === "draft" ? (
                  <button
                    className="event-ops__action event-ops__action--quiet"
                    onClick={() => publish.mutate(item.id)}
                    type="button"
                  >
                    Publicar
                  </button>
                ) : (
                  <span />
                )}
              </div>
            ))}
            {(subscriptions.data ?? []).map((item) => (
              <div className="event-ops__row" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>{item.consumer_name}</small>
                </div>
                <span>{item.event_type}</span>
                <span>{item.delivery_mode}</span>
                <Status value={item.active ? "ativa" : "pausada"} />
                <button
                  className="event-ops__action event-ops__action--quiet"
                  onClick={() => toggle.mutate(item)}
                  type="button"
                >
                  {item.active ? "Pausar" : "Ativar"}
                </button>
              </div>
            ))}
          </div>
        </article>
        <article className="event-ops__panel">
          <span className="event-ops__eyebrow">Entregas</span>
          <h2>Consumo e DLQ</h2>
          <div className="event-ops__list">
            {(deliveries.data ?? []).slice(0, 25).map((item) => (
              <div className="event-ops__row" key={item.id}>
                <div>
                  <strong>{item.id.slice(0, 8)}</strong>
                  <small>{item.last_error_code ?? item.event_id}</small>
                </div>
                <span>
                  {item.attempt_count}/{item.max_attempts}
                </span>
                <span>{item.replay_count} replay</span>
                <Status value={item.status} />
                {["failed", "dead_letter"].includes(item.status) ? (
                  <button
                    className="event-ops__action event-ops__action--quiet"
                    onClick={() => replayDelivery.mutate(item.id)}
                    type="button"
                  >
                    Reprocessar
                  </button>
                ) : (
                  <span />
                )}
              </div>
            ))}
          </div>
        </article>
        <article className="event-ops__panel">
          <span className="event-ops__eyebrow">Transactional outbox</span>
          <h2>Eventos publicados</h2>
          <div className="event-ops__list">
            {(outbox.data ?? []).slice(0, 25).map((item) => (
              <div className="event-ops__row" key={item.id}>
                <div>
                  <strong>{item.event_type}</strong>
                  <small>
                    v{item.event_version} · {item.id.slice(0, 8)}
                  </small>
                </div>
                <span>{item.attempt_count} tent.</span>
                <span>{item.causation_id ? "replay" : "origem"}</span>
                <Status value={item.status} />
                {["failed", "dead_letter"].includes(item.status) ? (
                  <button
                    className="event-ops__action event-ops__action--quiet"
                    onClick={() => replayOutbox.mutate(item.id)}
                    type="button"
                  >
                    Novo replay
                  </button>
                ) : (
                  <span />
                )}
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}

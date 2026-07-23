import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CirclePause,
  CirclePlay,
  Clock3,
  DatabaseZap,
  KeyRound,
  RadioTower,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { request } from "../lib/http";
import { useSession } from "../session/context";

type SyncConnector = {
  id: string;
  source_code: string;
  source_name: string;
  transport: "push" | "pull" | "webhook";
  status: "active" | "paused";
  credential_configured: boolean;
  schedule_minutes: number;
  max_attempts: number;
  base_backoff_seconds: number;
  lease_ttl_seconds: number;
  has_cursor: boolean;
  cursor_fingerprint: string | null;
  next_run_at: string | null;
  leased_until: string | null;
  consecutive_failures: number;
};

type SyncRun = {
  id: string;
  connector_id: string;
  trigger: "manual" | "scheduled" | "webhook" | "retry";
  status: "running" | "completed" | "partial" | "failed";
  attempt: number;
  total_records: number;
  accepted_records: number;
  rejected_records: number;
  duration_ms: number | null;
  error_code: string | null;
  retry_at: string | null;
  started_at: string;
};

type SyncObservability = {
  connectors_total: number;
  connectors_active: number;
  connectors_due: number;
  connectors_leased: number;
  runs_total: number;
  runs_failed: number;
  records_processed: number;
  records_rejected: number;
  success_rate: number;
  average_duration_ms: number;
};

const emptyObservability: SyncObservability = {
  connectors_total: 0,
  connectors_active: 0,
  connectors_due: 0,
  connectors_leased: 0,
  runs_total: 0,
  runs_failed: 0,
  records_processed: 0,
  records_rejected: 0,
  success_rate: 0,
  average_duration_ms: 0,
};

function formatDate(value: string | null) {
  if (!value) return "Não agendado";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function CustomerSyncPage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const canManage =
    session.me?.permissions.includes("crm.contacts.update") ?? false;
  const [feedback, setFeedback] = useState("");
  const [form, setForm] = useState({
    source_code: "",
    source_name: "",
    transport: "push",
    schedule_minutes: 60,
    max_attempts: 5,
    base_backoff_seconds: 30,
    lease_ttl_seconds: 300,
  });

  const connectors = useQuery({
    queryKey: ["customer-sync-connectors"],
    queryFn: () =>
      request<SyncConnector[]>("/crm/customer-data/sync/connectors"),
  });
  const runs = useQuery({
    queryKey: ["customer-sync-runs"],
    queryFn: () => request<SyncRun[]>("/crm/customer-data/sync/runs?limit=30"),
  });
  const observability = useQuery({
    queryKey: ["customer-sync-observability"],
    queryFn: () =>
      request<SyncObservability>("/crm/customer-data/sync/observability"),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["customer-sync-connectors"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-sync-runs"] }),
      queryClient.invalidateQueries({
        queryKey: ["customer-sync-observability"],
      }),
    ]);
  };

  const createConnector = useMutation({
    mutationFn: () =>
      request<SyncConnector>("/crm/customer-data/sync/connectors", {
        method: "POST",
        body: JSON.stringify({ ...form, credential_binding_id: null }),
      }),
    onSuccess: async () => {
      setFeedback(
        "Conector criado com agenda segura e controle de concorrência.",
      );
      setForm((current) => ({
        ...current,
        source_code: "",
        source_name: "",
      }));
      await refresh();
    },
    onError: (error: Error) => setFeedback(error.message),
  });

  const changeStatus = useMutation({
    mutationFn: ({
      connectorId,
      action,
    }: {
      connectorId: string;
      action: "pause" | "resume";
    }) =>
      request<SyncConnector>(
        `/crm/customer-data/sync/connectors/${connectorId}/${action}`,
        { method: "POST" },
      ),
    onSuccess: async (_, variables) => {
      setFeedback(
        variables.action === "pause"
          ? "Conector pausado sem apagar histórico ou cursor."
          : "Conector retomado e marcado para a próxima execução.",
      );
      await refresh();
    },
    onError: (error: Error) => setFeedback(error.message),
  });

  const metrics = observability.data ?? emptyObservability;
  const connectorItems = connectors.data ?? [];
  const runItems = runs.data ?? [];

  return (
    <main className="customer-sync">
      <section className="customer-sync__hero">
        <div>
          <span className="eyebrow">PLATAFORMA DE DADOS</span>
          <h1>Sincronização governada</h1>
          <p>
            Agende fontes, acompanhe cursores protegidos, evite execuções
            concorrentes e trate falhas com retentativa controlada.
          </p>
        </div>
        <div className="customer-sync__hero-signal">
          <RadioTower aria-hidden="true" />
          <strong>{metrics.connectors_active}</strong>
          <span>conectores ativos</span>
        </div>
      </section>

      {feedback ? <p className="customer-sync__feedback">{feedback}</p> : null}

      <section className="customer-sync__metrics" aria-label="Indicadores">
        <article>
          <DatabaseZap />
          <span>Registros processados</span>
          <strong>{metrics.records_processed}</strong>
        </article>
        <article>
          <Activity />
          <span>Taxa de sucesso</span>
          <strong>{metrics.success_rate.toFixed(1)}%</strong>
        </article>
        <article>
          <Clock3 />
          <span>Fontes aguardando</span>
          <strong>{metrics.connectors_due}</strong>
        </article>
        <article>
          <ShieldCheck />
          <span>Execuções exclusivas</span>
          <strong>{metrics.connectors_leased}</strong>
        </article>
      </section>

      <section className="customer-sync__grid">
        <article className="customer-sync__panel">
          <div className="customer-sync__title">
            <DatabaseZap />
            <div>
              <span className="eyebrow">NOVA FONTE</span>
              <h2>Configurar conector</h2>
            </div>
          </div>
          <p>
            A interface nunca recebe senhas ou tokens. Credenciais externas são
            vinculadas somente pelo cofre seguro da API.
          </p>
          <form
            className="customer-sync__form"
            onSubmit={(event) => {
              event.preventDefault();
              createConnector.mutate();
            }}
          >
            <label>
              Código técnico
              <input
                value={form.source_code}
                pattern="[a-z][a-z0-9._-]{1,79}"
                placeholder="erp.clientes"
                required
                disabled={!canManage}
                onChange={(event) =>
                  setForm({ ...form, source_code: event.target.value })
                }
              />
            </label>
            <label>
              Nome para a equipe
              <input
                value={form.source_name}
                placeholder="Clientes do ERP"
                required
                disabled={!canManage}
                onChange={(event) =>
                  setForm({ ...form, source_name: event.target.value })
                }
              />
            </label>
            <label>
              Transporte
              <select
                value={form.transport}
                disabled={!canManage}
                onChange={(event) =>
                  setForm({ ...form, transport: event.target.value })
                }
              >
                <option value="push">Envio seguro</option>
                <option value="pull">Consulta pelo adaptador</option>
                <option value="webhook">Webhook autenticado</option>
              </select>
            </label>
            <label>
              Intervalo em minutos
              <input
                type="number"
                min={5}
                max={10080}
                value={form.schedule_minutes}
                disabled={!canManage}
                onChange={(event) =>
                  setForm({
                    ...form,
                    schedule_minutes: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Máximo de tentativas
              <input
                type="number"
                min={1}
                max={10}
                value={form.max_attempts}
                disabled={!canManage}
                onChange={(event) =>
                  setForm({
                    ...form,
                    max_attempts: Number(event.target.value),
                  })
                }
              />
            </label>
            <button
              type="submit"
              disabled={!canManage || createConnector.isPending}
              title={!canManage ? "Acesso somente leitura" : undefined}
            >
              <RadioTower />
              Criar conector
            </button>
          </form>
        </article>

        <article className="customer-sync__panel customer-sync__panel--dark">
          <div className="customer-sync__title">
            <ShieldCheck />
            <div>
              <span className="eyebrow">SEGURANÇA OPERACIONAL</span>
              <h2>O que fica protegido</h2>
            </div>
          </div>
          <ul>
            <li>
              Lease armazenado somente como SHA-256 e descartado ao concluir.
            </li>
            <li>
              Cursor exibido apenas como fingerprint, nunca em texto aberto.
            </li>
            <li>
              Credencial validada por empresa e mantida no cofre criptografado.
            </li>
            <li>Backoff exponencial reduz repetição e sobrecarga em falhas.</li>
            <li>
              RLS bloqueia leitura e escrita entre empresas no PostgreSQL.
            </li>
          </ul>
        </article>
      </section>

      <section className="customer-sync__panel">
        <div className="customer-sync__section-heading">
          <div>
            <span className="eyebrow">FONTES CADASTRADAS</span>
            <h2>Agenda e estado operacional</h2>
          </div>
          <button type="button" onClick={() => void refresh()}>
            <RefreshCw />
            Atualizar
          </button>
        </div>
        <div className="customer-sync__connectors">
          {connectorItems.length ? (
            connectorItems.map((connector) => (
              <article key={connector.id}>
                <div>
                  <strong>{connector.source_name}</strong>
                  <span>{connector.source_code}</span>
                </div>
                <span
                  className={`customer-sync__status customer-sync__status--${connector.status}`}
                >
                  {connector.status === "active" ? "ATIVO" : "PAUSADO"}
                </span>
                <dl>
                  <div>
                    <dt>Próxima janela</dt>
                    <dd>{formatDate(connector.next_run_at)}</dd>
                  </div>
                  <div>
                    <dt>Transporte</dt>
                    <dd>{connector.transport}</dd>
                  </div>
                  <div>
                    <dt>Falhas seguidas</dt>
                    <dd>{connector.consecutive_failures}</dd>
                  </div>
                  <div>
                    <dt>Cursor</dt>
                    <dd>{connector.has_cursor ? "Protegido" : "Inicial"}</dd>
                  </div>
                </dl>
                <div className="customer-sync__connector-actions">
                  <span>
                    <KeyRound />
                    {connector.credential_configured
                      ? "Cofre vinculado"
                      : "Sem credencial"}
                  </span>
                  <button
                    type="button"
                    disabled={!canManage || changeStatus.isPending}
                    title={!canManage ? "Acesso somente leitura" : undefined}
                    onClick={() =>
                      changeStatus.mutate({
                        connectorId: connector.id,
                        action:
                          connector.status === "active" ? "pause" : "resume",
                      })
                    }
                  >
                    {connector.status === "active" ? (
                      <CirclePause />
                    ) : (
                      <CirclePlay />
                    )}
                    {connector.status === "active" ? "Pausar" : "Retomar"}
                  </button>
                </div>
              </article>
            ))
          ) : (
            <p>Nenhum conector configurado para esta empresa.</p>
          )}
        </div>
      </section>

      <section className="customer-sync__panel">
        <div className="customer-sync__section-heading">
          <div>
            <span className="eyebrow">OBSERVABILIDADE</span>
            <h2>Execuções recentes</h2>
          </div>
          <span>{metrics.average_duration_ms} ms em média</span>
        </div>
        <div className="customer-sync__runs">
          {runItems.length ? (
            runItems.map((run) => (
              <article key={run.id}>
                <span
                  className={`customer-sync__status customer-sync__status--${run.status}`}
                >
                  {run.status.toUpperCase()}
                </span>
                <div>
                  <strong>{formatDate(run.started_at)}</strong>
                  <span>
                    {run.trigger} · tentativa {run.attempt}
                  </span>
                </div>
                <div>
                  <strong>{run.accepted_records}</strong>
                  <span>aceitos</span>
                </div>
                <div>
                  <strong>{run.rejected_records}</strong>
                  <span>rejeitados</span>
                </div>
                <div>
                  <strong>{run.duration_ms ?? 0} ms</strong>
                  <span>{run.error_code ?? "sem erro"}</span>
                </div>
              </article>
            ))
          ) : (
            <p>
              As execuções aparecerão aqui quando um adaptador enviar dados.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}

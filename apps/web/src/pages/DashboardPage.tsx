import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  Coins,
  Download,
  FileCheck2,
  RefreshCw,
  ShieldAlert,
  UsersRound,
  Workflow,
  XCircle,
} from "lucide-react";
import { Alert } from "@orkestral/ui-components";
import { request } from "../lib/http";
import { useSession } from "../session/context";
import { getAccessToken } from "../session/tokenStore";
import { useWorkflows } from "../workflows/useWorkflows";
import "../metrics/dashboard.css";

type DashboardMetrics = {
  period: { start: string; end: string };
  totals: {
    automation_executions: number;
    automation_success: number;
    automation_failure: number;
    time_saved_minutes: number;
    agent_uses: number;
    tokens: number;
    ai_cost_usd: number;
    integration_failures: number;
    active_users: number;
    documents_processed: number;
    pending_approvals: number;
  };
  series: Array<{
    date: string;
    automation_executions: number;
    automation_success: number;
    automation_failure: number;
    agent_uses: number;
  }>;
  top_agents: Array<{
    id: string;
    name: string;
    uses: number;
    tokens: number;
    cost_usd: number;
  }>;
  generated_at: string;
  cached: boolean;
};

type AgentOption = { id: string; name: string };

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
    value,
  );
}

export function DashboardPage() {
  const { me } = useSession();
  const workflows = useWorkflows();
  const today = useMemo(() => new Date(), []);
  const monthAgo = useMemo(
    () => new Date(today.getTime() - 29 * 86_400_000),
    [today],
  );
  const [from, setFrom] = useState(isoDate(monthAgo));
  const [to, setTo] = useState(isoDate(today));
  const [module, setModule] = useState("");
  const [agentId, setAgentId] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const canView = me?.permissions.includes("metrics.view") ?? false;
  const canExport = me?.permissions.includes("metrics.export") ?? false;

  const agents = useQuery({
    queryKey: ["dashboard-agents"],
    queryFn: () => request<AgentOption[]>("/agents"),
    enabled: canView && (me?.permissions.includes("agents.view") ?? false),
  });
  const queryString = useMemo(() => {
    const params = new URLSearchParams({ from, to });
    if (module) params.set("module", module);
    if (agentId) params.set("agent_id", agentId);
    if (workflowId) params.set("workflow_id", workflowId);
    return params.toString();
  }, [agentId, from, module, to, workflowId]);
  const metrics = useQuery({
    queryKey: ["dashboard-metrics", queryString],
    queryFn: () =>
      request<DashboardMetrics>(`/metrics/dashboard?${queryString}`, {
        timeoutMs: 30_000,
      }),
    enabled: canView,
    staleTime: 60_000,
  });

  const maxExecutions = Math.max(
    1,
    ...(metrics.data?.series.map((point) => point.automation_executions) ?? [
      1,
    ]),
  );
  const totals = metrics.data?.totals;
  const cards = totals
    ? [
        {
          icon: Workflow,
          tone: "green",
          label: "Automacoes",
          value: formatNumber(totals.automation_executions),
          detail: `${totals.automation_success} sucesso · ${totals.automation_failure} falha`,
        },
        {
          icon: Clock3,
          tone: "sun",
          label: "Tempo economizado",
          value: `${formatNumber(totals.time_saved_minutes / 60)} h`,
          detail: `${formatNumber(totals.time_saved_minutes)} minutos estimados`,
        },
        {
          icon: Bot,
          tone: "ink",
          label: "Uso de agentes",
          value: formatNumber(totals.agent_uses),
          detail: "interacoes processadas",
        },
        {
          icon: Coins,
          tone: "orange",
          label: "IA",
          value: formatNumber(totals.tokens),
          detail: `US$ ${totals.ai_cost_usd.toFixed(4)} em tokens`,
        },
        {
          icon: ShieldAlert,
          tone: totals.integration_failures ? "red" : "green",
          label: "Integracoes com falha",
          value: formatNumber(totals.integration_failures),
          detail: totals.integration_failures
            ? "requerem atencao"
            : "operacao estavel",
        },
        {
          icon: UsersRound,
          tone: "blue",
          label: "Usuarios ativos",
          value: formatNumber(totals.active_users),
          detail: "sessoes no periodo",
        },
        {
          icon: FileCheck2,
          tone: "green",
          label: "Documentos",
          value: formatNumber(totals.documents_processed),
          detail: "fontes processadas",
        },
        {
          icon: Activity,
          tone: totals.pending_approvals ? "sun" : "green",
          label: "Aprovacoes pendentes",
          value: formatNumber(totals.pending_approvals),
          detail: "decisoes humanas aguardando",
        },
      ]
    : [];

  async function download(format: "csv" | "xlsx" | "pdf") {
    setDownloadError(null);
    const token = getAccessToken();
    try {
      const response = await fetch(
        `/api/metrics/export?format=${format}&${queryString}`,
        {
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        },
      );
      if (!response.ok) throw new Error("A exportacao nao pode ser gerada.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `orkestral-metricas-${from}-${to}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error.message : "Falha na exportacao.",
      );
    }
  }

  if (!canView) {
    return (
      <Alert variant="error">
        Voce nao possui permissao para visualizar metricas.
      </Alert>
    );
  }

  return (
    <div className="metrics-dashboard">
      <header className="metrics-hero">
        <div>
          <span>Inteligência operacional</span>
          <h1>Resultados que mostram onde a operacao esta ganhando tempo.</h1>
          <p>
            {me?.current_company?.trade_name ?? "Orkestral"} · dados agregados e
            isolados por empresa.
          </p>
        </div>
        <div className="metrics-health">
          {totals && totals.automation_failure === 0 ? (
            <CheckCircle2 />
          ) : (
            <XCircle />
          )}
          <strong>
            {totals && totals.automation_executions
              ? Math.round(
                  (totals.automation_success / totals.automation_executions) *
                    100,
                )
              : 0}
            %
          </strong>
          <small>taxa de sucesso</small>
        </div>
      </header>

      <section className="metrics-filterbar">
        <label>
          De
          <input
            onChange={(event) => setFrom(event.target.value)}
            type="date"
            value={from}
          />
        </label>
        <label>
          Ate
          <input
            onChange={(event) => setTo(event.target.value)}
            type="date"
            value={to}
          />
        </label>
        <label>
          Modulo
          <select
            onChange={(event) => setModule(event.target.value)}
            value={module}
          >
            <option value="">Todos</option>
            <option value="workflows">Automacoes</option>
            <option value="agents">Agentes</option>
            <option value="integrations">Integracoes</option>
            <option value="knowledge">Conhecimento</option>
            <option value="users">Usuarios</option>
          </select>
        </label>
        <label>
          Agente
          <select
            onChange={(event) => setAgentId(event.target.value)}
            value={agentId}
          >
            <option value="">Todos</option>
            {agents.data?.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Workflow
          <select
            onChange={(event) => setWorkflowId(event.target.value)}
            value={workflowId}
          >
            <option value="">Todos</option>
            {workflows.data?.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.name}
              </option>
            ))}
          </select>
        </label>
        <button
          aria-label="Atualizar metricas"
          onClick={() => void metrics.refetch()}
          type="button"
        >
          <RefreshCw
            className={metrics.isFetching ? "metrics-spin" : ""}
            size={17}
          />
        </button>
        {canExport ? (
          <div className="metrics-export">
            <span>
              <Download size={15} /> Exportar
            </span>
            <button onClick={() => void download("csv")} type="button">
              CSV
            </button>
            <button onClick={() => void download("xlsx")} type="button">
              XLSX
            </button>
            <button onClick={() => void download("pdf")} type="button">
              PDF
            </button>
          </div>
        ) : null}
      </section>

      {metrics.isError ? (
        <Alert variant="error">Nao foi possivel carregar os indicadores.</Alert>
      ) : null}
      {downloadError ? <Alert variant="error">{downloadError}</Alert> : null}

      <section className="metrics-card-grid">
        {metrics.isLoading
          ? Array.from({ length: 8 }, (_, index) => (
              <div className="metric-card metric-card--loading" key={index} />
            ))
          : null}
        {cards.map(({ icon: Icon, tone, label, value, detail }) => (
          <article className={`metric-card metric-card--${tone}`} key={label}>
            <div>
              <Icon size={20} />
              <span>{label}</span>
            </div>
            <strong>{value}</strong>
            <small>{detail}</small>
          </article>
        ))}
      </section>

      <section className="metrics-insights">
        <article className="metrics-chart-panel">
          <div className="metrics-panel-title">
            <div>
              <span>01</span>
              <h2>Ritmo da operacao</h2>
            </div>
            <small>
              {metrics.data?.cached ? "cache Redis" : "resumo atualizado"}
            </small>
          </div>
          <div className="metrics-bars">
            {metrics.data?.series.map((point, index) => (
              <div
                key={point.date}
                title={`${point.date}: ${point.automation_executions} execucoes`}
              >
                <div>
                  <i
                    style={{
                      height: `${Math.max(3, (point.automation_success / maxExecutions) * 100)}%`,
                    }}
                  />
                  <b
                    style={{
                      height: `${(point.automation_failure / maxExecutions) * 100}%`,
                    }}
                  />
                </div>
                {index %
                  Math.max(1, Math.floor(metrics.data.series.length / 6)) ===
                0 ? (
                  <span>
                    {new Date(`${point.date}T12:00:00`).toLocaleDateString(
                      "pt-BR",
                      { day: "2-digit", month: "2-digit" },
                    )}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
          <div className="metrics-legend">
            <span>
              <i /> Sucesso
            </span>
            <span>
              <b /> Falha
            </span>
          </div>
        </article>

        <article className="metrics-agent-panel">
          <div className="metrics-panel-title">
            <div>
              <span>02</span>
              <h2>Agentes mais utilizados</h2>
            </div>
            <Bot size={19} />
          </div>
          <div className="metrics-agent-list">
            {metrics.data?.top_agents.map((agent, index) => (
              <div key={agent.id}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{agent.name}</strong>
                  <small>
                    {formatNumber(agent.tokens)} tokens · US${" "}
                    {agent.cost_usd.toFixed(4)}
                  </small>
                </div>
                <b>{agent.uses}</b>
              </div>
            ))}
            {!metrics.data?.top_agents.length ? (
              <p>Nenhum uso de agente no periodo selecionado.</p>
            ) : null}
          </div>
        </article>
      </section>

      <footer className="metrics-generated">
        Ultima agregacao:{" "}
        {metrics.data
          ? new Date(metrics.data.generated_at).toLocaleString("pt-BR")
          : "carregando"}
      </footer>
    </div>
  );
}

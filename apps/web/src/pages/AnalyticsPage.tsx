import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Gauge,
  Plus,
  Target,
} from "lucide-react";
import { Alert } from "@orkestral/ui-components";
import { request } from "../lib/http";
import { useSession } from "../session/context";
import "./analytics.css";

type Unit = "number" | "currency" | "percent" | "hours" | "days";
type Direction = "higher_better" | "lower_better" | "neutral";
type Indicator = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  category: string;
  unit: Unit;
  direction: Direction;
  target_value: string | null;
  active: boolean;
};
type Snapshot = Indicator & {
  latest_value: string | null;
  previous_value: string | null;
  change_percent: string | null;
  target_progress_percent: string | null;
  target_status: "achieved" | "behind" | "no_target" | "no_data";
  measured_at: string | null;
};
type Overview = {
  summary: {
    active_indicators: number;
    indicators_with_data: number;
    targets_achieved: number;
    targets_behind: number;
  };
  indicators: Snapshot[];
  generated_at: string;
};
type Measurement = {
  id: string;
  indicator_id: string;
  period_start: string;
  period_end: string;
  value: string;
  source: string;
  notes: string | null;
};

const unitLabels: Record<Unit, string> = {
  number: "Número",
  currency: "Moeda",
  percent: "Percentual",
  hours: "Horas",
  days: "Dias",
};

function formatValue(value: string | null, unit: Unit) {
  if (value === null) return "Sem dados";
  const numeric = Number(value);
  if (unit === "currency") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(numeric);
  }
  const formatted = new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 2,
  }).format(numeric);
  if (unit === "percent") return `${formatted}%`;
  if (unit === "hours") return `${formatted} h`;
  if (unit === "days") return `${formatted} dias`;
  return formatted;
}

export function AnalyticsPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"overview" | "indicators" | "measurements">(
    "overview",
  );
  const [selectedId, setSelectedId] = useState("");
  const canView = me?.permissions.includes("analytics.view") ?? false;
  const canManage =
    me?.permissions.includes("analytics.indicators.manage") ?? false;
  const canRecord =
    me?.permissions.includes("analytics.measurements.manage") ?? false;
  const overview = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: () => request<Overview>("/analytics/overview"),
    enabled: canView,
  });
  const indicators = useQuery({
    queryKey: ["analytics-indicators"],
    queryFn: () => request<Indicator[]>("/analytics/indicators"),
    enabled: canView,
  });
  useEffect(() => {
    if (!selectedId && indicators.data?.length)
      setSelectedId(indicators.data[0].id);
  }, [indicators.data, selectedId]);
  const measurements = useQuery({
    queryKey: ["analytics-measurements", selectedId],
    queryFn: () =>
      request<Measurement[]>(
        `/analytics/indicators/${selectedId}/measurements`,
      ),
    enabled: canView && Boolean(selectedId),
  });
  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["analytics-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics-indicators"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics-measurements"] }),
    ]);
  };
  const createIndicator = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<Indicator>("/analytics/indicators", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidate,
  });
  const createMeasurement = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<Measurement>(`/analytics/indicators/${selectedId}/measurements`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidate,
  });
  const categories = useMemo(
    () => new Set(overview.data?.indicators.map((item) => item.category)).size,
    [overview.data],
  );

  function submitIndicator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    createIndicator.mutate({
      code: data.get("code"),
      name: data.get("name"),
      category: data.get("category"),
      unit: data.get("unit"),
      direction: data.get("direction"),
      target_value: data.get("target_value") || null,
      description: data.get("description") || null,
    });
    event.currentTarget.reset();
  }

  function submitMeasurement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    createMeasurement.mutate({
      period_start: data.get("period_start"),
      period_end: data.get("period_end"),
      value: data.get("value"),
      source: data.get("source") || "manual",
      notes: data.get("notes") || null,
    });
    event.currentTarget.reset();
  }

  if (!canView)
    return <Alert variant="error">Você não possui acesso ao Analytics.</Alert>;
  const summary = overview.data?.summary;
  return (
    <div className="analytics-page">
      <header className="analytics-hero">
        <div>
          <span>Leitura estratégica</span>
          <h1>Decisões apoiadas por números que fazem sentido.</h1>
          <p>
            Metas e indicadores da{" "}
            {me?.current_company?.trade_name ?? "empresa"}, organizados em um só
            lugar.
          </p>
        </div>
        <div className="analytics-hero-score">
          <Gauge />
          <strong>{summary?.targets_achieved ?? 0}</strong>
          <small>metas alcançadas</small>
        </div>
      </header>
      <nav className="analytics-tabs" aria-label="Áreas do Analytics">
        <button
          className={tab === "overview" ? "active" : ""}
          onClick={() => setTab("overview")}
          type="button"
        >
          Painel
        </button>
        <button
          className={tab === "indicators" ? "active" : ""}
          onClick={() => setTab("indicators")}
          type="button"
        >
          Indicadores
        </button>
        <button
          className={tab === "measurements" ? "active" : ""}
          onClick={() => setTab("measurements")}
          type="button"
        >
          Lançamentos
        </button>
      </nav>
      {overview.isError || indicators.isError ? (
        <Alert variant="error">Não foi possível carregar os indicadores.</Alert>
      ) : null}
      {tab === "overview" ? (
        <>
          <section className="analytics-summary">
            <article>
              <Activity />
              <span>Indicadores ativos</span>
              <strong>{summary?.active_indicators ?? 0}</strong>
            </article>
            <article>
              <CheckCircle2 />
              <span>Com dados</span>
              <strong>{summary?.indicators_with_data ?? 0}</strong>
            </article>
            <article>
              <Target />
              <span>Metas atingidas</span>
              <strong>{summary?.targets_achieved ?? 0}</strong>
            </article>
            <article>
              <Gauge />
              <span>Categorias</span>
              <strong>{categories}</strong>
            </article>
          </section>
          <section className="analytics-grid">
            {overview.isLoading ? <p>Preparando seus indicadores...</p> : null}
            {overview.data?.indicators.map((item) => {
              const change = Number(item.change_percent ?? 0);
              const favorable =
                item.direction === "lower_better" ? change <= 0 : change >= 0;
              return (
                <article
                  className={`analytics-kpi analytics-kpi--${item.target_status}`}
                  key={item.id}
                >
                  <div className="analytics-kpi-head">
                    <span>{item.category}</span>
                    <small>
                      {item.measured_at
                        ? new Date(
                            `${item.measured_at}T12:00:00`,
                          ).toLocaleDateString("pt-BR")
                        : "aguardando medição"}
                    </small>
                  </div>
                  <h2>{item.name}</h2>
                  <strong>{formatValue(item.latest_value, item.unit)}</strong>
                  <div className="analytics-kpi-foot">
                    {item.change_percent !== null ? (
                      <span className={favorable ? "positive" : "negative"}>
                        {change >= 0 ? <ArrowUpRight /> : <ArrowDownRight />}
                        {Math.abs(change).toLocaleString("pt-BR")}%
                      </span>
                    ) : (
                      <span>Primeira medição</span>
                    )}
                    <small>
                      {item.target_value
                        ? `Meta: ${formatValue(item.target_value, item.unit)}`
                        : "Sem meta definida"}
                    </small>
                  </div>
                </article>
              );
            })}
            {!overview.isLoading && !overview.data?.indicators.length ? (
              <div className="analytics-empty">
                <Target />
                <h2>Crie seu primeiro indicador</h2>
                <p>
                  Defina o que a empresa quer acompanhar e registre resultados
                  por período.
                </p>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
      {tab === "indicators" ? (
        <section className="analytics-workspace">
          <div className="analytics-list-panel">
            <div className="analytics-section-title">
              <span>01</span>
              <div>
                <h2>Catálogo de indicadores</h2>
                <p>O que a empresa acompanha.</p>
              </div>
            </div>
            <div className="analytics-indicator-list">
              {indicators.data?.map((item) => (
                <article key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <small>
                      {item.code} · {item.category}
                    </small>
                  </div>
                  <span>{unitLabels[item.unit]}</span>
                </article>
              ))}
            </div>
          </div>
          {canManage ? (
            <form className="analytics-form" onSubmit={submitIndicator}>
              <div className="analytics-section-title">
                <Plus />
                <div>
                  <h2>Novo indicador</h2>
                  <p>Cadastre uma meta mensurável.</p>
                </div>
              </div>
              <label>
                Nome
                <input name="name" required placeholder="Ex.: Receita mensal" />
              </label>
              <div className="analytics-form-row">
                <label>
                  Código
                  <input
                    name="code"
                    required
                    pattern="[a-z0-9._-]+"
                    placeholder="receita.mensal"
                  />
                </label>
                <label>
                  Categoria
                  <input name="category" required defaultValue="Geral" />
                </label>
              </div>
              <div className="analytics-form-row">
                <label>
                  Unidade
                  <select name="unit" defaultValue="number">
                    {Object.entries(unitLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Objetivo
                  <select name="direction" defaultValue="higher_better">
                    <option value="higher_better">Quanto maior, melhor</option>
                    <option value="lower_better">Quanto menor, melhor</option>
                    <option value="neutral">Somente acompanhar</option>
                  </select>
                </label>
              </div>
              <label>
                Meta
                <input name="target_value" type="number" step="0.0001" />
              </label>
              <label>
                Descrição
                <textarea name="description" rows={3} />
              </label>
              <button disabled={createIndicator.isPending} type="submit">
                {createIndicator.isPending ? "Criando..." : "Criar indicador"}
              </button>
              {createIndicator.isError ? (
                <Alert variant="error">
                  Não foi possível criar o indicador.
                </Alert>
              ) : null}
            </form>
          ) : null}
        </section>
      ) : null}
      {tab === "measurements" ? (
        <section className="analytics-workspace">
          <div className="analytics-list-panel">
            <div className="analytics-section-title">
              <span>02</span>
              <div>
                <h2>Histórico</h2>
                <p>Resultados registrados por período.</p>
              </div>
            </div>
            <label className="analytics-select">
              Indicador
              <select
                value={selectedId}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                <option value="">Selecione</option>
                {indicators.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="analytics-measurement-list">
              {measurements.data?.map((item) => (
                <article key={item.id}>
                  <div>
                    <strong>
                      {formatValue(
                        item.value,
                        indicators.data?.find(
                          (indicator) => indicator.id === item.indicator_id,
                        )?.unit ?? "number",
                      )}
                    </strong>
                    <small>
                      {new Date(
                        `${item.period_start}T12:00:00`,
                      ).toLocaleDateString("pt-BR")}{" "}
                      até{" "}
                      {new Date(
                        `${item.period_end}T12:00:00`,
                      ).toLocaleDateString("pt-BR")}
                    </small>
                  </div>
                  <span>{item.source}</span>
                </article>
              ))}
              {selectedId &&
              !measurements.isLoading &&
              !measurements.data?.length ? (
                <p>Nenhum lançamento para este indicador.</p>
              ) : null}
            </div>
          </div>
          {canRecord && selectedId ? (
            <form className="analytics-form" onSubmit={submitMeasurement}>
              <div className="analytics-section-title">
                <Plus />
                <div>
                  <h2>Novo lançamento</h2>
                  <p>Registre o resultado do período.</p>
                </div>
              </div>
              <div className="analytics-form-row">
                <label>
                  Início
                  <input name="period_start" type="date" required />
                </label>
                <label>
                  Fim
                  <input name="period_end" type="date" required />
                </label>
              </div>
              <label>
                Valor
                <input name="value" type="number" step="0.0001" required />
              </label>
              <label>
                Origem
                <input name="source" defaultValue="manual" required />
              </label>
              <label>
                Observação
                <textarea name="notes" rows={3} />
              </label>
              <button disabled={createMeasurement.isPending} type="submit">
                {createMeasurement.isPending
                  ? "Salvando..."
                  : "Registrar resultado"}
              </button>
              {createMeasurement.isError ? (
                <Alert variant="error">
                  Não foi possível registrar o resultado.
                </Alert>
              ) : null}
            </form>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

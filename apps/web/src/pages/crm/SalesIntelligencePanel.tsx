import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChartNoAxesCombined,
  CircleCheckBig,
  Sparkles,
} from "lucide-react";
import { Alert } from "@orkestral/ui-components";
import { request } from "../../lib/http";

type HealthLevel = "healthy" | "attention" | "critical";
type ForecastCategory = "pipeline" | "best_case" | "commit";

type OpportunityInsight = {
  opportunity_id: string;
  title: string;
  amount: string;
  probability: number;
  weighted_amount: string;
  expected_close_date: string | null;
  stale_days: number;
  activity_count: number;
  health_score: number;
  health_level: HealthLevel;
  forecast_category: ForecastCategory;
  reasons: string[];
  next_best_action: string;
};

type SalesForecast = {
  generated_at: string;
  currency: string;
  opportunity_count: number;
  at_risk_count: number;
  overdue_count: number;
  total_open_amount: string;
  weighted_amount: string;
  pipeline_amount: string;
  best_case_amount: string;
  commit_amount: string;
  opportunities: OpportunityInsight[];
};

const healthLabel: Record<HealthLevel, string> = {
  healthy: "Saudável",
  attention: "Atenção",
  critical: "Crítica",
};

const forecastLabel: Record<ForecastCategory, string> = {
  pipeline: "Em desenvolvimento",
  best_case: "Melhor cenário",
  commit: "Comprometida",
};

export function SalesIntelligencePanel() {
  const forecast = useQuery({
    queryKey: ["crm-sales-intelligence"],
    queryFn: () =>
      request<SalesForecast>("/crm/sales/intelligence/forecast"),
  });
  const money = useMemo(
    () =>
      new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: forecast.data?.currency ?? "BRL",
      }),
    [forecast.data?.currency],
  );

  return (
    <details className="crm-pipeline-disclosure sales-intelligence" open>
      <summary>
        <span>Previsão e saúde comercial</span>
        <small>
          Entenda o risco, a receita provável e a próxima ação de cada negócio.
        </small>
      </summary>
      <div className="sales-intelligence__intro">
        <div>
          <h2>Previsão explicável</h2>
          <p>
            O cálculo considera probabilidade, atividade, prazo, responsável e
            situação da proposta. Nenhuma ação é executada automaticamente.
          </p>
        </div>
        <Sparkles aria-hidden="true" size={28} />
      </div>
      {forecast.isError ? (
        <Alert variant="error">
          Não foi possível calcular a previsão comercial agora.
        </Alert>
      ) : null}
      {forecast.isLoading ? <p>Calculando previsão...</p> : null}
      {forecast.data ? (
        <>
          <div className="sales-intelligence__metrics">
            <article>
              <ChartNoAxesCombined size={20} />
              <span>Funil aberto</span>
              <strong>
                {money.format(Number(forecast.data.total_open_amount))}
              </strong>
            </article>
            <article>
              <CircleCheckBig size={20} />
              <span>Receita ponderada</span>
              <strong>
                {money.format(Number(forecast.data.weighted_amount))}
              </strong>
            </article>
            <article>
              <AlertTriangle size={20} />
              <span>Exigem atenção</span>
              <strong>{forecast.data.at_risk_count}</strong>
            </article>
            <article>
              <AlertTriangle size={20} />
              <span>Datas vencidas</span>
              <strong>{forecast.data.overdue_count}</strong>
            </article>
          </div>
          <div className="sales-intelligence__forecast">
            <span>
              Em desenvolvimento
              <b>{money.format(Number(forecast.data.pipeline_amount))}</b>
            </span>
            <span>
              Melhor cenário
              <b>{money.format(Number(forecast.data.best_case_amount))}</b>
            </span>
            <span>
              Comprometida
              <b>{money.format(Number(forecast.data.commit_amount))}</b>
            </span>
          </div>
          <div className="sales-intelligence__list">
            {forecast.data.opportunities.length === 0 ? (
              <p>Nenhuma oportunidade aberta para analisar.</p>
            ) : null}
            {forecast.data.opportunities.map((item) => (
              <article key={item.opportunity_id}>
                <div className="sales-intelligence__opportunity">
                  <div>
                    <strong>{item.title}</strong>
                    <small>
                      {money.format(Number(item.amount))} ·{" "}
                      {item.probability}% de probabilidade
                    </small>
                  </div>
                  <span data-health={item.health_level}>
                    {healthLabel[item.health_level]} · {item.health_score}/100
                  </span>
                </div>
                <meter max="100" min="0" value={item.health_score} />
                <div className="sales-intelligence__details">
                  <span>
                    Previsão: {forecastLabel[item.forecast_category]}
                  </span>
                  <span>
                    Última atividade:{" "}
                    {item.activity_count === 0
                      ? "não registrada"
                      : `há ${item.stale_days} dia(s)`}
                  </span>
                </div>
                <div className="sales-intelligence__action">
                  <Sparkles size={16} />
                  <span>
                    <b>Próxima ação:</b> {item.next_best_action}
                  </span>
                </div>
                <details>
                  <summary>Por que recebeu essa avaliação?</summary>
                  <ul>
                    {item.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </details>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </details>
  );
}

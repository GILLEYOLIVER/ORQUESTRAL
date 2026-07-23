import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, MapPinned, RefreshCcw, Target } from "lucide-react";
import { Alert, Button } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import { useSession } from "../../session/context";

type Territory = {
  id: string;
  name: string;
  region_code: string | null;
  status: "active" | "inactive";
  open_opportunity_count: number;
};

type Goal = {
  id: string;
  name: string;
  metric: "revenue" | "won_opportunities" | "new_accounts";
  target_value: string;
  progress_value: string;
  progress_percent: string;
  territory_name: string | null;
  period_end: string;
  status: "draft" | "active" | "completed" | "cancelled";
};

type Renewal = {
  id: string;
  account_id: string;
  account_name: string;
  title: string;
  renewal_date: string;
  expected_amount: string;
  status: "planned" | "contacted" | "negotiating" | "renewed" | "lost";
};

type Dashboard = {
  active_territory_count: number;
  active_goal_count: number;
  open_renewal_count: number;
  renewal_pipeline_amount: string;
  territories: Territory[];
  goals: Goal[];
  renewals: Renewal[];
};

type Account = { id: string; name: string };
type Opportunity = { id: string; title: string; status: string };

const metricLabel: Record<Goal["metric"], string> = {
  revenue: "Receita ganha",
  won_opportunities: "Negócios ganhos",
  new_accounts: "Novas contas",
};

const renewalLabel: Record<Renewal["status"], string> = {
  planned: "Planejada",
  contacted: "Contato realizado",
  negotiating: "Em negociação",
  renewed: "Renovada",
  lost: "Perdida",
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function SalesGovernancePanel() {
  const queryClient = useQueryClient();
  const session = useSession();
  const readOnly = session.me?.access_mode === "read_only";
  const [error, setError] = useState<string | null>(null);
  const [territoryName, setTerritoryName] = useState("");
  const [regionCode, setRegionCode] = useState("");
  const [goalName, setGoalName] = useState("");
  const [goalMetric, setGoalMetric] = useState<Goal["metric"]>("revenue");
  const [goalTarget, setGoalTarget] = useState("");
  const [goalTerritoryId, setGoalTerritoryId] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [assignmentTerritoryId, setAssignmentTerritoryId] = useState("");
  const [renewalAccountId, setRenewalAccountId] = useState("");
  const [renewalTitle, setRenewalTitle] = useState("");
  const [renewalDate, setRenewalDate] = useState("");
  const [renewalAmount, setRenewalAmount] = useState("");
  const year = new Date().getFullYear();

  const dashboard = useQuery({
    queryKey: ["crm-sales-governance"],
    queryFn: () =>
      request<Dashboard>("/crm/sales/governance/dashboard"),
  });
  const accounts = useQuery({
    queryKey: ["crm-sales-accounts"],
    queryFn: () => request<Account[]>("/crm/sales/accounts"),
  });
  const opportunities = useQuery({
    queryKey: ["crm-opportunities"],
    queryFn: () => request<Opportunity[]>("/crm/opportunities"),
  });
  const money = useMemo(
    () =>
      new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
      }),
    [],
  );
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["crm-sales-governance"] });

  const createTerritory = useMutation({
    mutationFn: () =>
      request("/crm/sales/governance/territories", {
        method: "POST",
        body: {
          name: territoryName,
          region_code: regionCode || null,
        },
      }),
    onSuccess: async () => {
      setTerritoryName("");
      setRegionCode("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar o território.")),
  });

  const createGoal = useMutation({
    mutationFn: () =>
      request("/crm/sales/governance/goals", {
        method: "POST",
        body: {
          name: goalName,
          metric: goalMetric,
          period_start: `${year}-01-01`,
          period_end: `${year}-12-31`,
          target_value: Number(goalTarget),
          territory_id:
            goalMetric === "new_accounts" || !goalTerritoryId
              ? null
              : goalTerritoryId,
        },
      }),
    onSuccess: async () => {
      setGoalName("");
      setGoalTarget("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a meta.")),
  });

  const assignTerritory = useMutation({
    mutationFn: () =>
      request(
        `/crm/sales/governance/opportunities/${opportunityId}/territory`,
        {
          method: "PUT",
          body: { territory_id: assignmentTerritoryId || null },
        },
      ),
    onSuccess: async () => {
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(
        errorMessage(caught, "Não foi possível atribuir o território."),
      ),
  });

  const createRenewal = useMutation({
    mutationFn: () =>
      request("/crm/sales/governance/renewals", {
        method: "POST",
        body: {
          account_id: renewalAccountId,
          title: renewalTitle,
          renewal_date: renewalDate,
          expected_amount: Number(renewalAmount || 0),
        },
      }),
    onSuccess: async () => {
      setRenewalTitle("");
      setRenewalDate("");
      setRenewalAmount("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a renovação.")),
  });

  const updateRenewal = useMutation({
    mutationFn: ({
      renewal,
      status,
    }: {
      renewal: Renewal;
      status: Renewal["status"];
    }) =>
      request(`/crm/sales/governance/renewals/${renewal.id}/status`, {
        method: "POST",
        body: {
          status,
          note: `Situação alterada para ${renewalLabel[status]}.`,
        },
      }),
    onSuccess: refresh,
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível avançar a renovação.")),
  });

  const nextRenewalStatus = (status: Renewal["status"]) => {
    if (status === "planned") return "contacted";
    if (status === "contacted") return "negotiating";
    if (status === "negotiating") return "renewed";
    return null;
  };

  return (
    <details className="crm-pipeline-disclosure sales-governance" open>
      <summary>
        <span>Metas, territórios e renovações</span>
        <small>
          Organize a cobertura comercial e acompanhe crescimento recorrente.
        </small>
      </summary>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="sales-governance__metrics">
        <article>
          <MapPinned size={20} />
          <strong>{dashboard.data?.active_territory_count ?? 0}</strong>
          <span>territórios ativos</span>
        </article>
        <article>
          <Target size={20} />
          <strong>{dashboard.data?.active_goal_count ?? 0}</strong>
          <span>metas acompanhadas</span>
        </article>
        <article>
          <RefreshCcw size={20} />
          <strong>{dashboard.data?.open_renewal_count ?? 0}</strong>
          <span>renovações abertas</span>
        </article>
        <article>
          <Flag size={20} />
          <strong>
            {money.format(
              Number(dashboard.data?.renewal_pipeline_amount ?? 0),
            )}
          </strong>
          <span>receita em renovação</span>
        </article>
      </div>
      <div className="sales-governance__forms">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createTerritory.mutate();
          }}
        >
          <strong>Novo território</strong>
          <label>
            Nome
            <input
              disabled={readOnly}
              onChange={(event) => setTerritoryName(event.target.value)}
              placeholder="Ex.: Sudeste"
              value={territoryName}
            />
          </label>
          <label>
            Código da região
            <input
              disabled={readOnly}
              onChange={(event) => setRegionCode(event.target.value)}
              placeholder="Ex.: BR-SE"
              value={regionCode}
            />
          </label>
          <Button
            disabled={readOnly || territoryName.trim().length < 2}
            loading={createTerritory.isPending}
            type="submit"
          >
            Criar território
          </Button>
        </form>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createGoal.mutate();
          }}
        >
          <strong>Nova meta anual</strong>
          <label>
            Nome
            <input
              disabled={readOnly}
              onChange={(event) => setGoalName(event.target.value)}
              value={goalName}
            />
          </label>
          <label>
            Indicador
            <select
              disabled={readOnly}
              onChange={(event) =>
                setGoalMetric(event.target.value as Goal["metric"])
              }
              value={goalMetric}
            >
              {Object.entries(metricLabel).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Valor-alvo
            <input
              disabled={readOnly}
              min="0.01"
              onChange={(event) => setGoalTarget(event.target.value)}
              step="0.01"
              type="number"
              value={goalTarget}
            />
          </label>
          <label>
            Território
            <select
              disabled={readOnly || goalMetric === "new_accounts"}
              onChange={(event) => setGoalTerritoryId(event.target.value)}
              value={goalTerritoryId}
            >
              <option value="">Empresa inteira</option>
              {dashboard.data?.territories.map((territory) => (
                <option key={territory.id} value={territory.id}>
                  {territory.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            disabled={
              readOnly ||
              goalName.trim().length < 2 ||
              Number(goalTarget) <= 0
            }
            loading={createGoal.isPending}
            type="submit"
          >
            Criar meta
          </Button>
        </form>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            assignTerritory.mutate();
          }}
        >
          <strong>Atribuir oportunidade</strong>
          <label>
            Oportunidade
            <select
              disabled={readOnly}
              onChange={(event) => setOpportunityId(event.target.value)}
              value={opportunityId}
            >
              <option value="">Selecione</option>
              {opportunities.data?.map((opportunity) => (
                <option key={opportunity.id} value={opportunity.id}>
                  {opportunity.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Território
            <select
              disabled={readOnly}
              onChange={(event) =>
                setAssignmentTerritoryId(event.target.value)
              }
              value={assignmentTerritoryId}
            >
              <option value="">Sem território</option>
              {dashboard.data?.territories.map((territory) => (
                <option key={territory.id} value={territory.id}>
                  {territory.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            disabled={readOnly || !opportunityId}
            loading={assignTerritory.isPending}
            type="submit"
          >
            Salvar atribuição
          </Button>
        </form>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createRenewal.mutate();
          }}
        >
          <strong>Planejar renovação</strong>
          <label>
            Conta
            <select
              disabled={readOnly}
              onChange={(event) => setRenewalAccountId(event.target.value)}
              value={renewalAccountId}
            >
              <option value="">Selecione</option>
              {accounts.data?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Título
            <input
              disabled={readOnly}
              onChange={(event) => setRenewalTitle(event.target.value)}
              value={renewalTitle}
            />
          </label>
          <label>
            Data da renovação
            <input
              disabled={readOnly}
              onChange={(event) => setRenewalDate(event.target.value)}
              type="date"
              value={renewalDate}
            />
          </label>
          <label>
            Valor esperado
            <input
              disabled={readOnly}
              min="0"
              onChange={(event) => setRenewalAmount(event.target.value)}
              step="0.01"
              type="number"
              value={renewalAmount}
            />
          </label>
          <Button
            disabled={
              readOnly ||
              !renewalAccountId ||
              renewalTitle.trim().length < 2 ||
              !renewalDate
            }
            loading={createRenewal.isPending}
            type="submit"
          >
            Criar renovação
          </Button>
        </form>
      </div>
      <div className="sales-governance__boards">
        <section>
          <strong>Progresso das metas</strong>
          {dashboard.data?.goals.length === 0 ? (
            <p>Nenhuma meta cadastrada.</p>
          ) : null}
          {dashboard.data?.goals.map((goal) => (
            <article key={goal.id}>
              <div>
                <strong>{goal.name}</strong>
                <small>
                  {metricLabel[goal.metric]} ·{" "}
                  {goal.territory_name ?? "Empresa inteira"}
                </small>
              </div>
              <meter
                max="100"
                min="0"
                value={Math.min(Number(goal.progress_percent), 100)}
              />
              <span>
                {goal.metric === "revenue"
                  ? money.format(Number(goal.progress_value))
                  : Number(goal.progress_value).toLocaleString("pt-BR")}{" "}
                de{" "}
                {goal.metric === "revenue"
                  ? money.format(Number(goal.target_value))
                  : Number(goal.target_value).toLocaleString("pt-BR")}
              </span>
            </article>
          ))}
        </section>
        <section>
          <strong>Carteira de renovações</strong>
          {dashboard.data?.renewals.length === 0 ? (
            <p>Nenhuma renovação planejada.</p>
          ) : null}
          {dashboard.data?.renewals.map((renewal) => {
            const next = nextRenewalStatus(renewal.status);
            return (
              <article key={renewal.id}>
                <div>
                  <strong>{renewal.title}</strong>
                  <small>
                    {renewal.account_name} ·{" "}
                    {new Date(
                      `${renewal.renewal_date}T12:00:00`,
                    ).toLocaleDateString("pt-BR")}
                  </small>
                </div>
                <b>{money.format(Number(renewal.expected_amount))}</b>
                <span>{renewalLabel[renewal.status]}</span>
                {next ? (
                  <Button
                    disabled={readOnly}
                    onClick={() =>
                      updateRenewal.mutate({ renewal, status: next })
                    }
                    variant="secondary"
                  >
                    Avançar para {renewalLabel[next]}
                  </Button>
                ) : null}
              </article>
            );
          })}
        </section>
      </div>
    </details>
  );
}

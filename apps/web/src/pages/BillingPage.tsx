import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  CreditCard,
  Gauge,
  Plus,
  ShieldCheck,
} from "lucide-react";
import type { CompanyResponse } from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import {
  type PlanResponse,
  type UsageMetric,
  useBillingOverview,
  usePlans,
} from "../billing/useBilling";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import "../billing/billing.css";

const metricLabels: Record<UsageMetric, string> = {
  users: "Usuários",
  agents: "Agentes",
  workflows: "Automações",
  workflow_executions: "Execuções mensais",
  tokens: "Tokens mensais",
  storage_bytes: "Armazenamento em bytes",
  integrations: "Integrações",
  documents: "Documentos",
  api_calls: "Chamadas de API",
};

const metrics = Object.keys(metricLabels) as UsageMetric[];
const emptyLimits = Object.fromEntries(
  metrics.map((metric) => [metric, ""]),
) as Record<UsageMetric, string>;

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

function formatUsage(metric: UsageMetric, amount: number) {
  if (metric === "storage_bytes") {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = amount;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value)} ${units[unit]}`;
  }
  return new Intl.NumberFormat("pt-BR").format(amount);
}

function currency(value: string) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

export function BillingPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const overview = useBillingOverview();
  const plans = usePlans();
  const isPlatformAdmin = me?.user.is_platform_admin ?? false;
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [cycle, setCycle] = useState<"monthly" | "yearly">("monthly");
  const [limits, setLimits] =
    useState<Record<UsageMetric, string>>(emptyLimits);
  const [companyId, setCompanyId] = useState("");
  const [planId, setPlanId] = useState("");

  const companies = useQuery({
    queryKey: ["companies", "billing"],
    queryFn: () => request<CompanyResponse[]>("/companies"),
    enabled: isPlatformAdmin,
  });

  const activePlans = useMemo(
    () => plans.data?.filter((plan) => plan.status === "active") ?? [],
    [plans.data],
  );

  const createPlan = useMutation({
    mutationFn: () => {
      const configuredLimits = Object.fromEntries(
        metrics
          .filter((metric) => limits[metric].trim() !== "")
          .map((metric) => [metric, Number.parseInt(limits[metric], 10)]),
      );
      return request<PlanResponse>("/billing/plans", {
        method: "POST",
        body: {
          name,
          description: description || null,
          price,
          billing_cycle: cycle,
          limits: configuredLimits,
          status: "active",
        },
      });
    },
    onSuccess: async () => {
      setName("");
      setDescription("");
      setPrice("");
      setLimits(emptyLimits);
      setError(null);
      setFeedback("Plano criado e disponível para atribuição.");
      await queryClient.invalidateQueries({ queryKey: ["billing-plans"] });
    },
    onError: (caught) => {
      setFeedback(null);
      setError(errorMessage(caught, "Não foi possível criar o plano."));
    },
  });

  const assignPlan = useMutation({
    mutationFn: () =>
      request(`/billing/companies/${companyId}/subscription`, {
        method: "PUT",
        body: { plan_id: planId, status: "active" },
      }),
    onSuccess: async () => {
      setError(null);
      setFeedback("Assinatura atribuída à empresa com sucesso.");
      await queryClient.invalidateQueries({ queryKey: ["billing-overview"] });
    },
    onError: (caught) => {
      setFeedback(null);
      setError(errorMessage(caught, "Não foi possível atribuir a assinatura."));
    },
  });

  return (
    <div className="billing-page">
      <header className="billing-hero">
        <div>
          <span className="eyebrow">Capacidade comercial</span>
          <h1>Plano e consumo</h1>
          <p>
            Acompanhe recursos contratados, saldo disponível e o período atual
            em um só lugar.
          </p>
        </div>
        <div className="billing-hero__seal">
          <ShieldCheck size={22} />
          <span>
            Limites validados
            <strong>no servidor</strong>
          </span>
        </div>
      </header>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {feedback ? <Alert>{feedback}</Alert> : null}

      {overview.isLoading ? <p>Calculando consumo atual…</p> : null}
      {overview.isError ? (
        <Alert variant="error">Não foi possível carregar o faturamento.</Alert>
      ) : null}

      {overview.data?.subscription ? (
        <section className="billing-plan-banner">
          <div className="billing-plan-banner__icon">
            <CreditCard size={25} />
          </div>
          <div>
            <span>Plano atual</span>
            <h2>{overview.data.subscription.plan.name}</h2>
            <p>
              {overview.data.subscription.plan.description ??
                "Plano ativo da empresa."}
            </p>
          </div>
          <div className="billing-plan-banner__price">
            <strong>{currency(overview.data.subscription.plan.price)}</strong>
            <span>
              /
              {overview.data.subscription.plan.billing_cycle === "monthly"
                ? "mês"
                : "ano"}
            </span>
          </div>
          <div className="billing-plan-banner__period">
            <span>Próxima renovação</span>
            <strong>
              {new Intl.DateTimeFormat("pt-BR").format(
                new Date(overview.data.subscription.current_period_end),
              )}
            </strong>
          </div>
        </section>
      ) : (
        <Card className="billing-empty" eyebrow="Assinatura">
          <Gauge size={30} />
          <h2>Nenhum plano atribuído</h2>
          <p>
            {overview.data?.enforcement_enabled
              ? "As operações comerciais ficam bloqueadas até a atribuição de um plano."
              : "A fiscalização de limites não está ativa neste ambiente."}
          </p>
        </Card>
      )}

      {overview.data?.limits.length ? (
        <section
          className="billing-usage-grid"
          aria-label="Consumo por recurso"
        >
          {overview.data.limits.map((item) => (
            <article className="billing-usage-card" key={item.metric}>
              <div className="billing-usage-card__heading">
                <span>{item.label}</span>
                {item.exceeded ? (
                  <strong className="billing-usage-card__danger">
                    Limite excedido
                  </strong>
                ) : (
                  <CheckCircle2 size={17} />
                )}
              </div>
              <strong className="billing-usage-card__value">
                {formatUsage(item.metric, item.used)}
                <small>
                  {item.limit === null
                    ? " sem limite"
                    : ` de ${formatUsage(item.metric, item.limit)}`}
                </small>
              </strong>
              <div className="billing-meter" aria-hidden="true">
                <span style={{ width: `${item.percentage ?? 0}%` }} />
              </div>
              <p>
                {item.remaining === null
                  ? "Uso ilimitado neste plano"
                  : `${formatUsage(item.metric, item.remaining)} disponíveis`}
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {isPlatformAdmin ? (
        <section className="billing-admin-section">
          <div className="dashboard__heading">
            <div>
              <span className="eyebrow">Administração da plataforma</span>
              <h2>Catálogo comercial</h2>
              <p>Crie planos reais e atribua-os às empresas cadastradas.</p>
            </div>
          </div>
          <div className="billing-admin-grid">
            <Card eyebrow="Novo plano">
              <form
                className="stack-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  createPlan.mutate();
                }}
              >
                <TextField
                  label="Nome do plano"
                  onChange={(event) => setName(event.target.value)}
                  required
                  value={name}
                />
                <TextField
                  label="Descrição"
                  onChange={(event) => setDescription(event.target.value)}
                  value={description}
                />
                <TextField
                  label="Preço em reais"
                  min="0"
                  onChange={(event) => setPrice(event.target.value)}
                  required
                  step="0.01"
                  type="number"
                  value={price}
                />
                <label className="native-field">
                  <span>Ciclo</span>
                  <select
                    onChange={(event) =>
                      setCycle(event.target.value as "monthly" | "yearly")
                    }
                    value={cycle}
                  >
                    <option value="monthly">Mensal</option>
                    <option value="yearly">Anual</option>
                  </select>
                </label>
                <fieldset className="billing-limit-fields">
                  <legend>Limites, deixe vazio para ilimitado</legend>
                  {metrics.map((metric) => (
                    <label key={metric}>
                      <span>{metricLabels[metric]}</span>
                      <input
                        min="1"
                        onChange={(event) =>
                          setLimits((current) => ({
                            ...current,
                            [metric]: event.target.value,
                          }))
                        }
                        type="number"
                        value={limits[metric]}
                      />
                    </label>
                  ))}
                </fieldset>
                <Button loading={createPlan.isPending} type="submit">
                  <Plus size={17} /> Criar plano
                </Button>
              </form>
            </Card>

            <div className="billing-admin-stack">
              <Card eyebrow="Atribuir assinatura">
                <form
                  className="stack-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    assignPlan.mutate();
                  }}
                >
                  <label className="native-field">
                    <span>Empresa</span>
                    <select
                      onChange={(event) => setCompanyId(event.target.value)}
                      required
                      value={companyId}
                    >
                      <option value="">Selecione</option>
                      {companies.data?.map((company) => (
                        <option key={company.id} value={company.id}>
                          {company.trade_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="native-field">
                    <span>Plano</span>
                    <select
                      onChange={(event) => setPlanId(event.target.value)}
                      required
                      value={planId}
                    >
                      <option value="">Selecione</option>
                      {activePlans.map((plan) => (
                        <option key={plan.id} value={plan.id}>
                          {plan.name} · {currency(plan.price)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button loading={assignPlan.isPending} type="submit">
                    Atribuir à empresa
                  </Button>
                </form>
              </Card>

              <Card eyebrow="Planos cadastrados">
                <div className="billing-plan-list">
                  {plans.data?.map((plan) => (
                    <article key={plan.id}>
                      <div>
                        <strong>{plan.name}</strong>
                        <span>{plan.description ?? "Sem descrição"}</span>
                      </div>
                      <strong>{currency(plan.price)}</strong>
                      <span
                        className={`status-chip status-chip--${plan.status}`}
                      >
                        {plan.status}
                      </span>
                    </article>
                  ))}
                  {!plans.isLoading && !plans.data?.length ? (
                    <p>Nenhum plano cadastrado.</p>
                  ) : null}
                </div>
              </Card>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

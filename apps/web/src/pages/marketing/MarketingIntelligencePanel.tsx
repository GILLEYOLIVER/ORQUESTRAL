import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeDollarSign,
  BarChart3,
  FlaskConical,
  Link2,
  MousePointerClick,
  Percent,
  Plus,
  TrendingUp,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { ApiClientError, request } from "../../lib/http";

export type MarketingCampaignOption = {
  id: string;
  name: string;
};

type Performance = {
  campaign_id: string | null;
  impressions: number;
  reach: number;
  clicks: number;
  leads: number;
  conversions: number;
  spend_cents: number;
  revenue_cents: number;
  click_rate: number;
  lead_rate: number;
  conversion_rate: number;
  cost_per_lead_cents: number;
  acquisition_cost_cents: number;
  roas: number;
};

type Experiment = {
  id: string;
  campaign_id: string;
  name: string;
  hypothesis: string;
  success_metric: "click_rate" | "lead_rate" | "conversion_rate" | "revenue";
  status: "draft" | "running" | "completed" | "cancelled";
  variants: Array<{ key: string; name: string; description?: string }>;
  winner_key: string | null;
};

type Attribution = {
  id: string;
  contact_id: string | null;
  opportunity_id: string | null;
  touchpoint: string;
  source: string | null;
  medium: string | null;
  value_cents: number;
  occurred_at: string;
};

type ContactPage = {
  items: Array<{ id: string; name: string; company_name: string | null }>;
};

type Opportunity = {
  id: string;
  title: string;
  amount: string;
  contact_name: string | null;
  status: string;
};

function currency(cents: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

function message(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir esta operação.";
}

export function MarketingIntelligencePanel({
  campaigns,
  canUpdate,
}: {
  campaigns: MarketingCampaignOption[];
  canUpdate: boolean;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [view, setView] = useState<"metrics" | "experiments" | "attribution">(
    "metrics",
  );
  const [campaignId, setCampaignId] = useState("");
  const selectedCampaignId = campaignId || campaigns[0]?.id || "";
  const [metricDate, setMetricDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [impressions, setImpressions] = useState("");
  const [clicks, setClicks] = useState("");
  const [leads, setLeads] = useState("");
  const [conversions, setConversions] = useState("");
  const [spend, setSpend] = useState("");
  const [revenue, setRevenue] = useState("");
  const [experimentName, setExperimentName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [metric, setMetric] =
    useState<Experiment["success_metric"]>("conversion_rate");
  const [variantA, setVariantA] = useState("Mensagem direta");
  const [variantB, setVariantB] = useState("Mensagem consultiva");
  const [contactId, setContactId] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [touchpoint, setTouchpoint] = useState("conversion");
  const [source, setSource] = useState("");
  const [medium, setMedium] = useState("");
  const [attributedValue, setAttributedValue] = useState("");

  const overall = useQuery({
    queryKey: ["marketing", "performance", "overall"],
    queryFn: () => request<Performance>("/marketing/performance"),
  });
  const campaignPerformance = useQuery({
    queryKey: ["marketing", "performance", selectedCampaignId],
    queryFn: () =>
      request<Performance>(
        `/marketing/campaigns/${selectedCampaignId}/performance`,
      ),
    enabled: Boolean(selectedCampaignId),
  });
  const experiments = useQuery({
    queryKey: ["marketing", "experiments", selectedCampaignId],
    queryFn: () =>
      request<Experiment[]>(
        `/marketing/experiments?campaign_id=${selectedCampaignId}`,
      ),
    enabled: expanded && Boolean(selectedCampaignId),
  });
  const attributions = useQuery({
    queryKey: ["marketing", "attributions", selectedCampaignId],
    queryFn: () =>
      request<Attribution[]>(
        `/marketing/campaigns/${selectedCampaignId}/attributions`,
      ),
    enabled: expanded && Boolean(selectedCampaignId),
  });
  const contacts = useQuery({
    queryKey: ["marketing", "attribution-contacts"],
    queryFn: () => request<ContactPage>("/crm/contacts?page_size=100"),
    enabled: expanded && view === "attribution",
    retry: false,
  });
  const opportunities = useQuery({
    queryKey: ["marketing", "attribution-opportunities"],
    queryFn: () => request<Opportunity[]>("/crm/opportunities"),
    enabled: expanded && view === "attribution",
    retry: false,
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["marketing", "performance"] }),
      queryClient.invalidateQueries({ queryKey: ["marketing", "campaigns"] }),
      queryClient.invalidateQueries({ queryKey: ["marketing", "summary"] }),
    ]);
  };

  const recordMetric = useMutation({
    mutationFn: () =>
      request(`/marketing/campaigns/${selectedCampaignId}/metrics`, {
        method: "POST",
        body: {
          observed_on: metricDate,
          channel: "multi_channel",
          variant_key: "all",
          impressions: Number(impressions || 0),
          reach: Number(impressions || 0),
          clicks: Number(clicks || 0),
          leads: Number(leads || 0),
          conversions: Number(conversions || 0),
          spend_cents: Math.round(Number(spend || 0) * 100),
          revenue_cents: Math.round(Number(revenue || 0) * 100),
        },
      }),
    onSuccess: async () => {
      setImpressions("");
      setClicks("");
      setLeads("");
      setConversions("");
      setSpend("");
      setRevenue("");
      await refresh();
    },
  });

  const createExperiment = useMutation({
    mutationFn: () =>
      request<Experiment>("/marketing/experiments", {
        method: "POST",
        body: {
          campaign_id: selectedCampaignId,
          name: experimentName,
          hypothesis,
          success_metric: metric,
          variants: [
            { key: "A", name: variantA },
            { key: "B", name: variantB },
          ],
        },
      }),
    onSuccess: async () => {
      setExperimentName("");
      setHypothesis("");
      await queryClient.invalidateQueries({
        queryKey: ["marketing", "experiments", selectedCampaignId],
      });
    },
  });

  const updateExperiment = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      request<Experiment>(`/marketing/experiments/${id}`, {
        method: "PATCH",
        body,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["marketing", "experiments", selectedCampaignId],
      });
    },
  });

  const createAttribution = useMutation({
    mutationFn: () =>
      request<Attribution>(
        `/marketing/campaigns/${selectedCampaignId}/attributions`,
        {
          method: "POST",
          body: {
            contact_id: contactId || null,
            opportunity_id: opportunityId || null,
            touchpoint,
            source: source || null,
            medium: medium || null,
            value_cents: Math.round(Number(attributedValue || 0) * 100),
            metadata_json: { recorded_from: "marketing_intelligence_panel" },
          },
        },
      ),
    onSuccess: async () => {
      setAttributedValue("");
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["marketing", "attributions", selectedCampaignId],
        }),
        queryClient.invalidateQueries({ queryKey: ["marketing", "campaigns"] }),
        queryClient.invalidateQueries({ queryKey: ["marketing", "summary"] }),
      ]);
    },
  });

  const performance = campaignPerformance.data ?? overall.data;
  const attributedRevenue = useMemo(
    () =>
      attributions.data?.reduce((total, item) => total + item.value_cents, 0) ??
      0,
    [attributions.data],
  );
  const activeError =
    recordMetric.error ||
    createExperiment.error ||
    updateExperiment.error ||
    createAttribution.error;

  return (
    <section className="marketing-intelligence">
      <header>
        <div>
          <span className="eyebrow">Inteligência de crescimento</span>
          <h2>Da atenção até a receita</h2>
          <p>
            Compare investimento, aquisição e retorno sem perder a origem de
            cada negócio.
          </p>
        </div>
        <Button
          onClick={() => setExpanded((value) => !value)}
          variant="secondary"
        >
          <BarChart3 size={17} />{" "}
          {expanded ? "Recolher painel" : "Abrir painel completo"}
        </Button>
      </header>

      <div className="marketing-performance-strip">
        <article>
          <MousePointerClick size={19} />
          <span>CTR</span>
          <strong>{performance?.click_rate ?? 0}%</strong>
        </article>
        <article>
          <Percent size={19} />
          <span>Conversão</span>
          <strong>{performance?.conversion_rate ?? 0}%</strong>
        </article>
        <article>
          <BadgeDollarSign size={19} />
          <span>Custo por lead</span>
          <strong>{currency(performance?.cost_per_lead_cents ?? 0)}</strong>
        </article>
        <article>
          <TrendingUp size={19} />
          <span>ROAS</span>
          <strong>{performance?.roas ?? 0}x</strong>
        </article>
      </div>

      {expanded ? (
        <div className="marketing-intelligence-body">
          <div className="marketing-intelligence-controls">
            <label>
              Campanha analisada
              <select
                value={selectedCampaignId}
                onChange={(event) => setCampaignId(event.target.value)}
              >
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </label>
            <nav>
              <button
                className={view === "metrics" ? "active" : ""}
                onClick={() => setView("metrics")}
              >
                <BarChart3 size={15} /> Métricas
              </button>
              <button
                className={view === "experiments" ? "active" : ""}
                onClick={() => setView("experiments")}
              >
                <FlaskConical size={15} /> Experimentos
              </button>
              <button
                className={view === "attribution" ? "active" : ""}
                onClick={() => setView("attribution")}
              >
                <Link2 size={15} /> Atribuição
              </button>
            </nav>
          </div>

          {activeError ? (
            <Alert variant="error">{message(activeError)}</Alert>
          ) : null}
          {!selectedCampaignId ? (
            <Alert variant="info">
              Crie uma campanha para começar a medir resultados.
            </Alert>
          ) : null}

          {view === "metrics" && selectedCampaignId ? (
            <Card
              className="marketing-deep-form"
              eyebrow="Registro consolidado"
            >
              <h3>Adicionar desempenho do período</h3>
              <p>
                Use dados do provedor de anúncios, e-mail, WhatsApp ou outra
                fonte conectada.
              </p>
              <div className="marketing-deep-grid">
                <label>
                  Data
                  <input
                    type="date"
                    value={metricDate}
                    onChange={(event) => setMetricDate(event.target.value)}
                  />
                </label>
                <label>
                  Impressões
                  <input
                    type="number"
                    min="0"
                    value={impressions}
                    onChange={(event) => setImpressions(event.target.value)}
                  />
                </label>
                <label>
                  Cliques
                  <input
                    type="number"
                    min="0"
                    value={clicks}
                    onChange={(event) => setClicks(event.target.value)}
                  />
                </label>
                <label>
                  Leads
                  <input
                    type="number"
                    min="0"
                    value={leads}
                    onChange={(event) => setLeads(event.target.value)}
                  />
                </label>
                <label>
                  Conversões
                  <input
                    type="number"
                    min="0"
                    value={conversions}
                    onChange={(event) => setConversions(event.target.value)}
                  />
                </label>
                <label>
                  Investimento em R$
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={spend}
                    onChange={(event) => setSpend(event.target.value)}
                  />
                </label>
                <label>
                  Receita em R$
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={revenue}
                    onChange={(event) => setRevenue(event.target.value)}
                  />
                </label>
              </div>
              {canUpdate ? (
                <Button
                  onClick={() => recordMetric.mutate()}
                  loading={recordMetric.isPending}
                >
                  Salvar e recalcular
                </Button>
              ) : null}
            </Card>
          ) : null}

          {view === "experiments" && selectedCampaignId ? (
            <div className="marketing-experiment-layout">
              {canUpdate ? (
                <Card
                  className="marketing-deep-form"
                  eyebrow="Teste controlado"
                >
                  <h3>Criar experimento A/B</h3>
                  <label>
                    Nome
                    <input
                      value={experimentName}
                      onChange={(event) =>
                        setExperimentName(event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Hipótese
                    <textarea
                      value={hypothesis}
                      onChange={(event) => setHypothesis(event.target.value)}
                      placeholder="Se alterarmos a mensagem, esperamos aumentar..."
                    />
                  </label>
                  <label>
                    Métrica principal
                    <select
                      value={metric}
                      onChange={(event) =>
                        setMetric(
                          event.target.value as Experiment["success_metric"],
                        )
                      }
                    >
                      <option value="click_rate">Taxa de cliques</option>
                      <option value="lead_rate">Taxa de leads</option>
                      <option value="conversion_rate">Taxa de conversão</option>
                      <option value="revenue">Receita</option>
                    </select>
                  </label>
                  <div className="marketing-variant-fields">
                    <label>
                      Variante A
                      <input
                        value={variantA}
                        onChange={(event) => setVariantA(event.target.value)}
                      />
                    </label>
                    <label>
                      Variante B
                      <input
                        value={variantB}
                        onChange={(event) => setVariantB(event.target.value)}
                      />
                    </label>
                  </div>
                  <Button
                    disabled={
                      experimentName.length < 2 || hypothesis.length < 5
                    }
                    onClick={() => createExperiment.mutate()}
                    loading={createExperiment.isPending}
                  >
                    <Plus size={16} /> Criar experimento
                  </Button>
                </Card>
              ) : null}
              <div className="marketing-experiment-list">
                {experiments.data?.map((experiment) => (
                  <article key={experiment.id}>
                    <span>{experiment.status}</span>
                    <h4>{experiment.name}</h4>
                    <p>{experiment.hypothesis}</p>
                    <small>Métrica: {experiment.success_metric}</small>
                    {canUpdate && experiment.status === "draft" ? (
                      <Button
                        variant="secondary"
                        onClick={() =>
                          updateExperiment.mutate({
                            id: experiment.id,
                            body: { status: "running" },
                          })
                        }
                      >
                        Iniciar teste
                      </Button>
                    ) : null}
                    {canUpdate && experiment.status === "running" ? (
                      <div className="marketing-winner-actions">
                        {experiment.variants.map((variant) => (
                          <button
                            key={variant.key}
                            onClick={() =>
                              updateExperiment.mutate({
                                id: experiment.id,
                                body: {
                                  status: "completed",
                                  winner_key: variant.key,
                                },
                              })
                            }
                          >
                            Vencedora: {variant.key}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {view === "attribution" && selectedCampaignId ? (
            <div className="marketing-attribution-layout">
              <Card className="marketing-deep-form" eyebrow="Receita atribuída">
                <h3>Conectar campanha ao resultado</h3>
                <label>
                  Contato
                  <select
                    value={contactId}
                    onChange={(event) => setContactId(event.target.value)}
                  >
                    <option value="">Sem contato</option>
                    {contacts.data?.items.map((contact) => (
                      <option key={contact.id} value={contact.id}>
                        {contact.name}
                        {contact.company_name
                          ? ` · ${contact.company_name}`
                          : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Oportunidade
                  <select
                    value={opportunityId}
                    onChange={(event) => setOpportunityId(event.target.value)}
                  >
                    <option value="">Sem oportunidade</option>
                    {opportunities.data?.map((opportunity) => (
                      <option key={opportunity.id} value={opportunity.id}>
                        {opportunity.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Ponto de contato
                  <select
                    value={touchpoint}
                    onChange={(event) => setTouchpoint(event.target.value)}
                  >
                    <option value="first_touch">Primeiro contato</option>
                    <option value="lead_creation">Criação do lead</option>
                    <option value="influenced">Influenciou a negociação</option>
                    <option value="last_touch">Último contato</option>
                    <option value="conversion">Conversão</option>
                  </select>
                </label>
                <div className="marketing-variant-fields">
                  <label>
                    Origem
                    <input
                      value={source}
                      onChange={(event) => setSource(event.target.value)}
                      placeholder="Google, indicação..."
                    />
                  </label>
                  <label>
                    Mídia
                    <input
                      value={medium}
                      onChange={(event) => setMedium(event.target.value)}
                      placeholder="CPC, e-mail..."
                    />
                  </label>
                </div>
                <label>
                  Valor atribuído em R$
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={attributedValue}
                    onChange={(event) => setAttributedValue(event.target.value)}
                  />
                </label>
                {canUpdate ? (
                  <Button
                    onClick={() => createAttribution.mutate()}
                    loading={createAttribution.isPending}
                  >
                    Registrar atribuição
                  </Button>
                ) : null}
              </Card>
              <div className="marketing-attribution-list">
                <article className="marketing-attributed-total">
                  <span>Receita atribuída</span>
                  <strong>{currency(attributedRevenue)}</strong>
                </article>
                {attributions.data?.map((item) => (
                  <article key={item.id}>
                    <Link2 size={17} />
                    <div>
                      <strong>{currency(item.value_cents)}</strong>
                      <span>
                        {item.touchpoint} ·{" "}
                        {[item.source, item.medium]
                          .filter(Boolean)
                          .join(" / ") || "origem não informada"}
                      </span>
                      <time>
                        {new Date(item.occurred_at).toLocaleString("pt-BR")}
                      </time>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

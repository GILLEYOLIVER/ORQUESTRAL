import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ContactRound,
  GitBranch,
  Megaphone,
  Plus,
  Trash2,
  UsersRound,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import { MarketingIntelligencePanel } from "./marketing/MarketingIntelligencePanel";
import "./marketing.css";

type CampaignStatus =
  "draft" | "scheduled" | "active" | "paused" | "completed" | "cancelled";
type CampaignChannel =
  "email" | "whatsapp" | "sms" | "social" | "multi_channel";
type Campaign = {
  id: string;
  name: string;
  description: string | null;
  objective: string | null;
  channel: CampaignChannel;
  status: CampaignStatus;
  budget_cents: number;
  spent_cents: number;
  audience_total: number;
  engaged_total: number;
  converted_total: number;
};
type Summary = {
  campaigns_total: number;
  campaigns_active: number;
  audience_total: number;
  conversions_total: number;
};
type Audience = {
  id: string;
  campaign_id: string;
  contact_id: string;
  status: string;
};
type Contact = { id: string; name: string; email: string | null };
type Journey = {
  id: string;
  name: string;
  description: string | null;
  trigger_type: string;
  status: string;
  step_total: number;
};
type JourneyStep = {
  id: string;
  journey_id: string;
  name: string;
  action_type: string;
  position: number;
};

const channelLabels: Record<CampaignChannel, string> = {
  email: "E-mail",
  whatsapp: "WhatsApp",
  sms: "SMS",
  social: "Redes sociais",
  multi_channel: "Multicanal",
};
const statusLabels: Record<CampaignStatus, string> = {
  draft: "Rascunho",
  scheduled: "Agendada",
  active: "Ativa",
  paused: "Pausada",
  completed: "Concluída",
  cancelled: "Cancelada",
};
function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}
function money(cents: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

export function MarketingPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"campaigns" | "journeys">("campaigns");
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(
    null,
  );
  const [selectedJourneyId, setSelectedJourneyId] = useState<string | null>(
    null,
  );
  const [showCampaignForm, setShowCampaignForm] = useState(false);
  const [showJourneyForm, setShowJourneyForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [channel, setChannel] = useState<CampaignChannel>("email");
  const [budget, setBudget] = useState("");
  const [journeyName, setJourneyName] = useState("");
  const [stepName, setStepName] = useState("");
  const [contactId, setContactId] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canCreate = me?.permissions.includes("marketing.create") ?? false;
  const canUpdate = me?.permissions.includes("marketing.update") ?? false;
  const canDelete = me?.permissions.includes("marketing.delete") ?? false;
  const canAudience =
    me?.permissions.includes("marketing.audience.manage") ?? false;
  const canJourneys =
    me?.permissions.includes("marketing.journeys.manage") ?? false;
  const canViewContacts =
    me?.permissions.includes("crm.contacts.view") ?? false;
  const campaigns = useQuery({
    queryKey: ["marketing", "campaigns"],
    queryFn: () => request<Campaign[]>("/marketing/campaigns"),
  });
  const summary = useQuery({
    queryKey: ["marketing", "summary"],
    queryFn: () => request<Summary>("/marketing/summary"),
  });
  const journeys = useQuery({
    queryKey: ["marketing", "journeys"],
    queryFn: () => request<Journey[]>("/marketing/journeys"),
  });
  const audience = useQuery({
    queryKey: ["marketing", "campaigns", selectedCampaignId, "audience"],
    queryFn: () =>
      request<Audience[]>(
        `/marketing/campaigns/${selectedCampaignId}/audience`,
      ),
    enabled: Boolean(selectedCampaignId),
  });
  const contacts = useQuery({
    queryKey: ["crm-contacts", "marketing"],
    queryFn: () => request<Contact[]>("/crm/contacts"),
    enabled: canViewContacts && Boolean(selectedCampaignId),
  });
  const steps = useQuery({
    queryKey: ["marketing", "journeys", selectedJourneyId, "steps"],
    queryFn: () =>
      request<JourneyStep[]>(`/marketing/journeys/${selectedJourneyId}/steps`),
    enabled: Boolean(selectedJourneyId),
  });
  const selectedCampaign = useMemo(
    () =>
      campaigns.data?.find((item) => item.id === selectedCampaignId) ?? null,
    [campaigns.data, selectedCampaignId],
  );
  useEffect(() => {
    if (!selectedCampaignId && campaigns.data?.length)
      setSelectedCampaignId(campaigns.data[0].id);
  }, [campaigns.data, selectedCampaignId]);
  const refreshCampaigns = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["marketing", "campaigns"] }),
      queryClient.invalidateQueries({ queryKey: ["marketing", "summary"] }),
    ]);
  };
  const createCampaign = useMutation({
    mutationFn: () =>
      request<Campaign>("/marketing/campaigns", {
        method: "POST",
        body: {
          name,
          description: description || null,
          channel,
          budget_cents: Math.round((Number(budget) || 0) * 100),
        },
      }),
    onSuccess: async (item) => {
      setName("");
      setDescription("");
      setBudget("");
      setShowCampaignForm(false);
      setSelectedCampaignId(item.id);
      setFeedback("Campanha criada com sucesso.");
      setError(null);
      await refreshCampaigns();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a campanha.")),
  });
  const updateCampaign = useMutation({
    mutationFn: ({ id, status }: { id: string; status: CampaignStatus }) =>
      request<Campaign>(`/marketing/campaigns/${id}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: async () => {
      setFeedback("Situação da campanha atualizada.");
      await refreshCampaigns();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível atualizar a campanha.")),
  });
  const archiveCampaign = useMutation({
    mutationFn: (id: string) =>
      request(`/marketing/campaigns/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setSelectedCampaignId(null);
      setFeedback("Campanha arquivada.");
      await refreshCampaigns();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível arquivar a campanha.")),
  });
  const addContact = useMutation({
    mutationFn: () =>
      request<Audience>(`/marketing/campaigns/${selectedCampaignId}/audience`, {
        method: "POST",
        body: { contact_id: contactId },
      }),
    onSuccess: async () => {
      setContactId("");
      setFeedback("Contato adicionado ao público.");
      await Promise.all([
        refreshCampaigns(),
        queryClient.invalidateQueries({
          queryKey: ["marketing", "campaigns", selectedCampaignId, "audience"],
        }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível adicionar o contato.")),
  });
  const removeContact = useMutation({
    mutationFn: (id: string) =>
      request(`/marketing/campaigns/${selectedCampaignId}/audience/${id}`, {
        method: "DELETE",
      }),
    onSuccess: async () => {
      await Promise.all([
        refreshCampaigns(),
        queryClient.invalidateQueries({
          queryKey: ["marketing", "campaigns", selectedCampaignId, "audience"],
        }),
      ]);
    },
  });
  const createJourney = useMutation({
    mutationFn: () =>
      request<Journey>("/marketing/journeys", {
        method: "POST",
        body: { name: journeyName },
      }),
    onSuccess: async (item) => {
      setJourneyName("");
      setShowJourneyForm(false);
      setSelectedJourneyId(item.id);
      setFeedback("Jornada criada com sucesso.");
      await queryClient.invalidateQueries({
        queryKey: ["marketing", "journeys"],
      });
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a jornada.")),
  });
  const createStep = useMutation({
    mutationFn: () =>
      request<JourneyStep>(`/marketing/journeys/${selectedJourneyId}/steps`, {
        method: "POST",
        body: {
          name: stepName,
          action_type: "task",
          position: steps.data?.length ?? 0,
        },
      }),
    onSuccess: async () => {
      setStepName("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["marketing", "journeys"] }),
        queryClient.invalidateQueries({
          queryKey: ["marketing", "journeys", selectedJourneyId, "steps"],
        }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível adicionar a etapa.")),
  });
  return (
    <div className="marketing-page">
      <section className="marketing-hero">
        <div>
          <span className="eyebrow eyebrow--light">Crescimento coordenado</span>
          <h1>Campanhas que acompanham cada oportunidade.</h1>
          <p>
            Planeje canais, organize públicos e construa jornadas conectadas ao
            relacionamento com seus clientes.
          </p>
        </div>
        <Megaphone size={58} />
      </section>
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <section className="marketing-metrics">
        <Card>
          <strong>{summary.data?.campaigns_active ?? 0}</strong>
          <span>campanhas ativas</span>
        </Card>
        <Card>
          <strong>{summary.data?.audience_total ?? 0}</strong>
          <span>pessoas alcançadas</span>
        </Card>
        <Card>
          <strong>{summary.data?.conversions_total ?? 0}</strong>
          <span>conversões registradas</span>
        </Card>
      </section>
      <MarketingIntelligencePanel
        campaigns={campaigns.data ?? []}
        canUpdate={canUpdate}
      />
      <div className="marketing-tabs">
        <button
          className={tab === "campaigns" ? "active" : ""}
          onClick={() => setTab("campaigns")}
          type="button"
        >
          <Megaphone size={16} /> Campanhas
        </button>
        <button
          className={tab === "journeys" ? "active" : ""}
          onClick={() => setTab("journeys")}
          type="button"
        >
          <GitBranch size={16} /> Jornadas
        </button>
      </div>
      {tab === "campaigns" ? (
        <>
          <div className="marketing-heading">
            <div>
              <span className="eyebrow">Campanhas</span>
              <h2>Planejamento e desempenho</h2>
            </div>
            {canCreate ? (
              <Button onClick={() => setShowCampaignForm((value) => !value)}>
                <Plus size={16} /> Nova campanha
              </Button>
            ) : null}
          </div>
          {showCampaignForm ? (
            <Card className="marketing-form">
              <label>
                Nome
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label>
                Canal
                <select
                  value={channel}
                  onChange={(event) =>
                    setChannel(event.target.value as CampaignChannel)
                  }
                >
                  {Object.entries(channelLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Orçamento em reais
                <input
                  inputMode="decimal"
                  value={budget}
                  onChange={(event) => setBudget(event.target.value)}
                />
              </label>
              <label className="wide">
                Objetivo
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>
              <Button
                disabled={name.trim().length < 2}
                loading={createCampaign.isPending}
                onClick={() => createCampaign.mutate()}
              >
                Criar campanha
              </Button>
            </Card>
          ) : null}
          <section className="marketing-workspace">
            <aside className="campaign-list">
              {campaigns.data?.length ? (
                campaigns.data.map((item) => (
                  <button
                    className={item.id === selectedCampaignId ? "active" : ""}
                    key={item.id}
                    onClick={() => setSelectedCampaignId(item.id)}
                    type="button"
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>{channelLabels[item.channel]}</small>
                    </span>
                    <i>{statusLabels[item.status]}</i>
                  </button>
                ))
              ) : (
                <p className="marketing-empty">Nenhuma campanha cadastrada.</p>
              )}
            </aside>
            <Card className="campaign-detail">
              {selectedCampaign ? (
                <>
                  <div className="campaign-detail__top">
                    <div>
                      <span
                        className={`campaign-pill campaign-pill--${selectedCampaign.status}`}
                      >
                        {statusLabels[selectedCampaign.status]}
                      </span>
                      <h2>{selectedCampaign.name}</h2>
                      <p>
                        {selectedCampaign.description ||
                          "Defina o objetivo e monte o público desta campanha."}
                      </p>
                    </div>
                    {canDelete ? (
                      <button
                        className="marketing-danger"
                        onClick={() =>
                          archiveCampaign.mutate(selectedCampaign.id)
                        }
                        type="button"
                      >
                        <Trash2 size={16} /> Arquivar
                      </button>
                    ) : null}
                  </div>
                  <div className="campaign-numbers">
                    <article>
                      <strong>{selectedCampaign.audience_total}</strong>
                      <span>no público</span>
                    </article>
                    <article>
                      <strong>{selectedCampaign.engaged_total}</strong>
                      <span>engajados</span>
                    </article>
                    <article>
                      <strong>{selectedCampaign.converted_total}</strong>
                      <span>convertidos</span>
                    </article>
                    <article>
                      <strong>{money(selectedCampaign.budget_cents)}</strong>
                      <span>orçamento</span>
                    </article>
                  </div>
                  {canUpdate ? (
                    <div className="campaign-actions">
                      <button
                        onClick={() =>
                          updateCampaign.mutate({
                            id: selectedCampaign.id,
                            status: "active",
                          })
                        }
                        type="button"
                      >
                        Ativar
                      </button>
                      <button
                        onClick={() =>
                          updateCampaign.mutate({
                            id: selectedCampaign.id,
                            status: "paused",
                          })
                        }
                        type="button"
                      >
                        Pausar
                      </button>
                      <button
                        onClick={() =>
                          updateCampaign.mutate({
                            id: selectedCampaign.id,
                            status: "completed",
                          })
                        }
                        type="button"
                      >
                        Concluir
                      </button>
                    </div>
                  ) : null}
                  <div className="audience-heading">
                    <div>
                      <UsersRound size={19} />
                      <strong>Público da campanha</strong>
                    </div>
                    {canAudience && canViewContacts ? (
                      <div className="audience-add">
                        <select
                          value={contactId}
                          onChange={(event) => setContactId(event.target.value)}
                        >
                          <option value="">Selecione um contato</option>
                          {contacts.data
                            ?.filter(
                              (contact) =>
                                !audience.data?.some(
                                  (item) => item.contact_id === contact.id,
                                ),
                            )
                            .map((contact) => (
                              <option key={contact.id} value={contact.id}>
                                {contact.name}
                              </option>
                            ))}
                        </select>
                        <Button
                          disabled={!contactId}
                          loading={addContact.isPending}
                          onClick={() => addContact.mutate()}
                        >
                          Adicionar
                        </Button>
                      </div>
                    ) : null}
                  </div>
                  <div className="audience-list">
                    {audience.data?.length ? (
                      audience.data.map((item) => {
                        const contact = contacts.data?.find(
                          (value) => value.id === item.contact_id,
                        );
                        return (
                          <article key={item.id}>
                            <ContactRound size={18} />
                            <span>
                              <strong>
                                {contact?.name ?? "Contato do CRM"}
                              </strong>
                              <small>{item.status}</small>
                            </span>
                            {canAudience ? (
                              <button
                                aria-label="Remover contato"
                                onClick={() => removeContact.mutate(item.id)}
                                type="button"
                              >
                                <Trash2 size={15} />
                              </button>
                            ) : null}
                          </article>
                        );
                      })
                    ) : (
                      <p className="marketing-empty">
                        Adicione contatos do CRM para formar o público.
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <p className="marketing-empty">Selecione uma campanha.</p>
              )}
            </Card>
          </section>
        </>
      ) : (
        <>
          <div className="marketing-heading">
            <div>
              <span className="eyebrow">Jornadas</span>
              <h2>Sequências de relacionamento</h2>
            </div>
            {canJourneys ? (
              <Button onClick={() => setShowJourneyForm((value) => !value)}>
                <Plus size={16} /> Nova jornada
              </Button>
            ) : null}
          </div>
          {showJourneyForm ? (
            <Card className="journey-create">
              <input
                placeholder="Nome da jornada"
                value={journeyName}
                onChange={(event) => setJourneyName(event.target.value)}
              />
              <Button
                disabled={journeyName.trim().length < 2}
                loading={createJourney.isPending}
                onClick={() => createJourney.mutate()}
              >
                Criar jornada
              </Button>
            </Card>
          ) : null}
          <section className="journey-grid">
            <div className="journey-list">
              {journeys.data?.length ? (
                journeys.data.map((journey) => (
                  <button
                    className={journey.id === selectedJourneyId ? "active" : ""}
                    key={journey.id}
                    onClick={() => setSelectedJourneyId(journey.id)}
                    type="button"
                  >
                    <GitBranch size={18} />
                    <span>
                      <strong>{journey.name}</strong>
                      <small>
                        {journey.step_total} etapas · {journey.status}
                      </small>
                    </span>
                    <ArrowRight size={16} />
                  </button>
                ))
              ) : (
                <p className="marketing-empty">Nenhuma jornada criada.</p>
              )}
            </div>
            <Card className="journey-flow">
              {selectedJourneyId ? (
                <>
                  <h3>Etapas da jornada</h3>
                  <div className="journey-steps">
                    {steps.data?.map((step, index) => (
                      <article key={step.id}>
                        <i>{index + 1}</i>
                        <span>
                          <strong>{step.name}</strong>
                          <small>{step.action_type}</small>
                        </span>
                      </article>
                    ))}
                  </div>
                  {canJourneys ? (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (stepName.trim().length >= 2) createStep.mutate();
                      }}
                    >
                      <input
                        placeholder="Nome da próxima etapa"
                        value={stepName}
                        onChange={(event) => setStepName(event.target.value)}
                      />
                      <Button
                        disabled={stepName.trim().length < 2}
                        loading={createStep.isPending}
                        type="submit"
                      >
                        Adicionar etapa
                      </Button>
                    </form>
                  ) : null}
                </>
              ) : (
                <p className="marketing-empty">
                  Selecione uma jornada para montar o fluxo.
                </p>
              )}
            </Card>
          </section>
        </>
      )}
    </div>
  );
}

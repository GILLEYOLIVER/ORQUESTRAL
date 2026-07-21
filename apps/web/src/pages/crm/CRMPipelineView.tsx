import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  CalendarClock,
  CircleDollarSign,
  Plus,
  StickyNote,
  Target,
  Trophy,
} from "lucide-react";

import { request } from "../../lib/http";

type Stage = {
  id: string;
  pipeline_id: string;
  name: string;
  position: number;
  probability: number;
  color: string;
};

type Pipeline = {
  id: string;
  name: string;
  is_default: boolean;
  stages: Stage[];
  opportunity_count: number;
  open_value: string;
};

type Opportunity = {
  id: string;
  pipeline_id: string;
  pipeline_name: string;
  stage_id: string;
  stage_name: string;
  stage_probability: number;
  contact_id: string | null;
  contact_name: string | null;
  title: string;
  amount: string;
  probability: number | null;
  expected_close_date: string | null;
  source: string | null;
  status: "open" | "won" | "lost";
  lost_reason: string | null;
  notes: string | null;
  updated_at: string;
};

type CommercialSummary = {
  pipeline_count: number;
  open_opportunities: number;
  open_value: string;
  won_opportunities: number;
  lost_opportunities: number;
  overdue_opportunities: number;
  weighted_forecast: string;
};

type ActivityItem = {
  id: string;
  activity_type: string;
  subject: string;
  body: string | null;
  occurred_at: string;
};

type ContactPage = {
  items: Array<{ id: string; name: string; company_name: string | null }>;
};

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const refreshKeys = [
  "crm-summary",
  "crm-pipelines",
  "crm-opportunities",
] as const;

export function CRMPipelineView() {
  const queryClient = useQueryClient();
  const [pipelineId, setPipelineId] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showOpportunityForm, setShowOpportunityForm] = useState(false);
  const [showPipelineForm, setShowPipelineForm] = useState(false);
  const [pipelineName, setPipelineName] = useState("");
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [contactId, setContactId] = useState("");
  const [closeDate, setCloseDate] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const [activitySubject, setActivitySubject] = useState("");
  const [activityBody, setActivityBody] = useState("");

  const summaryQuery = useQuery({
    queryKey: ["crm-summary"],
    queryFn: () => request<CommercialSummary>("/crm/summary"),
  });
  const pipelinesQuery = useQuery({
    queryKey: ["crm-pipelines"],
    queryFn: () => request<Pipeline[]>("/crm/pipelines"),
  });
  const activePipelineId = pipelineId || pipelinesQuery.data?.[0]?.id || "";
  const activePipeline = pipelinesQuery.data?.find(
    (item) => item.id === activePipelineId,
  );
  const opportunitiesQuery = useQuery({
    queryKey: ["crm-opportunities", activePipelineId],
    queryFn: () =>
      request<Opportunity[]>(
        `/crm/opportunities?pipeline_id=${activePipelineId}`,
      ),
    enabled: Boolean(activePipelineId),
  });
  const contactsQuery = useQuery({
    queryKey: ["crm-contacts-options"],
    queryFn: () => request<ContactPage>("/crm/contacts?page_size=100"),
  });
  const selectedOpportunity = opportunitiesQuery.data?.find(
    (item) => item.id === selectedId,
  );
  const activitiesQuery = useQuery({
    queryKey: ["crm-opportunity-activities", selectedId],
    queryFn: () =>
      request<ActivityItem[]>(`/crm/opportunities/${selectedId}/activities`),
    enabled: Boolean(selectedId),
  });

  const invalidateCommercial = async () => {
    await Promise.all(
      refreshKeys.map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
  };

  const createPipeline = useMutation({
    mutationFn: () =>
      request<Pipeline>("/crm/pipelines", {
        method: "POST",
        body: {
          name: pipelineName,
          stages: [
            {
              name: "Novo contato",
              position: 0,
              probability: 10,
              color: "#2f6f64",
            },
            {
              name: "Qualificação",
              position: 1,
              probability: 30,
              color: "#d69f40",
            },
            {
              name: "Proposta",
              position: 2,
              probability: 60,
              color: "#cf7246",
            },
            {
              name: "Negociação",
              position: 3,
              probability: 80,
              color: "#377c8c",
            },
            {
              name: "Fechamento",
              position: 4,
              probability: 100,
              color: "#2d8659",
            },
          ],
        },
      }),
    onSuccess: async (pipeline) => {
      setPipelineId(pipeline.id);
      setPipelineName("");
      setShowPipelineForm(false);
      await invalidateCommercial();
    },
  });

  const createOpportunity = useMutation({
    mutationFn: () => {
      const firstStage = activePipeline?.stages[0];
      if (!activePipeline || !firstStage)
        throw new Error("Crie uma etapa antes do negócio.");
      return request<Opportunity>("/crm/opportunities", {
        method: "POST",
        body: {
          title,
          pipeline_id: activePipeline.id,
          stage_id: firstStage.id,
          contact_id: contactId || null,
          amount: Number(amount || 0),
          expected_close_date: closeDate || null,
          source: source || null,
          notes: notes || null,
        },
      });
    },
    onSuccess: async (opportunity) => {
      setSelectedId(opportunity.id);
      setTitle("");
      setAmount("");
      setContactId("");
      setCloseDate("");
      setSource("");
      setNotes("");
      setShowOpportunityForm(false);
      await invalidateCommercial();
    },
  });

  const updateOpportunity = useMutation({
    mutationFn: ({
      id,
      changes,
    }: {
      id: string;
      changes: Record<string, unknown>;
    }) =>
      request<Opportunity>(`/crm/opportunities/${id}`, {
        method: "PATCH",
        body: changes,
      }),
    onSuccess: invalidateCommercial,
  });

  const createActivity = useMutation({
    mutationFn: () =>
      request<ActivityItem>(`/crm/opportunities/${selectedId}/activities`, {
        method: "POST",
        body: {
          activity_type: "note",
          subject: activitySubject,
          body: activityBody || null,
        },
      }),
    onSuccess: async () => {
      setActivitySubject("");
      setActivityBody("");
      await queryClient.invalidateQueries({
        queryKey: ["crm-opportunity-activities", selectedId],
      });
    },
  });

  const opportunitiesByStage = useMemo(() => {
    const grouped = new Map<string, Opportunity[]>();
    activePipeline?.stages.forEach((stage) => grouped.set(stage.id, []));
    opportunitiesQuery.data
      ?.filter((item) => item.status === "open")
      .forEach((item) => grouped.get(item.stage_id)?.push(item));
    return grouped;
  }, [activePipeline, opportunitiesQuery.data]);

  const summary = summaryQuery.data;
  const pendingError =
    createPipeline.error ||
    createOpportunity.error ||
    updateOpportunity.error ||
    createActivity.error;

  return (
    <section className="crm-pipeline-shell">
      <div className="crm-commercial-summary" aria-label="Resumo comercial">
        <article className="crm-metric-card">
          <Target size={20} />
          <span>Negócios abertos</span>
          <strong>{summary?.open_opportunities ?? 0}</strong>
        </article>
        <article className="crm-metric-card">
          <CircleDollarSign size={20} />
          <span>Valor em aberto</span>
          <strong>{money.format(Number(summary?.open_value ?? 0))}</strong>
        </article>
        <article className="crm-metric-card">
          <Trophy size={20} />
          <span>Negócios ganhos</span>
          <strong>{summary?.won_opportunities ?? 0}</strong>
        </article>
        <article className="crm-metric-card">
          <CalendarClock size={20} />
          <span>Previsão ponderada</span>
          <strong>
            {money.format(Number(summary?.weighted_forecast ?? 0))}
          </strong>
          <small>{summary?.overdue_opportunities ?? 0} atrasados</small>
        </article>
      </div>

      <div className="crm-pipeline-toolbar">
        <div>
          <label htmlFor="crm-pipeline-select">Funil comercial</label>
          <select
            id="crm-pipeline-select"
            value={activePipelineId}
            onChange={(event) => {
              setPipelineId(event.target.value);
              setSelectedId(null);
            }}
          >
            {pipelinesQuery.data?.map((pipeline) => (
              <option key={pipeline.id} value={pipeline.id}>
                {pipeline.name}
              </option>
            ))}
          </select>
        </div>
        <button
          className="button secondary"
          type="button"
          onClick={() => setShowPipelineForm((value) => !value)}
        >
          <Plus size={17} /> Novo funil
        </button>
        <button
          className="button primary"
          type="button"
          onClick={() => setShowOpportunityForm((value) => !value)}
        >
          <Plus size={17} /> Nova oportunidade
        </button>
      </div>

      {showPipelineForm ? (
        <form
          className="crm-inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            createPipeline.mutate();
          }}
        >
          <label>
            Nome do novo funil
            <input
              value={pipelineName}
              onChange={(event) => setPipelineName(event.target.value)}
              minLength={2}
              required
            />
          </label>
          <p>
            O funil será criado com cinco etapas comerciais que poderão ser
            ajustadas pela API.
          </p>
          <button
            className="button primary"
            disabled={createPipeline.isPending}
          >
            Criar funil
          </button>
        </form>
      ) : null}

      {showOpportunityForm ? (
        <form
          className="crm-opportunity-form"
          onSubmit={(event) => {
            event.preventDefault();
            createOpportunity.mutate();
          }}
        >
          <label>
            Oportunidade
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Ex.: Implantação para Loja Aurora"
              minLength={2}
              required
            />
          </label>
          <label>
            Valor estimado
            <input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>
          <label>
            Contato
            <select
              value={contactId}
              onChange={(event) => setContactId(event.target.value)}
            >
              <option value="">Sem contato vinculado</option>
              {contactsQuery.data?.items.map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {contact.name}
                  {contact.company_name ? ` · ${contact.company_name}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Previsão de fechamento
            <input
              type="date"
              value={closeDate}
              onChange={(event) => setCloseDate(event.target.value)}
            />
          </label>
          <label>
            Origem
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="Indicação, site, campanha..."
            />
          </label>
          <label className="crm-form-wide">
            Contexto
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Problema, necessidade, próximos passos e restrições do cliente."
            />
          </label>
          <button
            className="button primary crm-form-wide"
            disabled={createOpportunity.isPending}
          >
            Adicionar ao funil
          </button>
        </form>
      ) : null}

      {pendingError ? (
        <p className="form-error">
          {pendingError instanceof Error
            ? pendingError.message
            : "Não foi possível concluir a ação."}
        </p>
      ) : null}

      <div
        className={
          selectedOpportunity
            ? "crm-pipeline-layout has-detail"
            : "crm-pipeline-layout"
        }
      >
        <div
          className="crm-pipeline-board"
          aria-label="Quadro de oportunidades"
        >
          {activePipeline?.stages.map((stage) => {
            const stageItems = opportunitiesByStage.get(stage.id) ?? [];
            const stageValue = stageItems.reduce(
              (total, item) => total + Number(item.amount),
              0,
            );
            return (
              <section
                className="crm-pipeline-column"
                key={stage.id}
                style={{ "--stage-color": stage.color } as React.CSSProperties}
              >
                <header>
                  <div>
                    <span className="crm-stage-dot" />
                    <strong>{stage.name}</strong>
                  </div>
                  <span>{stageItems.length}</span>
                  <small>
                    {money.format(stageValue)} · {stage.probability}%
                  </small>
                </header>
                <div className="crm-stage-stack">
                  {stageItems.map((opportunity) => (
                    <article
                      className={
                        selectedId === opportunity.id
                          ? "crm-opportunity-card selected"
                          : "crm-opportunity-card"
                      }
                      key={opportunity.id}
                      onClick={() => setSelectedId(opportunity.id)}
                    >
                      <strong>{opportunity.title}</strong>
                      <span>
                        {opportunity.contact_name || "Sem contato vinculado"}
                      </span>
                      <b>{money.format(Number(opportunity.amount))}</b>
                      <div className="crm-opportunity-meta">
                        <span>
                          {opportunity.expected_close_date
                            ? new Date(
                                `${opportunity.expected_close_date}T12:00:00`,
                              ).toLocaleDateString("pt-BR")
                            : "Sem previsão"}
                        </span>
                        <select
                          value={opportunity.stage_id}
                          aria-label={`Mover ${opportunity.title}`}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) =>
                            updateOpportunity.mutate({
                              id: opportunity.id,
                              changes: { stage_id: event.target.value },
                            })
                          }
                        >
                          {activePipeline.stages.map((target) => (
                            <option key={target.id} value={target.id}>
                              {target.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </article>
                  ))}
                  {!stageItems.length ? (
                    <p className="crm-stage-empty">
                      Nenhum negócio nesta etapa.
                    </p>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>

        {selectedOpportunity ? (
          <aside className="crm-opportunity-detail">
            <span className="eyebrow">Negócio selecionado</span>
            <h3>{selectedOpportunity.title}</h3>
            <strong className="crm-detail-value">
              {money.format(Number(selectedOpportunity.amount))}
            </strong>
            <dl>
              <div>
                <dt>Contato</dt>
                <dd>{selectedOpportunity.contact_name || "Não vinculado"}</dd>
              </div>
              <div>
                <dt>Etapa</dt>
                <dd>{selectedOpportunity.stage_name}</dd>
              </div>
              <div>
                <dt>Probabilidade</dt>
                <dd>
                  {selectedOpportunity.probability ??
                    selectedOpportunity.stage_probability}
                  %
                </dd>
              </div>
              <div>
                <dt>Origem</dt>
                <dd>{selectedOpportunity.source || "Não informada"}</dd>
              </div>
            </dl>
            {selectedOpportunity.notes ? (
              <p className="crm-detail-notes">{selectedOpportunity.notes}</p>
            ) : null}
            <div className="crm-result-actions">
              <button
                className="button primary"
                onClick={() =>
                  updateOpportunity.mutate({
                    id: selectedOpportunity.id,
                    changes: { status: "won" },
                  })
                }
              >
                <Trophy size={16} /> Marcar como ganha
              </button>
              <button
                className="button secondary"
                onClick={() =>
                  updateOpportunity.mutate({
                    id: selectedOpportunity.id,
                    changes: {
                      status: "lost",
                      lost_reason: "Encerrada no painel comercial",
                    },
                  })
                }
              >
                Marcar como perdida
              </button>
            </div>
            <form
              className="crm-activity-form"
              onSubmit={(event) => {
                event.preventDefault();
                createActivity.mutate();
              }}
            >
              <h4>
                <StickyNote size={17} /> Registrar atividade
              </h4>
              <input
                value={activitySubject}
                onChange={(event) => setActivitySubject(event.target.value)}
                placeholder="Ex.: Reunião de diagnóstico"
                minLength={2}
                required
              />
              <textarea
                value={activityBody}
                onChange={(event) => setActivityBody(event.target.value)}
                placeholder="O que aconteceu e qual é o próximo passo?"
              />
              <button
                className="button secondary"
                disabled={createActivity.isPending}
              >
                Salvar atividade
              </button>
            </form>
            <div className="crm-activity-list">
              <h4>
                <Activity size={17} /> Histórico
              </h4>
              {activitiesQuery.data?.map((item) => (
                <article key={item.id}>
                  <ArrowRight size={15} />
                  <div>
                    <strong>{item.subject}</strong>
                    {item.body ? <p>{item.body}</p> : null}
                    <time>
                      {new Date(item.occurred_at).toLocaleString("pt-BR")}
                    </time>
                  </div>
                </article>
              ))}
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  );
}

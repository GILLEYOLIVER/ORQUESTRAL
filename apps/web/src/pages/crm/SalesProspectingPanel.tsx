import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, Target, UserPlus } from "lucide-react";
import { Alert, Button } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import { useSession } from "../../session/context";

type Account = {
  id: string;
  name: string;
  industry: string | null;
  website: string | null;
  status: "prospect" | "customer" | "partner" | "inactive";
};

type Lead = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company_name: string | null;
  source: string | null;
  status: "new" | "working" | "qualified" | "converted" | "disqualified";
  score: number;
  converted_account_id: string | null;
  converted_contact_id: string | null;
  converted_opportunity_id: string | null;
};

type Pipeline = {
  id: string;
  name: string;
  stages: Array<{ id: string; name: string; position: number }>;
};

const statusLabel: Record<Lead["status"], string> = {
  new: "Novo",
  working: "Em contato",
  qualified: "Qualificado",
  converted: "Convertido",
  disqualified: "Desqualificado",
};

function messageFrom(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function SalesProspectingPanel() {
  const queryClient = useQueryClient();
  const session = useSession();
  const readOnly = session.me?.access_mode === "read_only";
  const [error, setError] = useState<string | null>(null);
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadCompany, setLeadCompany] = useState("");
  const [leadSource, setLeadSource] = useState("");
  const [accountName, setAccountName] = useState("");
  const [accountIndustry, setAccountIndustry] = useState("");
  const [accountWebsite, setAccountWebsite] = useState("");
  const [filter, setFilter] = useState<Lead["status"] | "all">("all");
  const [convertLeadId, setConvertLeadId] = useState<string | null>(null);
  const [pipelineId, setPipelineId] = useState("");
  const [stageId, setStageId] = useState("");
  const [opportunityTitle, setOpportunityTitle] = useState("");
  const [amount, setAmount] = useState("0");

  const leads = useQuery({
    queryKey: ["crm-sales-leads", filter],
    queryFn: () =>
      request<Lead[]>(
        `/crm/sales/leads${filter === "all" ? "" : `?status=${filter}`}`,
      ),
  });
  const accounts = useQuery({
    queryKey: ["crm-sales-accounts"],
    queryFn: () => request<Account[]>("/crm/sales/accounts"),
  });
  const pipelines = useQuery({
    queryKey: ["crm-pipelines"],
    queryFn: () => request<Pipeline[]>("/crm/pipelines"),
  });

  const activePipeline = useMemo(
    () =>
      pipelines.data?.find((item) => item.id === pipelineId) ??
      pipelines.data?.[0],
    [pipelineId, pipelines.data],
  );
  const activeStage =
    activePipeline?.stages.find((item) => item.id === stageId) ??
    activePipeline?.stages.toSorted((a, b) => a.position - b.position)[0];

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["crm-sales-leads"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-sales-accounts"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-opportunities"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-contacts"] }),
      queryClient.invalidateQueries({ queryKey: ["crm-commercial-summary"] }),
    ]);
  };

  const createLead = useMutation({
    mutationFn: () =>
      request<Lead>("/crm/sales/leads", {
        method: "POST",
        body: {
          name: leadName,
          email: leadEmail || null,
          phone: leadPhone || null,
          company_name: leadCompany || null,
          source: leadSource || null,
        },
      }),
    onSuccess: async () => {
      setLeadName("");
      setLeadEmail("");
      setLeadPhone("");
      setLeadCompany("");
      setLeadSource("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(messageFrom(caught, "Não foi possível criar o lead.")),
  });

  const createAccount = useMutation({
    mutationFn: () =>
      request<Account>("/crm/sales/accounts", {
        method: "POST",
        body: {
          name: accountName,
          industry: accountIndustry || null,
          website: accountWebsite || null,
        },
      }),
    onSuccess: async () => {
      setAccountName("");
      setAccountIndustry("");
      setAccountWebsite("");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(messageFrom(caught, "Não foi possível criar a conta.")),
  });

  const qualify = useMutation({
    mutationFn: (lead: Lead) =>
      request<Lead>(`/crm/sales/leads/${lead.id}/qualification`, {
        method: "POST",
        body: {
          decision: "qualified",
          note: `Qualificado manualmente com pontuação ${lead.score}.`,
        },
      }),
    onSuccess: refresh,
    onError: (caught) =>
      setError(messageFrom(caught, "Não foi possível qualificar o lead.")),
  });

  const convert = useMutation({
    mutationFn: () => {
      if (!convertLeadId || !activePipeline || !activeStage) {
        throw new Error("Selecione um funil e uma etapa.");
      }
      return request(`/crm/sales/leads/${convertLeadId}/conversion`, {
        method: "POST",
        body: {
          pipeline_id: activePipeline.id,
          stage_id: activeStage.id,
          create_account: true,
          opportunity_title: opportunityTitle,
          amount: Number(amount || 0),
        },
      });
    },
    onSuccess: async () => {
      setConvertLeadId(null);
      setOpportunityTitle("");
      setAmount("0");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(messageFrom(caught, "Não foi possível converter o lead.")),
  });

  const metrics = useMemo(() => {
    const items = leads.data ?? [];
    return {
      total: items.length,
      qualified: items.filter((item) => item.status === "qualified").length,
      converted: items.filter((item) => item.status === "converted").length,
      average:
        items.length > 0
          ? Math.round(items.reduce((sum, item) => sum + item.score, 0) / items.length)
          : 0,
    };
  }, [leads.data]);

  return (
    <details className="crm-pipeline-disclosure sales-prospecting" open>
      <summary>
        <span>Prospecção e contas</span>
        <small>
          Capture, qualifique e converta leads sem duplicar contatos ou
          oportunidades.
        </small>
      </summary>
      <div className="sales-prospecting__header">
        <div>
          <h2>Central de prospecção</h2>
          <p>Uma trilha auditável desde o primeiro contato até o negócio.</p>
        </div>
        <div className="sales-prospecting__toolbar">
          <select
            aria-label="Filtrar leads por situação"
            onChange={(event) =>
              setFilter(event.target.value as Lead["status"] | "all")
            }
            value={filter}
          >
            <option value="all">Todos os leads</option>
            {Object.entries(statusLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="sales-prospecting__metrics">
        <div className="sales-prospecting__metric">
          <strong>{metrics.total}</strong>
          <span>leads no filtro</span>
        </div>
        <div className="sales-prospecting__metric">
          <strong>{metrics.qualified}</strong>
          <span>qualificados</span>
        </div>
        <div className="sales-prospecting__metric">
          <strong>{metrics.converted}</strong>
          <span>convertidos</span>
        </div>
        <div className="sales-prospecting__metric">
          <strong>{metrics.average}</strong>
          <span>pontuação média</span>
        </div>
      </div>
      <div className="sales-prospecting__forms">
        <form
          className="sales-prospecting__form"
          onSubmit={(event) => {
            event.preventDefault();
            createLead.mutate();
          }}
        >
          <strong>
            <UserPlus size={17} /> Novo lead
          </strong>
          <label>
            Nome
            <input
              disabled={readOnly}
              onChange={(event) => setLeadName(event.target.value)}
              required
              value={leadName}
            />
          </label>
          <label>
            Empresa
            <input
              disabled={readOnly}
              onChange={(event) => setLeadCompany(event.target.value)}
              value={leadCompany}
            />
          </label>
          <label>
            E-mail
            <input
              disabled={readOnly}
              onChange={(event) => setLeadEmail(event.target.value)}
              type="email"
              value={leadEmail}
            />
          </label>
          <label>
            Telefone
            <input
              disabled={readOnly}
              onChange={(event) => setLeadPhone(event.target.value)}
              value={leadPhone}
            />
          </label>
          <label>
            Origem
            <input
              disabled={readOnly}
              onChange={(event) => setLeadSource(event.target.value)}
              placeholder="Evento, indicação, site..."
              value={leadSource}
            />
          </label>
          <Button
            disabled={readOnly || leadName.trim().length < 2}
            loading={createLead.isPending}
            title={readOnly ? "Acesso somente leitura" : undefined}
            type="submit"
          >
            Cadastrar lead
          </Button>
        </form>
        <form
          className="sales-prospecting__form"
          onSubmit={(event) => {
            event.preventDefault();
            createAccount.mutate();
          }}
        >
          <strong>
            <Building2 size={17} /> Nova conta empresarial
          </strong>
          <label>
            Nome da conta
            <input
              disabled={readOnly}
              onChange={(event) => setAccountName(event.target.value)}
              required
              value={accountName}
            />
          </label>
          <label>
            Segmento
            <input
              disabled={readOnly}
              onChange={(event) => setAccountIndustry(event.target.value)}
              value={accountIndustry}
            />
          </label>
          <label>
            Site
            <input
              disabled={readOnly}
              onChange={(event) => setAccountWebsite(event.target.value)}
              placeholder="https://"
              type="url"
              value={accountWebsite}
            />
          </label>
          <Button
            disabled={readOnly || accountName.trim().length < 2}
            loading={createAccount.isPending}
            title={readOnly ? "Acesso somente leitura" : undefined}
            type="submit"
          >
            Cadastrar conta
          </Button>
        </form>
      </div>
      <div className="sales-prospecting__content">
        <div className="sales-prospecting__list">
          <strong>Leads comerciais</strong>
          {leads.isLoading ? <p>Carregando leads...</p> : null}
          {leads.data?.length === 0 ? (
            <p className="sales-prospecting__empty">
              Nenhum lead neste filtro.
            </p>
          ) : null}
          {leads.data?.map((lead) => (
            <article className="sales-prospecting__lead" key={lead.id}>
              <div className="sales-prospecting__lead-head">
                <div>
                  <h3>{lead.name}</h3>
                  <p>{lead.company_name || "Sem empresa informada"}</p>
                </div>
                <span className="sales-prospecting__status">
                  {statusLabel[lead.status]}
                </span>
              </div>
              <div className="sales-prospecting__score">
                <meter max="100" min="0" value={lead.score} />
                <strong>{lead.score}/100</strong>
              </div>
              <small>
                {lead.source ? `Origem: ${lead.source}` : "Origem não informada"}
              </small>
              <div className="sales-prospecting__actions">
                {lead.status !== "converted" && lead.status !== "qualified" ? (
                  <Button
                    disabled={readOnly}
                    loading={qualify.isPending}
                    onClick={() => qualify.mutate(lead)}
                    title={readOnly ? "Acesso somente leitura" : undefined}
                    variant="secondary"
                  >
                    <CheckCircle2 size={16} /> Qualificar
                  </Button>
                ) : null}
                {lead.status === "qualified" ? (
                  <Button
                    disabled={readOnly}
                    onClick={() => {
                      setConvertLeadId(lead.id);
                      setOpportunityTitle(
                        `Negócio com ${lead.company_name || lead.name}`,
                      );
                    }}
                    title={readOnly ? "Acesso somente leitura" : undefined}
                  >
                    <Target size={16} /> Converter
                  </Button>
                ) : null}
              </div>
              {convertLeadId === lead.id ? (
                <div className="sales-prospecting__conversion">
                  <label>
                    Funil
                    <select
                      disabled={readOnly}
                      onChange={(event) => {
                        setPipelineId(event.target.value);
                        setStageId("");
                      }}
                      value={activePipeline?.id ?? ""}
                    >
                      {pipelines.data?.map((pipeline) => (
                        <option key={pipeline.id} value={pipeline.id}>
                          {pipeline.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Etapa inicial
                    <select
                      disabled={readOnly}
                      onChange={(event) => setStageId(event.target.value)}
                      value={activeStage?.id ?? ""}
                    >
                      {activePipeline?.stages
                        .toSorted((a, b) => a.position - b.position)
                        .map((stage) => (
                          <option key={stage.id} value={stage.id}>
                            {stage.name}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Oportunidade
                    <input
                      disabled={readOnly}
                      onChange={(event) =>
                        setOpportunityTitle(event.target.value)
                      }
                      value={opportunityTitle}
                    />
                  </label>
                  <label>
                    Valor estimado
                    <input
                      disabled={readOnly}
                      min="0"
                      onChange={(event) => setAmount(event.target.value)}
                      step="0.01"
                      type="number"
                      value={amount}
                    />
                  </label>
                  <div className="sales-prospecting__actions">
                    <Button
                      disabled={
                        readOnly ||
                        !activePipeline ||
                        !activeStage ||
                        opportunityTitle.trim().length < 2
                      }
                      loading={convert.isPending}
                      onClick={() => convert.mutate()}
                    >
                      Confirmar conversão
                    </Button>
                    <Button
                      onClick={() => setConvertLeadId(null)}
                      variant="secondary"
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
        <div className="sales-prospecting__accounts">
          <strong>Contas empresariais</strong>
          {accounts.isLoading ? <p>Carregando contas...</p> : null}
          {accounts.data?.length === 0 ? (
            <p className="sales-prospecting__empty">
              Nenhuma conta cadastrada.
            </p>
          ) : null}
          {accounts.data?.map((account) => (
            <article className="sales-prospecting__account" key={account.id}>
              <strong>{account.name}</strong>
              <small>{account.industry || "Segmento não informado"}</small>
              <span className="sales-prospecting__status">
                {account.status}
              </span>
            </article>
          ))}
        </div>
      </div>
    </details>
  );
}

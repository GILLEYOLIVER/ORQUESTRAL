import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarCheck2,
  Clock3,
  FolderTree,
  LockKeyhole,
  Plus,
  ShieldAlert,
  Target,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { ApiClientError, request } from "../../lib/http";
import "./project-portfolio.css";

export interface GovernedProject {
  id: string;
  name: string;
  portfolio_id: string | null;
  owner_user_id: string | null;
  health: "unknown" | "on_track" | "at_risk" | "off_track";
  budget_cents: number;
  version: number;
}

type Summary = {
  portfolio_count: number;
  project_count: number;
  active_projects: number;
  overdue_projects: number;
  at_risk_projects: number;
  open_risks: number;
  critical_risks: number;
  milestone_count: number;
  overdue_milestones: number;
  planned_minutes: number;
  actual_minutes: number;
};

type Portfolio = {
  id: string;
  name: string;
  description: string | null;
  objective: string | null;
  budget_cents: number;
  project_count: number;
  active_projects: number;
  at_risk_projects: number;
};

type Milestone = {
  id: string;
  name: string;
  description: string | null;
  due_date: string;
  status: "pending" | "at_risk" | "completed" | "cancelled";
  task_total: number;
  task_done: number;
};

type Risk = {
  id: string;
  title: string;
  description: string;
  mitigation: string | null;
  probability: number;
  impact: number;
  score: number;
  status: "open" | "mitigating" | "accepted" | "closed";
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação de portfólio.";
}

function currency(cents: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

export function ProjectPortfolioPanel({
  project,
  canCreate,
  canUpdate,
}: {
  project: GovernedProject | null;
  canCreate: boolean;
  canUpdate: boolean;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [view, setView] = useState<"governance" | "milestones" | "risks">(
    "governance",
  );
  const [showPortfolioForm, setShowPortfolioForm] = useState(false);
  const [portfolioName, setPortfolioName] = useState("");
  const [portfolioObjective, setPortfolioObjective] = useState("");
  const [portfolioBudget, setPortfolioBudget] = useState("");
  const [milestoneName, setMilestoneName] = useState("");
  const [milestoneDate, setMilestoneDate] = useState("");
  const [riskTitle, setRiskTitle] = useState("");
  const [riskDescription, setRiskDescription] = useState("");
  const [riskMitigation, setRiskMitigation] = useState("");
  const [riskProbability, setRiskProbability] = useState(3);
  const [riskImpact, setRiskImpact] = useState(3);

  const summary = useQuery({
    queryKey: ["projects", "portfolio-summary"],
    queryFn: () => request<Summary>("/projects/portfolio-summary"),
  });
  const portfolios = useQuery({
    queryKey: ["projects", "portfolios"],
    queryFn: () => request<Portfolio[]>("/projects/portfolios"),
  });
  const governance = useQuery({
    queryKey: ["projects", project?.id, "governance"],
    queryFn: () =>
      request<GovernedProject>(`/projects/${project?.id}/governance`),
    enabled: Boolean(project),
  });
  const governedProject = governance.data ?? project;
  const milestones = useQuery({
    queryKey: ["projects", project?.id, "milestones"],
    queryFn: () => request<Milestone[]>(`/projects/${project?.id}/milestones`),
    enabled: expanded && Boolean(project),
  });
  const risks = useQuery({
    queryKey: ["projects", project?.id, "risks"],
    queryFn: () => request<Risk[]>(`/projects/${project?.id}/risks`),
    enabled: expanded && Boolean(project),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["projects"] }),
      queryClient.invalidateQueries({
        queryKey: ["projects", "portfolio-summary"],
      }),
      queryClient.invalidateQueries({ queryKey: ["projects", "portfolios"] }),
      queryClient.invalidateQueries({ queryKey: ["projects", project?.id] }),
      queryClient.invalidateQueries({
        queryKey: ["projects", project?.id, "governance"],
      }),
    ]);
  };

  const createPortfolio = useMutation({
    mutationFn: () =>
      request<Portfolio>("/projects/portfolios", {
        method: "POST",
        body: {
          name: portfolioName,
          objective: portfolioObjective || null,
          description: null,
          budget_cents: Math.round(Number(portfolioBudget || 0) * 100),
        },
      }),
    onSuccess: async () => {
      setPortfolioName("");
      setPortfolioObjective("");
      setPortfolioBudget("");
      setShowPortfolioForm(false);
      await refresh();
    },
  });

  const updateGovernance = useMutation({
    mutationFn: (changes: Record<string, unknown>) => {
      if (!governedProject) throw new Error("Selecione um projeto.");
      return request<GovernedProject>(
        `/projects/${governedProject.id}/governance`,
        {
          method: "PATCH",
          body: { ...changes, expected_version: governedProject.version },
        },
      );
    },
    onSuccess: refresh,
  });

  const createMilestone = useMutation({
    mutationFn: () =>
      request<Milestone>(`/projects/${project?.id}/milestones`, {
        method: "POST",
        body: {
          name: milestoneName,
          description: null,
          due_date: milestoneDate,
        },
      }),
    onSuccess: async () => {
      setMilestoneName("");
      setMilestoneDate("");
      await refresh();
    },
  });

  const updateMilestone = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Milestone["status"] }) =>
      request<Milestone>(`/projects/${project?.id}/milestones/${id}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: refresh,
  });

  const createRisk = useMutation({
    mutationFn: () =>
      request<Risk>(`/projects/${project?.id}/risks`, {
        method: "POST",
        body: {
          title: riskTitle,
          description: riskDescription,
          mitigation: riskMitigation || null,
          probability: riskProbability,
          impact: riskImpact,
          owner_user_id: null,
        },
      }),
    onSuccess: async () => {
      setRiskTitle("");
      setRiskDescription("");
      setRiskMitigation("");
      await refresh();
    },
  });

  const updateRisk = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Risk["status"] }) =>
      request<Risk>(`/projects/${project?.id}/risks/${id}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: refresh,
  });

  const activeError =
    createPortfolio.error ||
    updateGovernance.error ||
    createMilestone.error ||
    updateMilestone.error ||
    createRisk.error ||
    updateRisk.error;
  const data = summary.data;

  return (
    <section className="project-portfolio-panel">
      <header>
        <div>
          <span className="eyebrow">Governança e segurança</span>
          <h2>Portfólio, capacidade e risco</h2>
          <p>
            Controle decisões, dependências e informações sensíveis sem misturar
            empresas.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          <FolderTree size={17} />{" "}
          {expanded ? "Recolher governança" : "Abrir governança"}
        </Button>
      </header>

      <div className="project-portfolio-metrics">
        <article>
          <Target size={19} />
          <span>Projetos ativos</span>
          <strong>{data?.active_projects ?? 0}</strong>
        </article>
        <article>
          <CalendarCheck2 size={19} />
          <span>Marcos atrasados</span>
          <strong>{data?.overdue_milestones ?? 0}</strong>
        </article>
        <article className={(data?.critical_risks ?? 0) > 0 ? "danger" : ""}>
          <ShieldAlert size={19} />
          <span>Riscos críticos</span>
          <strong>{data?.critical_risks ?? 0}</strong>
        </article>
        <article>
          <Clock3 size={19} />
          <span>Horas planejadas</span>
          <strong>{Math.round((data?.planned_minutes ?? 0) / 60)} h</strong>
        </article>
      </div>

      {expanded ? (
        <div className="project-portfolio-body">
          <div className="project-security-banner">
            <LockKeyhole size={20} />
            <div>
              <strong>Dados sensíveis protegidos</strong>
              <span>
                Descrições e planos de mitigação dos riscos usam criptografia
                autenticada AES-256-GCM.
              </span>
            </div>
          </div>
          {activeError ? (
            <Alert variant="error">{errorMessage(activeError)}</Alert>
          ) : null}
          <div className="project-governance-controls">
            <nav>
              <button
                className={view === "governance" ? "active" : ""}
                onClick={() => setView("governance")}
              >
                Governança
              </button>
              <button
                className={view === "milestones" ? "active" : ""}
                onClick={() => setView("milestones")}
              >
                Marcos
              </button>
              <button
                className={view === "risks" ? "active" : ""}
                onClick={() => setView("risks")}
              >
                Riscos
              </button>
            </nav>
            {canCreate ? (
              <button onClick={() => setShowPortfolioForm((value) => !value)}>
                <Plus size={15} /> Novo portfólio
              </button>
            ) : null}
          </div>

          {showPortfolioForm ? (
            <Card className="project-deep-form" eyebrow="Novo portfólio">
              <label>
                Nome
                <input
                  value={portfolioName}
                  onChange={(event) => setPortfolioName(event.target.value)}
                />
              </label>
              <label>
                Objetivo
                <input
                  value={portfolioObjective}
                  onChange={(event) =>
                    setPortfolioObjective(event.target.value)
                  }
                />
              </label>
              <label>
                Orçamento em R$
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={portfolioBudget}
                  onChange={(event) => setPortfolioBudget(event.target.value)}
                />
              </label>
              <Button
                disabled={portfolioName.length < 2}
                loading={createPortfolio.isPending}
                onClick={() => createPortfolio.mutate()}
              >
                Criar portfólio
              </Button>
            </Card>
          ) : null}

          {view === "governance" ? (
            <div className="project-governance-grid">
              <div className="portfolio-list">
                {portfolios.data?.map((portfolio) => (
                  <article key={portfolio.id}>
                    <strong>{portfolio.name}</strong>
                    <span>
                      {portfolio.objective || "Objetivo não informado"}
                    </span>
                    <dl>
                      <div>
                        <dt>Projetos</dt>
                        <dd>{portfolio.project_count}</dd>
                      </div>
                      <div>
                        <dt>Em risco</dt>
                        <dd>{portfolio.at_risk_projects}</dd>
                      </div>
                      <div>
                        <dt>Orçamento</dt>
                        <dd>{currency(portfolio.budget_cents)}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
              {governedProject ? (
                <Card
                  className="project-deep-form"
                  eyebrow="Projeto selecionado"
                >
                  <h3>{governedProject.name}</h3>
                  <label>
                    Portfólio
                    <select
                      value={governedProject.portfolio_id ?? ""}
                      onChange={(event) =>
                        updateGovernance.mutate({
                          portfolio_id: event.target.value || null,
                        })
                      }
                    >
                      <option value="">Sem portfólio</option>
                      {portfolios.data?.map((portfolio) => (
                        <option key={portfolio.id} value={portfolio.id}>
                          {portfolio.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Saúde do projeto
                    <select
                      value={governedProject.health}
                      onChange={(event) =>
                        updateGovernance.mutate({ health: event.target.value })
                      }
                    >
                      <option value="unknown">Não avaliado</option>
                      <option value="on_track">No caminho</option>
                      <option value="at_risk">Em risco</option>
                      <option value="off_track">Fora do plano</option>
                    </select>
                  </label>
                  <label>
                    Orçamento em R$
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      defaultValue={governedProject.budget_cents / 100}
                      onBlur={(event) =>
                        canUpdate &&
                        updateGovernance.mutate({
                          budget_cents: Math.round(
                            Number(event.target.value) * 100,
                          ),
                        })
                      }
                    />
                  </label>
                </Card>
              ) : (
                <p className="project-panel-hint">
                  Selecione um projeto para definir sua governança.
                </p>
              )}
            </div>
          ) : null}

          {view === "milestones" && project ? (
            <div className="project-milestone-layout">
              {canUpdate ? (
                <Card
                  className="project-deep-form"
                  eyebrow="Entrega importante"
                >
                  <label>
                    Nome do marco
                    <input
                      value={milestoneName}
                      onChange={(event) => setMilestoneName(event.target.value)}
                    />
                  </label>
                  <label>
                    Data limite
                    <input
                      type="date"
                      value={milestoneDate}
                      onChange={(event) => setMilestoneDate(event.target.value)}
                    />
                  </label>
                  <Button
                    disabled={milestoneName.length < 2 || !milestoneDate}
                    onClick={() => createMilestone.mutate()}
                  >
                    Criar marco
                  </Button>
                </Card>
              ) : null}
              <div className="project-milestone-list">
                {milestones.data?.map((milestone) => (
                  <article
                    className={`status-${milestone.status}`}
                    key={milestone.id}
                  >
                    <CalendarCheck2 size={18} />
                    <div>
                      <strong>{milestone.name}</strong>
                      <span>
                        {new Date(
                          `${milestone.due_date}T12:00:00`,
                        ).toLocaleDateString("pt-BR")}{" "}
                        · {milestone.task_done}/{milestone.task_total} tarefas
                      </span>
                    </div>
                    {canUpdate && milestone.status !== "completed" ? (
                      <button
                        onClick={() =>
                          updateMilestone.mutate({
                            id: milestone.id,
                            status: "completed",
                          })
                        }
                      >
                        Concluir
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {view === "risks" && project ? (
            <div className="project-risk-layout">
              {canUpdate ? (
                <Card
                  className="project-deep-form"
                  eyebrow="Registro criptografado"
                >
                  <label>
                    Título
                    <input
                      value={riskTitle}
                      onChange={(event) => setRiskTitle(event.target.value)}
                    />
                  </label>
                  <label>
                    Descrição
                    <textarea
                      value={riskDescription}
                      onChange={(event) =>
                        setRiskDescription(event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Plano de mitigação
                    <textarea
                      value={riskMitigation}
                      onChange={(event) =>
                        setRiskMitigation(event.target.value)
                      }
                    />
                  </label>
                  <div className="project-risk-scales">
                    <label>
                      Probabilidade
                      <select
                        value={riskProbability}
                        onChange={(event) =>
                          setRiskProbability(Number(event.target.value))
                        }
                      >
                        {[1, 2, 3, 4, 5].map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Impacto
                      <select
                        value={riskImpact}
                        onChange={(event) =>
                          setRiskImpact(Number(event.target.value))
                        }
                      >
                        {[1, 2, 3, 4, 5].map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <Button
                    disabled={
                      riskTitle.length < 2 || riskDescription.length < 2
                    }
                    onClick={() => createRisk.mutate()}
                  >
                    Registrar risco
                  </Button>
                </Card>
              ) : null}
              <div className="project-risk-list">
                {risks.data?.map((risk) => (
                  <article
                    className={risk.score >= 15 ? "critical" : ""}
                    key={risk.id}
                  >
                    <header>
                      <AlertTriangle size={18} />
                      <strong>{risk.title}</strong>
                      <b>{risk.score}/25</b>
                    </header>
                    <p>{risk.description}</p>
                    <span>
                      {risk.mitigation || "Mitigação ainda não definida."}
                    </span>
                    {canUpdate && risk.status !== "closed" ? (
                      <button
                        onClick={() =>
                          updateRisk.mutate({ id: risk.id, status: "closed" })
                        }
                      >
                        Encerrar risco
                      </button>
                    ) : null}
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

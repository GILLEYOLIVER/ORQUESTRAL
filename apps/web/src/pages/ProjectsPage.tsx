import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Circle,
  FolderKanban,
  PauseCircle,
  Plus,
  Trash2,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import {
  ProjectPortfolioPanel,
  type GovernedProject,
} from "./projects/ProjectPortfolioPanel";
import "./projects.css";

type ProjectStatus =
  "planning" | "active" | "on_hold" | "completed" | "cancelled";
type TaskStatus = "todo" | "in_progress" | "blocked" | "done" | "cancelled";
type Priority = "low" | "normal" | "high" | "urgent";
type Project = {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  priority: Priority;
  start_date: string | null;
  due_date: string | null;
  task_total: number;
  task_done: number;
  progress_percent: number;
  updated_at: string;
  portfolio_id: string | null;
  owner_user_id: string | null;
  health: "unknown" | "on_track" | "at_risk" | "off_track";
  budget_cents: number;
  version: number;
};
type ProjectTask = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: Priority;
  due_date: string | null;
  position: number;
};

const statusLabels: Record<ProjectStatus, string> = {
  planning: "Planejamento",
  active: "Em andamento",
  on_hold: "Pausado",
  completed: "Concluído",
  cancelled: "Cancelado",
};
const taskStatusLabels: Record<TaskStatus, string> = {
  todo: "A fazer",
  in_progress: "Em andamento",
  blocked: "Bloqueada",
  done: "Concluída",
  cancelled: "Cancelada",
};
function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}
function formatDate(value: string | null) {
  if (!value) return "Sem prazo";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium" }).format(
    new Date(`${value}T12:00:00`),
  );
}

export function ProjectsPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const canCreate = me?.permissions.includes("projects.create") ?? false;
  const canUpdate = me?.permissions.includes("projects.update") ?? false;
  const canDelete = me?.permissions.includes("projects.delete") ?? false;
  const canManageTasks =
    me?.permissions.includes("projects.tasks.manage") ?? false;
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => request<Project[]>("/projects"),
  });
  const selected = useMemo(
    () => projects.data?.find((project) => project.id === selectedId) ?? null,
    [projects.data, selectedId],
  );
  const tasks = useQuery({
    queryKey: ["projects", selectedId, "tasks"],
    queryFn: () => request<ProjectTask[]>(`/projects/${selectedId}/tasks`),
    enabled: Boolean(selectedId),
  });
  useEffect(() => {
    if (!selectedId && projects.data?.length)
      setSelectedId(projects.data[0].id);
    if (
      selectedId &&
      projects.data &&
      !projects.data.some((item) => item.id === selectedId)
    )
      setSelectedId(projects.data[0]?.id ?? null);
  }, [projects.data, selectedId]);
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
  };
  const createProject = useMutation({
    mutationFn: () =>
      request<Project>("/projects", {
        method: "POST",
        body: {
          name,
          description: description || null,
          due_date: dueDate || null,
        },
      }),
    onSuccess: async (project) => {
      setError(null);
      setFeedback("Projeto criado e pronto para receber tarefas.");
      setName("");
      setDescription("");
      setDueDate("");
      setShowCreate(false);
      setSelectedId(project.id);
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar o projeto.")),
  });
  const updateProject = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProjectStatus }) =>
      request<Project>(`/projects/${id}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: async () => {
      setError(null);
      setFeedback("Situação do projeto atualizada.");
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível atualizar o projeto.")),
  });
  const archiveProject = useMutation({
    mutationFn: (id: string) =>
      request(`/projects/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setSelectedId(null);
      setError(null);
      setFeedback("Projeto arquivado com segurança.");
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível arquivar o projeto.")),
  });
  const createTask = useMutation({
    mutationFn: () =>
      request<ProjectTask>(`/projects/${selectedId}/tasks`, {
        method: "POST",
        body: { title: taskTitle },
      }),
    onSuccess: async () => {
      setTaskTitle("");
      setError(null);
      await Promise.all([
        refresh(),
        queryClient.invalidateQueries({
          queryKey: ["projects", selectedId, "tasks"],
        }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar a tarefa.")),
  });
  const updateTask = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: TaskStatus }) =>
      request<ProjectTask>(`/projects/${selectedId}/tasks/${taskId}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: async () => {
      await Promise.all([
        refresh(),
        queryClient.invalidateQueries({
          queryKey: ["projects", selectedId, "tasks"],
        }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível atualizar a tarefa.")),
  });
  const deleteTask = useMutation({
    mutationFn: (taskId: string) =>
      request(`/projects/${selectedId}/tasks/${taskId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await Promise.all([
        refresh(),
        queryClient.invalidateQueries({
          queryKey: ["projects", selectedId, "tasks"],
        }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível excluir a tarefa.")),
  });
  return (
    <div className="projects-page">
      <section className="projects-hero">
        <div>
          <span className="eyebrow eyebrow--light">Central de entregas</span>
          <h1>Projetos com rumo, prazo e progresso visível.</h1>
          <p>
            Organize iniciativas, acompanhe tarefas e transforme planos em
            entregas.
          </p>
        </div>
        <div className="projects-hero__summary">
          <strong>
            {projects.data?.filter((item) => item.status === "active").length ??
              0}
          </strong>
          <span>em andamento</span>
        </div>
      </section>
      <ProjectPortfolioPanel
        project={selected as GovernedProject | null}
        canCreate={canCreate}
        canUpdate={canUpdate}
      />
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="projects-toolbar">
        <div>
          <span className="eyebrow">Portfólio</span>
          <h2>Projetos da empresa</h2>
        </div>
        {canCreate ? (
          <Button onClick={() => setShowCreate((current) => !current)}>
            <Plus size={17} /> Novo projeto
          </Button>
        ) : null}
      </div>
      {showCreate ? (
        <Card className="project-create">
          <label>
            Nome do projeto
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            Prazo
            <input
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
            />
          </label>
          <label className="project-create__description">
            Objetivo
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <Button
            disabled={name.trim().length < 2}
            loading={createProject.isPending}
            onClick={() => createProject.mutate()}
          >
            Criar projeto
          </Button>
        </Card>
      ) : null}
      <section className="projects-workspace">
        <aside className="project-list" aria-label="Lista de projetos">
          {projects.isLoading ? (
            <p className="projects-empty">Carregando projetos...</p>
          ) : projects.data?.length ? (
            projects.data.map((project) => (
              <button
                className={`project-list__item ${project.id === selectedId ? "project-list__item--active" : ""}`}
                key={project.id}
                onClick={() => setSelectedId(project.id)}
                type="button"
              >
                <span className="project-list__icon">
                  <FolderKanban size={18} />
                </span>
                <span>
                  <strong>{project.name}</strong>
                  <small>
                    {statusLabels[project.status]} · {project.progress_percent}%
                  </small>
                </span>
                <span className="project-list__progress">
                  <i style={{ width: `${project.progress_percent}%` }} />
                </span>
              </button>
            ))
          ) : (
            <div className="projects-empty">
              <FolderKanban size={30} />
              <p>
                Crie o primeiro projeto para começar a organizar as entregas.
              </p>
            </div>
          )}
        </aside>
        <Card className="project-detail">
          {selected ? (
            <>
              <div className="project-detail__heading">
                <div>
                  <span
                    className={`project-status project-status--${selected.status}`}
                  >
                    {statusLabels[selected.status]}
                  </span>
                  <h2>{selected.name}</h2>
                  <p>{selected.description || "Sem descrição informada."}</p>
                </div>
                {canDelete ? (
                  <button
                    className="project-danger"
                    onClick={() => archiveProject.mutate(selected.id)}
                    type="button"
                  >
                    <Trash2 size={16} /> Arquivar
                  </button>
                ) : null}
              </div>
              <div className="project-metrics">
                <article>
                  <CalendarDays size={18} />
                  <span>
                    <small>Prazo</small>
                    <strong>{formatDate(selected.due_date)}</strong>
                  </span>
                </article>
                <article>
                  <CheckCircle2 size={18} />
                  <span>
                    <small>Progresso</small>
                    <strong>
                      {selected.task_done} de {selected.task_total} tarefas
                    </strong>
                  </span>
                </article>
              </div>
              {canUpdate ? (
                <div className="project-status-actions">
                  <button
                    onClick={() =>
                      updateProject.mutate({
                        id: selected.id,
                        status: "active",
                      })
                    }
                    type="button"
                  >
                    <Circle size={15} /> Iniciar
                  </button>
                  <button
                    onClick={() =>
                      updateProject.mutate({
                        id: selected.id,
                        status: "on_hold",
                      })
                    }
                    type="button"
                  >
                    <PauseCircle size={15} /> Pausar
                  </button>
                  <button
                    onClick={() =>
                      updateProject.mutate({
                        id: selected.id,
                        status: "completed",
                      })
                    }
                    type="button"
                  >
                    <CheckCircle2 size={15} /> Concluir
                  </button>
                </div>
              ) : null}
              <div className="task-heading">
                <div>
                  <span className="eyebrow">Plano de ação</span>
                  <h3>Tarefas</h3>
                </div>
              </div>
              {canManageTasks ? (
                <form
                  className="task-create"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (taskTitle.trim().length >= 2) createTask.mutate();
                  }}
                >
                  <input
                    placeholder="Adicionar uma tarefa..."
                    value={taskTitle}
                    onChange={(event) => setTaskTitle(event.target.value)}
                  />
                  <Button
                    disabled={taskTitle.trim().length < 2}
                    loading={createTask.isPending}
                    type="submit"
                  >
                    Adicionar
                  </Button>
                </form>
              ) : null}
              <div className="task-list">
                {tasks.isLoading ? (
                  <p className="projects-empty">Carregando tarefas...</p>
                ) : tasks.data?.length ? (
                  tasks.data.map((task) => (
                    <article
                      className={`task-row task-row--${task.status}`}
                      key={task.id}
                    >
                      <button
                        aria-label={
                          task.status === "done"
                            ? "Reabrir tarefa"
                            : "Concluir tarefa"
                        }
                        disabled={!canManageTasks}
                        onClick={() =>
                          updateTask.mutate({
                            taskId: task.id,
                            status: task.status === "done" ? "todo" : "done",
                          })
                        }
                        type="button"
                      >
                        {task.status === "done" ? (
                          <CheckCircle2 size={20} />
                        ) : (
                          <Circle size={20} />
                        )}
                      </button>
                      <span>
                        <strong>{task.title}</strong>
                        <small>{taskStatusLabels[task.status]}</small>
                      </span>
                      {canManageTasks ? (
                        <button
                          aria-label={`Excluir ${task.title}`}
                          onClick={() => deleteTask.mutate(task.id)}
                          type="button"
                        >
                          <Trash2 size={16} />
                        </button>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <p className="projects-empty">
                    Nenhuma tarefa cadastrada neste projeto.
                  </p>
                )}
              </div>
            </>
          ) : (
            <div className="projects-empty projects-empty--detail">
              <FolderKanban size={34} />
              <p>Selecione um projeto para ver os detalhes.</p>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}

import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Copy, Download, History, Play, Power, RefreshCw, Upload, Webhook, Workflow } from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  type WorkflowCreatedResponse,
  type WorkflowEngineStatus,
  type WorkflowExecutionResponse,
  type WorkflowResponse,
  useWorkflows,
} from "../workflows/useWorkflows";

function message(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function WorkflowsPage() {
  const queryClient = useQueryClient();
  const workflows = useWorkflows();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [input, setInput] = useState("{}");
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const selected = workflows.data?.find((workflow) => workflow.id === selectedId);

  useEffect(() => {
    if (!selectedId && workflows.data?.[0]) setSelectedId(workflows.data[0].id);
  }, [selectedId, workflows.data]);

  const engine = useQuery({
    queryKey: ["workflow-engine-status"],
    queryFn: () => request<WorkflowEngineStatus>("/workflows/engine/status"),
  });
  const executions = useQuery({
    queryKey: ["workflow-executions", selectedId],
    queryFn: () => request<WorkflowExecutionResponse[]>(`/workflows/${selectedId}/executions`),
    enabled: Boolean(selectedId),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["workflows"] });
    void queryClient.invalidateQueries({ queryKey: ["workflow-executions", selectedId] });
  };

  const create = useMutation({
    mutationFn: () => request<WorkflowCreatedResponse>("/workflows", { method: "POST", body: { name, description: description || null } }),
    onSuccess: (workflow) => {
      setName("");
      setDescription("");
      setNewSecret(workflow.webhook_secret);
      setSelectedId(workflow.id);
      refresh();
    },
  });
  const action = useMutation({
    mutationFn: ({ workflow, command }: { workflow: WorkflowResponse; command: "activate" | "deactivate" | "sync" }) =>
      request<WorkflowResponse>(`/workflows/${workflow.id}/${command}`, { method: "POST" }),
    onSuccess: refresh,
  });
  const execute = useMutation({
    mutationFn: (workflow: WorkflowResponse) => request<WorkflowExecutionResponse>(`/workflows/${workflow.id}/execute`, { method: "POST", body: { input: JSON.parse(input) as Record<string, unknown> }, timeoutMs: 30_000 }),
    onSuccess: refresh,
  });
  const duplicate = useMutation({
    mutationFn: (workflow: WorkflowResponse) => request<WorkflowCreatedResponse>(`/workflows/${workflow.id}/duplicate`, { method: "POST" }),
    onSuccess: (workflow) => {
      setSelectedId(workflow.id);
      setNewSecret(workflow.webhook_secret);
      refresh();
    },
  });
  const rotateSecret = useMutation({
    mutationFn: (workflow: WorkflowResponse) => request<{ webhook_url: string; webhook_secret: string }>(`/workflows/${workflow.id}/webhook-secret`, { method: "POST" }),
    onSuccess: (result) => setNewSecret(result.webhook_secret),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const content = JSON.parse(await file.text()) as { name: string; description?: string | null; definition: Record<string, unknown> };
    const result = await request<WorkflowCreatedResponse>("/workflows/import", { method: "POST", body: content });
    setSelectedId(result.id);
    setNewSecret(result.webhook_secret);
    refresh();
    event.target.value = "";
  };

  const exportWorkflow = async (workflow: WorkflowResponse) => {
    const exported = await request<Record<string, unknown>>(`/workflows/${workflow.id}/export`);
    const url = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${workflow.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.orkestral.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const activeCount = useMemo(() => workflows.data?.filter((item) => item.status === "active").length ?? 0, [workflows.data]);

  return (
    <div className="management-page workflow-page">
      <div className="dashboard__heading">
        <div><span className="eyebrow">Fase 6 · Motor interno protegido</span><h1>Automações</h1><p>Crie, publique e acompanhe fluxos sem sair da Orkestral.</p></div>
        <div className="workflow-summary"><Activity size={18} /><strong>{activeCount}</strong><span>ativas</span></div>
      </div>
      {engine.data ? <Alert variant={engine.data.available ? "success" : "error"}>{engine.data.message}</Alert> : null}
      {create.isError || action.isError || execute.isError || duplicate.isError ? (
        <Alert variant="error">{message(create.error ?? action.error ?? execute.error ?? duplicate.error, "A operação não pôde ser concluída.")}</Alert>
      ) : null}
      {newSecret ? (
        <Alert variant="success">Segredo do webhook: <code>{newSecret}</code> <Button onClick={() => void navigator.clipboard.writeText(newSecret)} variant="ghost">Copiar</Button></Alert>
      ) : null}

      <div className="workflow-toolbar">
        <PermissionGuard all={["workflows.configure"]}>
          <Card className="workflow-create" eyebrow="Nova automação" title="Comece com uma entrada segura">
            <form className="stack-form" onSubmit={submit}>
              <TextField label="Nome" onChange={(event) => setName(event.target.value)} required value={name} />
              <TextField label="Descrição" onChange={(event) => setDescription(event.target.value)} value={description} />
              <Button loading={create.isPending} type="submit"><Workflow size={17} /> Criar automação</Button>
            </form>
          </Card>
          <Card className="workflow-import" eyebrow="Definição segura" title="Importar arquivo Orkestral">
            <p>Somente blocos permitidos e sem credenciais incorporadas são aceitos.</p>
            <label className="ui-button ui-button--secondary file-button"><Upload size={17} /> Importar JSON<input accept="application/json,.json" hidden onChange={(event) => void importFile(event)} type="file" /></label>
          </Card>
        </PermissionGuard>
      </div>

      <div className="workflow-layout">
        <Card className="workflow-list" eyebrow="Catálogo da empresa" title="Fluxos">
          {workflows.isLoading ? <p>Carregando automações…</p> : null}
          {workflows.data?.length === 0 ? <div className="empty-state"><Workflow /><strong>Nenhuma automação</strong><span>Crie o primeiro fluxo da empresa.</span></div> : null}
          {workflows.data?.map((workflow) => (
            <button className={`workflow-row ${selectedId === workflow.id ? "workflow-row--active" : ""}`} key={workflow.id} onClick={() => setSelectedId(workflow.id)} type="button">
              <span className="workflow-row__icon"><Workflow size={18} /></span>
              <span><strong>{workflow.name}</strong><small>v{workflow.version} · {workflow.sync_status === "synced" ? "sincronizada" : "aguardando sincronização"}</small></span>
              <span className={`status-chip status-chip--${workflow.status === "active" ? "active" : "inactive"}`}>{workflow.status}</span>
            </button>
          ))}
        </Card>

        {selected ? (
          <div className="workflow-detail">
            <Card eyebrow="Operação" title={selected.name}>
              <p>{selected.description || "Automação sem descrição."}</p>
              {selected.last_error ? <Alert variant="error">{selected.last_error}</Alert> : null}
              <div className="workflow-webhook"><Webhook size={18} /><code>{selected.webhook_url}</code></div>
              <div className="form-actions">
                <PermissionGuard all={["workflows.configure"]}>
                  {selected.sync_status !== "synced" ? <Button loading={action.isPending} onClick={() => action.mutate({ workflow: selected, command: "sync" })} variant="secondary"><RefreshCw size={16} /> Sincronizar</Button> : null}
                  <Button loading={action.isPending} onClick={() => action.mutate({ workflow: selected, command: selected.status === "active" ? "deactivate" : "activate" })} variant={selected.status === "active" ? "ghost" : "primary"}><Power size={16} /> {selected.status === "active" ? "Desativar" : "Ativar"}</Button>
                  <Button loading={duplicate.isPending} onClick={() => duplicate.mutate(selected)} variant="secondary"><Copy size={16} /> Duplicar</Button>
                  <Button onClick={() => void exportWorkflow(selected)} variant="ghost"><Download size={16} /> Exportar</Button>
                  <Button loading={rotateSecret.isPending} onClick={() => rotateSecret.mutate(selected)} variant="ghost"><Webhook size={16} /> Novo segredo</Button>
                </PermissionGuard>
              </div>
            </Card>
            <PermissionGuard all={["workflows.execute"]}>
              <Card eyebrow="Execução manual" title="Enviar entrada de teste">
                <label className="native-field"><span>Entrada JSON</span><textarea onChange={(event) => setInput(event.target.value)} rows={5} value={input} /></label>
                <Button disabled={selected.status !== "active"} loading={execute.isPending} onClick={() => execute.mutate(selected)}><Play size={17} /> Executar agora</Button>
              </Card>
            </PermissionGuard>
            <Card className="workflow-history" eyebrow="Observabilidade" title="Histórico de execuções">
              {executions.data?.length === 0 ? <div className="empty-state"><History /><span>Nenhuma execução registrada.</span></div> : null}
              {executions.data?.map((execution) => (
                <div className="execution-row" key={execution.id}>
                  <span className={`status-chip status-chip--${execution.status === "success" ? "active" : execution.status === "error" ? "disabled" : "inactive"}`}>{execution.status}</span>
                  <div><strong>{execution.source === "manual" ? "Execução manual" : "Webhook externo"}</strong><small>{new Date(execution.created_at).toLocaleString("pt-BR")} · {execution.duration_ms ?? 0} ms</small>{execution.error_summary ? <small>{execution.error_summary}</small> : null}</div>
                </div>
              ))}
            </Card>
          </div>
        ) : null}
      </div>
    </div>
  );
}

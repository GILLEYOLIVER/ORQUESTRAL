import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  Braces,
  CheckCircle2,
  Copy,
  FlaskConical,
  GitCompareArrows,
  History,
  Play,
  Plus,
  Power,
  Rocket,
  RotateCcw,
  Save,
  Trash2,
  Workflow,
  XCircle,
} from "lucide-react";
import { Alert, Button, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  type WorkflowBlock,
  type WorkflowComparison,
  type WorkflowCreatedResponse,
  type WorkflowDefinition,
  type WorkflowExecutionPolicy,
  type WorkflowEngineStatus,
  type WorkflowExecutionResponse,
  type WorkflowResponse,
  type WorkflowSimulationResponse,
  type WorkflowValidationResponse,
  type WorkflowVersion,
  useWorkflows,
  type EventContractOption,
} from "../workflows/useWorkflows";
import "../workflows/builder.css";

type VisualNodeData = {
  label: string;
  blockType: string;
  config: Record<string, unknown>;
  category: string;
};
type VisualNode = Node<VisualNodeData, "orkestral">;

const categoryTone: Record<string, string> = {
  Gatilhos: "sun",
  Logica: "blue",
  Dados: "green",
  Acoes: "orange",
  Inteligencia: "ink",
  Fluxo: "red",
};

function VisualBlock({ data, selected }: NodeProps<VisualNode>) {
  const isTrigger = data.blockType.startsWith("trigger.");
  const isEnd = data.blockType === "flow.end";
  const isCondition = data.blockType === "logic.condition";
  return (
    <div
      className={`visual-block visual-block--${categoryTone[data.category] ?? "ink"} ${selected ? "is-selected" : ""}`}
    >
      {!isTrigger ? <Handle position={Position.Left} type="target" /> : null}
      <span>{data.category}</span>
      <strong>{data.label}</strong>
      <small>{data.blockType}</small>
      {!isEnd && !isCondition ? (
        <Handle id="main" position={Position.Right} type="source" />
      ) : null}
      {isCondition ? (
        <>
          <Handle
            id="true"
            position={Position.Right}
            style={{ top: "38%" }}
            type="source"
          />
          <Handle
            id="false"
            position={Position.Right}
            style={{ top: "72%" }}
            type="source"
          />
        </>
      ) : null}
    </div>
  );
}

const nodeTypes = { orkestral: VisualBlock };
const defaultExecutionPolicy: WorkflowExecutionPolicy = {
  max_steps: 100,
  timeout_seconds: 300,
  concurrency_limit: 1,
  on_conflict: "reject",
};

function errorMessage(
  error: unknown,
  fallback = "A operacao nao pode ser concluida.",
) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function WorkflowsPage() {
  const queryClient = useQueryClient();
  const workflows = useWorkflows();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [input, setInput] = useState("{}");
  const [changeSummary, setChangeSummary] = useState(
    "Ajustes no canvas visual",
  );
  const [configDraft, setConfigDraft] = useState("{}");
  const [validation, setValidation] =
    useState<WorkflowValidationResponse | null>(null);
  const [comparison, setComparison] = useState<WorkflowComparison | null>(null);
  const [simulation, setSimulation] =
    useState<WorkflowSimulationResponse | null>(null);
  const [executionPolicy, setExecutionPolicy] =
    useState<WorkflowExecutionPolicy>(defaultExecutionPolicy);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<VisualNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const selected =
    workflows.data?.find((workflow) => workflow.id === selectedId) ?? null;
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null;

  const engine = useQuery({
    queryKey: ["workflow-engine-status"],
    queryFn: () => request<WorkflowEngineStatus>("/workflows/engine/status"),
  });
  const blocks = useQuery({
    queryKey: ["workflow-blocks"],
    queryFn: () => request<WorkflowBlock[]>("/workflows/blocks/catalog"),
  });
  const eventContracts = useQuery({
    queryKey: ["event-contract-options"],
    queryFn: () => request<EventContractOption[]>("/events/contracts"),
  });
  const versions = useQuery({
    queryKey: ["workflow-versions", selectedId],
    queryFn: () =>
      request<WorkflowVersion[]>(`/workflows/${selectedId}/versions`),
    enabled: Boolean(selectedId),
  });
  const executions = useQuery({
    queryKey: ["workflow-executions", selectedId],
    queryFn: () =>
      request<WorkflowExecutionResponse[]>(
        `/workflows/${selectedId}/executions`,
      ),
    enabled: Boolean(selectedId),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!selectedId && workflows.data?.[0]) setSelectedId(workflows.data[0].id);
  }, [selectedId, workflows.data]);

  useEffect(() => {
    if (!selected) return;
    const catalog = new Map(
      blocks.data?.map((item) => [item.type, item]) ?? [],
    );
    setNodes(
      selected.definition.nodes.map((node) => ({
        id: node.id,
        type: "orkestral",
        position: node.position,
        data: {
          label: node.label,
          blockType: node.type,
          config: node.config,
          category: catalog.get(node.type)?.category ?? "Fluxo",
        },
      })),
    );
    setEdges(
      selected.definition.connections.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.source_handle ?? "main",
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
      })),
    );
    setSelectedNodeId(null);
    setValidation(null);
    setSimulation(null);
    setExecutionPolicy(
      selected.definition.execution_policy ?? defaultExecutionPolicy,
    );
    // Rehydrate only when the persisted workflow version changes; query refetches
    // must not overwrite unsaved canvas edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocks.data, selected?.id, selected?.version, setEdges, setNodes]);

  useEffect(() => {
    setConfigDraft(JSON.stringify(selectedNode?.data.config ?? {}, null, 2));
  }, [selectedNodeId, selectedNode?.data.config]);

  const groupedBlocks = useMemo(() => {
    const groups = new Map<string, WorkflowBlock[]>();
    for (const block of blocks.data ?? []) {
      groups.set(block.category, [
        ...(groups.get(block.category) ?? []),
        block,
      ]);
    }
    return [...groups.entries()];
  }, [blocks.data]);

  const definition = (): WorkflowDefinition => ({
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data.blockType,
      label: node.data.label,
      position: {
        x: Math.round(node.position.x),
        y: Math.round(node.position.y),
      },
      config: node.data.config,
    })),
    connections: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      source_handle: edge.sourceHandle ?? "main",
    })),
    variables: selected?.definition.variables ?? {},
    execution_policy: executionPolicy,
    version: 1,
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["workflows"] }),
      queryClient.invalidateQueries({
        queryKey: ["workflow-versions", selectedId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["workflow-executions", selectedId],
      }),
    ]);
  };

  const create = useMutation({
    mutationFn: () =>
      request<WorkflowCreatedResponse>("/workflows", {
        method: "POST",
        body: { name, description: description || null },
      }),
    onSuccess: async (workflow) => {
      setName("");
      setDescription("");
      setSelectedId(workflow.id);
      setFeedback(
        "Rascunho criado. Monte o fluxo no canvas antes de publicar.",
      );
      await refresh();
    },
  });
  const saveDraft = useMutation({
    mutationFn: () =>
      request<WorkflowResponse>(`/workflows/${selectedId}`, {
        method: "PATCH",
        body: { definition: definition(), change_summary: changeSummary },
      }),
    onSuccess: async () => {
      setFeedback("Rascunho salvo e nova versao registrada.");
      await refresh();
    },
  });
  const validate = useMutation({
    mutationFn: () =>
      request<WorkflowValidationResponse>(`/workflows/${selectedId}/validate`, {
        method: "POST",
        body: { definition: definition() },
      }),
    onSuccess: (result) => {
      setValidation(result);
      setFeedback(
        result.valid
          ? "Definicao valida e pronta para publicacao."
          : "A validacao encontrou pontos que precisam de ajuste.",
      );
    },
  });
  const publish = useMutation({
    mutationFn: async () => {
      await request<WorkflowResponse>(`/workflows/${selectedId}`, {
        method: "PATCH",
        body: { definition: definition(), change_summary: changeSummary },
      });
      return request<WorkflowResponse>(`/workflows/${selectedId}/publish`, {
        method: "POST",
        timeoutMs: 30_000,
      });
    },
    onSuccess: async () => {
      setValidation(null);
      setFeedback("Fluxo compilado, publicado e ativado no n8n.");
      await refresh();
    },
  });
  const deactivate = useMutation({
    mutationFn: () =>
      request<WorkflowResponse>(`/workflows/${selectedId}/deactivate`, {
        method: "POST",
      }),
    onSuccess: refresh,
  });
  const duplicate = useMutation({
    mutationFn: () =>
      request<WorkflowCreatedResponse>(`/workflows/${selectedId}/duplicate`, {
        method: "POST",
      }),
    onSuccess: async (workflow) => {
      setSelectedId(workflow.id);
      await refresh();
    },
  });
  const restore = useMutation({
    mutationFn: (version: number) =>
      request<WorkflowResponse>(
        `/workflows/${selectedId}/versions/${version}/restore`,
        { method: "POST" },
      ),
    onSuccess: async () => {
      setFeedback("Versao restaurada como um novo rascunho.");
      await refresh();
    },
  });
  const compare = useMutation({
    mutationFn: ({ from, to }: { from: number; to: number }) =>
      request<WorkflowComparison>(
        `/workflows/${selectedId}/versions/compare?from_version=${from}&to_version=${to}`,
      ),
    onSuccess: setComparison,
  });
  const execute = useMutation({
    mutationFn: () =>
      request<WorkflowExecutionResponse>(`/workflows/${selectedId}/execute`, {
        method: "POST",
        body: { input: JSON.parse(input) as Record<string, unknown> },
        timeoutMs: 30_000,
      }),
    onSuccess: refresh,
  });
  const simulate = useMutation({
    mutationFn: () =>
      request<WorkflowSimulationResponse>(`/workflows/${selectedId}/simulate`, {
        method: "POST",
        body: {
          definition: definition(),
          input: JSON.parse(input) as Record<string, unknown>,
        },
      }),
    onSuccess: (result) => {
      setSimulation(result);
      setFeedback(
        result.valid
          ? "Simulacao concluida sem executar efeitos externos."
          : "A simulacao encontrou bloqueios antes da publicacao.",
      );
    },
  });

  function addBlock(block: WorkflowBlock) {
    const id = crypto.randomUUID();
    setNodes((current) => [
      ...current,
      {
        id,
        type: "orkestral",
        position: {
          x: 180 + current.length * 36,
          y: 100 + current.length * 28,
        },
        data: {
          label: block.label,
          blockType: block.type,
          config: structuredClone(block.defaults),
          category: block.category,
        },
      },
    ]);
    setSelectedNodeId(id);
    setValidation(null);
  }

  function connect(connection: Connection) {
    setEdges((current) =>
      addEdge(
        {
          ...connection,
          id: crypto.randomUUID(),
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
        },
        current,
      ),
    );
    setValidation(null);
  }

  function updateNode(patch: Partial<VisualNodeData>) {
    if (!selectedNodeId) return;
    setNodes((current) =>
      current.map((node) =>
        node.id === selectedNodeId
          ? { ...node, data: { ...node.data, ...patch } }
          : node,
      ),
    );
    setValidation(null);
  }

  function applyConfig() {
    try {
      const parsed = JSON.parse(configDraft) as Record<string, unknown>;
      updateNode({ config: parsed });
      setFeedback("Configuracao do bloco aplicada ao canvas.");
    } catch {
      setFeedback("A configuracao precisa ser um JSON valido.");
    }
  }

  function removeSelectedNode() {
    if (!selectedNodeId) return;
    setNodes((current) => current.filter((node) => node.id !== selectedNodeId));
    setEdges((current) =>
      current.filter(
        (edge) =>
          edge.source !== selectedNodeId && edge.target !== selectedNodeId,
      ),
    );
    setSelectedNodeId(null);
  }

  const submitCreate = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const activeCount =
    workflows.data?.filter((item) => item.status === "active").length ?? 0;
  const latestVersions = versions.data?.slice(0, 2) ?? [];
  const operationError =
    create.error ??
    saveDraft.error ??
    validate.error ??
    publish.error ??
    deactivate.error ??
    duplicate.error ??
    restore.error ??
    compare.error ??
    simulate.error ??
    execute.error;

  return (
    <div className="visual-workflow-page">
      <header className="visual-workflow-hero">
        <div>
          <span>Estúdio de automações</span>
          <h1>
            Desenhe a operacao.
            <br />A Orkestral cuida do motor.
          </h1>
          <p>
            Monte blocos, valide riscos e publique no n8n sem sair do sistema.
          </p>
        </div>
        <div className="visual-workflow-score">
          <Activity size={24} />
          <strong>{activeCount}</strong>
          <small>fluxos ativos</small>
        </div>
      </header>

      {engine.data ? (
        <Alert variant={engine.data.available ? "success" : "error"}>
          {engine.data.message}
        </Alert>
      ) : null}
      {feedback ? <div className="visual-feedback">{feedback}</div> : null}
      {operationError ? (
        <Alert variant="error">{errorMessage(operationError)}</Alert>
      ) : null}

      <section className="visual-create-bar">
        <form onSubmit={submitCreate}>
          <TextField
            label="Nome da automacao"
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
          <TextField
            label="Descricao"
            onChange={(event) => setDescription(event.target.value)}
            value={description}
          />
          <Button loading={create.isPending} type="submit">
            <Plus size={17} /> Novo rascunho
          </Button>
        </form>
      </section>

      <section className="visual-studio">
        <aside className="visual-sidebar">
          <div className="visual-section-title">
            <span>01</span>
            <h2>Fluxos</h2>
          </div>
          <div className="visual-workflow-list">
            {workflows.data?.map((workflow) => (
              <button
                className={workflow.id === selectedId ? "is-active" : ""}
                key={workflow.id}
                onClick={() => setSelectedId(workflow.id)}
                type="button"
              >
                <Workflow size={17} />
                <span>
                  <strong>{workflow.name}</strong>
                  <small>
                    v{workflow.version} · {workflow.status}
                  </small>
                </span>
              </button>
            ))}
          </div>
          <div className="visual-section-title visual-section-title--palette">
            <span>02</span>
            <h2>Blocos</h2>
          </div>
          <div className="visual-palette">
            {groupedBlocks.map(([category, items]) => (
              <div key={category}>
                <strong>{category}</strong>
                {items.map((block) => (
                  <button
                    key={block.type}
                    onClick={() => addBlock(block)}
                    title={block.description}
                    type="button"
                  >
                    <Plus size={13} /> {block.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </aside>

        <div className="visual-canvas-shell">
          <div className="visual-canvas-toolbar">
            <div>
              <strong>{selected?.name ?? "Selecione um fluxo"}</strong>
              <small>
                {nodes.length} blocos · {edges.length} conexoes
              </small>
            </div>
            <PermissionGuard all={["workflows.configure"]}>
              <input
                aria-label="Resumo da alteracao"
                onChange={(event) => setChangeSummary(event.target.value)}
                value={changeSummary}
              />
              <Button
                disabled={!selected}
                loading={saveDraft.isPending}
                onClick={() => saveDraft.mutate()}
                variant="secondary"
              >
                <Save size={16} /> Salvar
              </Button>
              <Button
                disabled={!selected}
                loading={validate.isPending}
                onClick={() => validate.mutate()}
                variant="secondary"
              >
                <CheckCircle2 size={16} /> Validar
              </Button>
              <Button
                disabled={!selected}
                loading={publish.isPending}
                onClick={() => publish.mutate()}
              >
                <Rocket size={16} /> Publicar
              </Button>
            </PermissionGuard>
          </div>
          <div className="visual-canvas">
            {selected ? (
              <ReactFlow
                edges={edges}
                fitView
                nodeTypes={nodeTypes}
                nodes={nodes}
                onConnect={connect}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
                onNodesChange={onNodesChange}
              >
                <Background color="#c9c2ab" gap={24} size={1.2} />
                <Controls />
                <MiniMap nodeColor="#315b44" pannable zoomable />
              </ReactFlow>
            ) : (
              <div className="visual-empty">
                <Workflow size={42} />
                <strong>Escolha ou crie uma automacao</strong>
              </div>
            )}
          </div>
        </div>

        <aside className="visual-inspector">
          <div className="visual-section-title">
            <span>03</span>
            <h2>Inspector</h2>
          </div>
          {selectedNode ? (
            <div className="visual-inspector-form">
              <label>
                Nome do bloco
                <input
                  onChange={(event) =>
                    updateNode({ label: event.target.value })
                  }
                  value={selectedNode.data.label}
                />
              </label>
              <label>
                Tipo
                <input disabled value={selectedNode.data.blockType} />
              </label>
              {selectedNode.data.blockType === "trigger.domain_event" ? (
                <>
                  <label>
                    Evento publicado
                    <input
                      list="published-event-contracts"
                      onChange={(event) =>
                        updateNode({
                          config: {
                            ...selectedNode.data.config,
                            event_type: event.target.value,
                          },
                        })
                      }
                      value={String(selectedNode.data.config.event_type ?? "")}
                    />
                    <datalist id="published-event-contracts">
                      {eventContracts.data
                        ?.filter((contract) => contract.status === "published")
                        .map((contract) => (
                          <option key={contract.id} value={contract.event_type}>
                            versao {contract.version}
                          </option>
                        ))}
                    </datalist>
                  </label>
                  <label>
                    Versao do contrato
                    <input
                      min={1}
                      onChange={(event) =>
                        updateNode({
                          config: {
                            ...selectedNode.data.config,
                            event_version: Number(event.target.value),
                          },
                        })
                      }
                      type="number"
                      value={Number(
                        selectedNode.data.config.event_version ?? 1,
                      )}
                    />
                  </label>
                </>
              ) : null}
              <label>
                Configuracao JSON
                <textarea
                  onChange={(event) => setConfigDraft(event.target.value)}
                  rows={12}
                  value={configDraft}
                />
              </label>
              <button onClick={applyConfig} type="button">
                <Braces size={15} /> Aplicar configuracao
              </button>
              <button
                className="is-danger"
                onClick={removeSelectedNode}
                type="button"
              >
                <Trash2 size={15} /> Remover bloco
              </button>
            </div>
          ) : (
            <p className="visual-muted">
              Selecione um bloco para editar nome e configuracao.
            </p>
          )}
          {validation ? (
            <div className="visual-validation">
              <strong>
                {validation.valid ? <CheckCircle2 /> : <XCircle />}{" "}
                {validation.valid ? "Fluxo valido" : "Ajustes necessarios"}
              </strong>
              {validation.issues.map((issue, index) => (
                <button
                  key={`${issue.code}-${index}`}
                  onClick={() =>
                    issue.node_id && setSelectedNodeId(issue.node_id)
                  }
                  type="button"
                >
                  <span>{issue.severity}</span>
                  {issue.message}
                </button>
              ))}
            </div>
          ) : null}
        </aside>
      </section>

      {selected ? (
        <section className="visual-operations">
          <article>
            <div className="visual-section-title">
              <span>04</span>
              <h2>Versoes</h2>
            </div>
            <div className="visual-version-actions">
              <Button
                disabled={latestVersions.length < 2}
                loading={compare.isPending}
                onClick={() =>
                  latestVersions.length >= 2 &&
                  compare.mutate({
                    from: latestVersions[1].version,
                    to: latestVersions[0].version,
                  })
                }
                variant="secondary"
              >
                <GitCompareArrows size={16} /> Comparar ultimas
              </Button>
              <Button
                loading={duplicate.isPending}
                onClick={() => duplicate.mutate()}
                variant="secondary"
              >
                <Copy size={16} /> Duplicar
              </Button>
              {selected.status === "active" ? (
                <Button
                  loading={deactivate.isPending}
                  onClick={() => deactivate.mutate()}
                  variant="ghost"
                >
                  <Power size={16} /> Desativar
                </Button>
              ) : null}
            </div>
            {comparison ? (
              <div className="visual-comparison">
                v{comparison.from_version} → v{comparison.to_version}:{" "}
                {comparison.added_nodes.length} adicionados,{" "}
                {comparison.removed_nodes.length} removidos,{" "}
                {comparison.changed_nodes.length} alterados.
              </div>
            ) : null}
            <div className="visual-version-list">
              {versions.data?.map((version) => (
                <div key={version.id}>
                  <History size={17} />
                  <span>
                    <strong>Versao {version.version}</strong>
                    <small>
                      {version.change_summary || "Sem resumo"} ·{" "}
                      {new Date(version.created_at).toLocaleString("pt-BR")}
                    </small>
                  </span>
                  <button
                    disabled={version.version === selected.version}
                    onClick={() => restore.mutate(version.version)}
                    title="Restaurar"
                    type="button"
                  >
                    <RotateCcw size={15} />
                  </button>
                </div>
              ))}
            </div>
          </article>

          <article>
            <div className="visual-section-title">
              <span>05</span>
              <h2>Execucoes</h2>
            </div>
            <PermissionGuard all={["workflows.execute"]}>
              <div className="visual-execute">
                <textarea
                  onChange={(event) => setInput(event.target.value)}
                  rows={3}
                  value={input}
                />
                <Button
                  disabled={selected.status !== "active"}
                  loading={execute.isPending}
                  onClick={() => execute.mutate()}
                >
                  <Play size={16} /> Executar
                </Button>
              </div>
            </PermissionGuard>
            <div className="visual-execution-list">
              {executions.data?.map((execution) => (
                <div key={execution.id}>
                  <span
                    className={`visual-dot visual-dot--${execution.status}`}
                  />
                  <span>
                    <strong>{execution.status}</strong>
                    <small>
                      {execution.source} ·{" "}
                      {new Date(execution.created_at).toLocaleString("pt-BR")} ·{" "}
                      {execution.duration_ms ?? 0} ms
                    </small>
                  </span>
                  {execution.error_summary ? (
                    <em>{execution.error_summary}</em>
                  ) : null}
                </div>
              ))}
            </div>
          </article>
          <article className="visual-simulation-panel">
            <div className="visual-section-title">
              <span>06</span>
              <h2>Simulacao e limites</h2>
            </div>
            <p className="visual-muted">
              Teste o caminho inteiro sem enviar mensagens, alterar dados ou
              chamar sistemas externos.
            </p>
            <div className="visual-policy-grid">
              <label>
                Limite de etapas
                <input
                  min={2}
                  max={1000}
                  onChange={(event) =>
                    setExecutionPolicy((current) => ({
                      ...current,
                      max_steps: Number(event.target.value),
                    }))
                  }
                  type="number"
                  value={executionPolicy.max_steps}
                />
              </label>
              <label>
                Tempo maximo (segundos)
                <input
                  min={5}
                  max={3600}
                  onChange={(event) =>
                    setExecutionPolicy((current) => ({
                      ...current,
                      timeout_seconds: Number(event.target.value),
                    }))
                  }
                  type="number"
                  value={executionPolicy.timeout_seconds}
                />
              </label>
              <label>
                Execucoes simultaneas
                <input
                  min={1}
                  max={50}
                  onChange={(event) =>
                    setExecutionPolicy((current) => ({
                      ...current,
                      concurrency_limit: Number(event.target.value),
                    }))
                  }
                  type="number"
                  value={executionPolicy.concurrency_limit}
                />
              </label>
            </div>
            <div className="visual-simulation-actions">
              <textarea
                aria-label="Dados de teste da simulacao"
                onChange={(event) => setInput(event.target.value)}
                rows={4}
                value={input}
              />
              <Button
                loading={simulate.isPending}
                onClick={() => simulate.mutate()}
                variant="secondary"
              >
                <FlaskConical size={16} /> Simular sem executar
              </Button>
            </div>
            {simulation ? (
              <div className="visual-simulation-result">
                <strong>
                  {simulation.valid
                    ? "Simulacao aprovada"
                    : "Simulacao bloqueada"}
                </strong>
                <small>
                  {simulation.estimated_steps} etapas analisadas ·{" "}
                  {simulation.blocked_side_effects} efeitos bloqueados
                </small>
                <div className="visual-simulation-trace">
                  {simulation.trace.map((step) => (
                    <div key={step.node_id}>
                      <span
                        className={`visual-trace-status visual-trace-status--${step.status}`}
                      />
                      <span>
                        <strong>{step.label}</strong>
                        <small>{step.detail}</small>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
        </section>
      ) : null}
    </div>
  );
}

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Check,
  Gauge,
  LockKeyhole,
  MessageSquare,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import {
  type AgentChatResponse,
  type AgentApprovalPolicyEvaluationResponse,
  type AgentApprovalPolicyResponse,
  type AgentMessageResponse,
  type AgentResponse,
  type AgentToolCatalog,
  type AgentToolResponse,
  type AgentToolRunResponse,
  type AgentUsageResponse,
  useAgents,
} from "../agents/useAgents";
import "../agents/agents.css";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "A operação do agente não pôde ser concluída.";
}

function parseContextValue(value: string): string | number | boolean | null {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (
      parsed === null ||
      typeof parsed === "string" ||
      typeof parsed === "number" ||
      typeof parsed === "boolean"
    ) {
      return parsed;
    }
  } catch {
    return trimmed;
  }
  return trimmed;
}

function parseArguments(value: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Os argumentos devem formar um objeto JSON.");
  }
  return parsed as Record<string, unknown>;
}

interface CompanyUserOption {
  user_id: string;
  name: string;
  email: string;
  user_status: string;
  membership_status: string;
}

interface ApprovalStageDraft {
  id: string;
  name: string;
  quorum: string;
  approverUserIds: string[];
}

export function AgentsPage() {
  const queryClient = useQueryClient();
  const { me } = useSession();
  const agents = useAgents();
  const canConfigure = me?.permissions.includes("agents.configure") ?? false;
  const canExecute = me?.permissions.includes("agents.execute") ?? false;
  const canViewUsers = me?.permissions.includes("users.view") ?? false;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState(
    "Ajude a equipe com respostas claras e use apenas ferramentas autorizadas.",
  );
  const [provider, setProvider] = useState<"local" | "openai_compatible">(
    "local",
  );
  const [model, setModel] = useState("orkestral-local");
  const [message, setMessage] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [policyName, setPolicyName] = useState("Operação supervisionada");
  const [policyKey, setPolicyKey] = useState("operacao.supervisionada");
  const [policyEffect, setPolicyEffect] = useState<
    "allow" | "require_approval" | "deny"
  >("require_approval");
  const [policyPriority, setPolicyPriority] = useState("500");
  const [policyToolKey, setPolicyToolKey] = useState("");
  const [policyAmountField, setPolicyAmountField] = useState("");
  const [policyMinAmount, setPolicyMinAmount] = useState("");
  const [policyMaxAmount, setPolicyMaxAmount] = useState("");
  const [policyCurrency, setPolicyCurrency] = useState("");
  const [policyContextPath, setPolicyContextPath] = useState("");
  const [policyContextValue, setPolicyContextValue] = useState("");
  const [policyApprovalTtl, setPolicyApprovalTtl] = useState("60");
  const [policyEffectiveFrom, setPolicyEffectiveFrom] = useState("");
  const [policyEffectiveUntil, setPolicyEffectiveUntil] = useState("");
  const [policyAssignedUserId, setPolicyAssignedUserId] = useState("");
  const [policyEscalationUserId, setPolicyEscalationUserId] = useState("");
  const [policyEscalationAfter, setPolicyEscalationAfter] = useState("30");
  const [policyStages, setPolicyStages] = useState<ApprovalStageDraft[]>([]);
  const [simulationToolKey, setSimulationToolKey] = useState("");
  const [simulationArguments, setSimulationArguments] = useState("{}");
  const [policyDecision, setPolicyDecision] =
    useState<AgentApprovalPolicyEvaluationResponse | null>(null);
  const [policyFormError, setPolicyFormError] = useState<string | null>(null);
  const selected = agents.data?.find((agent) => agent.id === selectedId);

  useEffect(() => {
    if (!agents.data?.length) {
      if (selectedId) setSelectedId(null);
      return;
    }
    if (!selectedId || !agents.data.some((agent) => agent.id === selectedId)) {
      setSelectedId(agents.data[0].id);
    }
  }, [agents.data, selectedId]);
  useEffect(() => {
    setConversationId(null);
  }, [selectedId]);
  const catalog = useQuery({
    queryKey: ["agent-tools-catalog"],
    queryFn: () => request<AgentToolCatalog[]>("/agents/tools/catalog"),
    enabled: canConfigure,
  });
  const tools = useQuery({
    queryKey: ["agent-tools", selectedId],
    queryFn: () => request<AgentToolResponse[]>(`/agents/${selectedId}/tools`),
    enabled: Boolean(selectedId),
  });
  const policies = useQuery({
    queryKey: ["agent-approval-policies", selectedId],
    queryFn: () =>
      request<AgentApprovalPolicyResponse[]>(
        `/agents/${selectedId}/approval-policies`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const companyUsers = useQuery({
    queryKey: ["company-users", me?.current_company?.id],
    queryFn: () => request<CompanyUserOption[]>("/company/users"),
    enabled: canConfigure && canViewUsers,
  });
  const messages = useQuery({
    queryKey: ["agent-messages", selectedId, conversationId],
    queryFn: () =>
      request<AgentMessageResponse[]>(
        `/agents/${selectedId}/conversations/${conversationId}/messages`,
      ),
    enabled: Boolean(selectedId && conversationId),
  });
  const pending = useQuery({
    queryKey: ["agent-pending-actions"],
    queryFn: () => request<AgentToolRunResponse[]>("/agents/actions/pending"),
    enabled: canExecute,
  });
  const usage = useQuery({
    queryKey: ["agent-usage"],
    queryFn: () => request<AgentUsageResponse[]>("/agents/usage"),
  });
  useEffect(() => {
    if (tools.data)
      setSelectedTools(
        tools.data.filter((tool) => tool.enabled).map((tool) => tool.tool_key),
      );
  }, [tools.data]);
  useEffect(() => {
    const firstTool = catalog.data?.[0]?.key;
    if (!simulationToolKey && firstTool) setSimulationToolKey(firstTool);
  }, [catalog.data, simulationToolKey]);
  useEffect(() => {
    setPolicyDecision(null);
    setPolicyFormError(null);
  }, [selectedId]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
    void queryClient.invalidateQueries({
      queryKey: ["agent-tools", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-messages", selectedId, conversationId],
    });
    void queryClient.invalidateQueries({ queryKey: ["agent-pending-actions"] });
    void queryClient.invalidateQueries({ queryKey: ["agent-usage"] });
    void queryClient.invalidateQueries({
      queryKey: ["agent-approval-policies", selectedId],
    });
  };
  const create = useMutation({
    mutationFn: () =>
      request<AgentResponse>("/agents", {
        method: "POST",
        body: { name, instructions, provider, model },
      }),
    onSuccess: (agent) => {
      queryClient.setQueriesData<AgentResponse[]>(
        { queryKey: ["agents"] },
        (current) => [
          agent,
          ...(current ?? []).filter((item) => item.id !== agent.id),
        ],
      );
      setSelectedId(agent.id);
      setName("");
      refresh();
    },
  });
  const configureTools = useMutation({
    mutationFn: () =>
      request<AgentToolResponse[]>(`/agents/${selectedId}/tools`, {
        method: "PUT",
        body: { tool_keys: selectedTools },
      }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (agentId: string) =>
      request<void>(`/agents/${agentId}`, { method: "DELETE" }),
    onSuccess: (_, agentId) => {
      queryClient.setQueriesData<AgentResponse[]>(
        { queryKey: ["agents"] },
        (current) => (current ?? []).filter((agent) => agent.id !== agentId),
      );
      setConversationId(null);
      setSelectedId((current) => (current === agentId ? null : current));
      refresh();
    },
  });
  const chat = useMutation({
    mutationFn: () =>
      request<AgentChatResponse>(`/agents/${selectedId}/chat`, {
        method: "POST",
        body: { message, conversation_id: conversationId },
        timeoutMs: 60_000,
      }),
    onSuccess: (response) => {
      setConversationId(response.conversation.id);
      setMessage("");
      refresh();
    },
  });
  const decide = useMutation({
    mutationFn: ({
      action,
      decision,
    }: {
      action: AgentToolRunResponse;
      decision: "approved" | "rejected";
    }) =>
      request<AgentToolRunResponse>(`/agents/actions/${action.id}/decision`, {
        method: "POST",
        body: { decision },
        timeoutMs: 30_000,
      }),
    onSuccess: refresh,
  });
  const createPolicy = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      request<AgentApprovalPolicyResponse>(
        `/agents/${selectedId}/approval-policies`,
        { method: "POST", body },
      ),
    onSuccess: () => {
      setPolicyFormError(null);
      setPolicyDecision(null);
      refresh();
    },
  });
  const publishPolicy = useMutation({
    mutationFn: (policyId: string) =>
      request<AgentApprovalPolicyResponse>(
        `/agents/${selectedId}/approval-policies/${policyId}/publish`,
        { method: "POST" },
      ),
    onSuccess: refresh,
  });
  const evaluatePolicy = useMutation({
    mutationFn: (body: {
      tool_key: string;
      arguments: Record<string, unknown>;
    }) =>
      request<AgentApprovalPolicyEvaluationResponse>(
        `/agents/${selectedId}/approval-policies/evaluate`,
        { method: "POST", body },
      ),
    onSuccess: (decision) => {
      setPolicyFormError(null);
      setPolicyDecision(decision);
    },
  });
  const submitAgent = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const submitMessage = (event: FormEvent) => {
    event.preventDefault();
    if (message.trim() && selectedId) chat.mutate();
  };
  const submitPolicy = (event: FormEvent) => {
    event.preventDefault();
    setPolicyFormError(null);
    const priority = Number(policyPriority);
    const minAmount = policyMinAmount ? Number(policyMinAmount) : null;
    const maxAmount = policyMaxAmount ? Number(policyMaxAmount) : null;
    const approvalTtl = Number(policyApprovalTtl);
    const escalationAfter = policyEscalationUserId
      ? Number(policyEscalationAfter)
      : null;
    if (!Number.isInteger(priority)) {
      setPolicyFormError("A prioridade deve ser um número inteiro.");
      return;
    }
    if (!Number.isInteger(approvalTtl) || approvalTtl < 5) {
      setPolicyFormError("A validade deve ser de pelo menos 5 minutos.");
      return;
    }
    const effectiveFrom = policyEffectiveFrom
      ? new Date(policyEffectiveFrom)
      : null;
    const effectiveUntil = policyEffectiveUntil
      ? new Date(policyEffectiveUntil)
      : null;
    if (
      (effectiveFrom && Number.isNaN(effectiveFrom.getTime())) ||
      (effectiveUntil && Number.isNaN(effectiveUntil.getTime())) ||
      (effectiveFrom && effectiveUntil && effectiveUntil <= effectiveFrom)
    ) {
      setPolicyFormError("O fim da vigência deve ser posterior ao início.");
      return;
    }
    if (policyEscalationUserId && !policyAssignedUserId) {
      setPolicyFormError("Defina o aprovador principal antes do substituto.");
      return;
    }
    if (
      policyEscalationUserId &&
      policyEscalationUserId === policyAssignedUserId
    ) {
      setPolicyFormError(
        "O aprovador substituto deve ser diferente do principal.",
      );
      return;
    }
    if (
      escalationAfter !== null &&
      (!Number.isInteger(escalationAfter) ||
        escalationAfter < 5 ||
        escalationAfter >= approvalTtl)
    ) {
      setPolicyFormError(
        "O escalonamento deve ocorrer entre 5 minutos e antes da expiração.",
      );
      return;
    }
    if (
      policyStages.some(
        (stage) =>
          !stage.name.trim() ||
          !Number.isInteger(Number(stage.quorum)) ||
          Number(stage.quorum) < 1 ||
          Number(stage.quorum) > stage.approverUserIds.length,
      )
    ) {
      setPolicyFormError(
        "Cada etapa precisa de nome, participantes e quórum compatível.",
      );
      return;
    }
    if (
      (minAmount !== null && !Number.isInteger(minAmount)) ||
      (maxAmount !== null && !Number.isInteger(maxAmount))
    ) {
      setPolicyFormError("Os valores devem ser inteiros em microunidades.");
      return;
    }
    createPolicy.mutate({
      policy_key: policyKey,
      name: policyName,
      effect: policyEffect,
      priority,
      tool_key: policyToolKey || null,
      amount_field: policyAmountField || null,
      min_amount_microunits: minAmount,
      max_amount_microunits: maxAmount,
      currency: policyCurrency || null,
      context_conditions: policyContextPath
        ? { [policyContextPath]: parseContextValue(policyContextValue) }
        : {},
      approval_ttl_minutes: approvalTtl,
      effective_from: effectiveFrom?.toISOString() ?? null,
      effective_until: effectiveUntil?.toISOString() ?? null,
      assigned_user_id:
        policyEffect === "require_approval" &&
        policyStages.length === 0 &&
        policyAssignedUserId
          ? policyAssignedUserId
          : null,
      escalation_user_id:
        policyEffect === "require_approval" &&
        policyStages.length === 0 &&
        policyEscalationUserId
          ? policyEscalationUserId
          : null,
      escalation_after_minutes:
        policyEffect === "require_approval" && policyStages.length === 0
          ? escalationAfter
          : null,
      approval_stages:
        policyEffect === "require_approval"
          ? policyStages.map((stage) => ({
              name: stage.name,
              quorum: Number(stage.quorum),
              approver_user_ids: stage.approverUserIds,
            }))
          : [],
    });
  };
  const simulatePolicy = () => {
    setPolicyFormError(null);
    try {
      evaluatePolicy.mutate({
        tool_key: simulationToolKey,
        arguments: parseArguments(simulationArguments),
      });
    } catch (error) {
      setPolicyFormError(
        error instanceof Error
          ? error.message
          : "Argumentos de teste inválidos.",
      );
    }
  };
  const activeCount = useMemo(
    () => agents.data?.filter((agent) => agent.status === "active").length ?? 0,
    [agents.data],
  );
  const totalTokens = useMemo(
    () => usage.data?.reduce((sum, item) => sum + item.total_tokens, 0) ?? 0,
    [usage.data],
  );
  const failure =
    create.error ??
    remove.error ??
    configureTools.error ??
    chat.error ??
    decide.error ??
    createPolicy.error ??
    publishPolicy.error ??
    evaluatePolicy.error;

  return (
    <div className="management-page agents-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Inteligência com limites</span>
          <h1>Agentes</h1>
          <p>
            Crie especialistas, autorize ferramentas e mantenha decisões
            críticas sob controle humano.
          </p>
        </div>
        <div className="agent-summary">
          <Sparkles size={18} />
          <strong>{activeCount}</strong>
          <span>ativos · {totalTokens} tokens</span>
        </div>
      </div>
      {failure ? <Alert variant="error">{errorMessage(failure)}</Alert> : null}
      {policyFormError ? (
        <Alert variant="error">{policyFormError}</Alert>
      ) : null}
      <PermissionGuard all={["agents.create"]}>
        <Card
          eyebrow="Novo especialista"
          title="Criar agente com limites explícitos"
        >
          <form className="agent-config-grid" onSubmit={submitAgent}>
            <TextField
              label="Nome"
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
            <label className="native-field">
              <span>Provedor</span>
              <select
                className="agent-native-select"
                onChange={(event) => {
                  const value = event.target.value as
                    "local" | "openai_compatible";
                  setProvider(value);
                  setModel(
                    value === "local" ? "orkestral-local" : "modelo-compatível",
                  );
                }}
                value={provider}
              >
                <option value="local">Local seguro</option>
                <option value="openai_compatible">API compatível</option>
              </select>
            </label>
            <TextField
              label="Modelo"
              onChange={(event) => setModel(event.target.value)}
              required
              value={model}
            />
            <label className="native-field">
              <span>Instruções</span>
              <textarea
                onChange={(event) => setInstructions(event.target.value)}
                rows={4}
                value={instructions}
              />
            </label>
            <Button loading={create.isPending} type="submit">
              <Bot size={17} /> Criar agente
            </Button>
          </form>
        </Card>
      </PermissionGuard>
      <div className="agent-studio">
        <Card
          className="agent-list"
          eyebrow="Equipe digital"
          title="Agentes da empresa"
        >
          {agents.data?.length === 0 ? (
            <div className="empty-state">
              <Bot />
              <strong>Nenhum agente</strong>
              <span>Crie o primeiro especialista da empresa.</span>
            </div>
          ) : null}
          {agents.data?.map((agent) => (
            <button
              className={`agent-row ${agent.id === selectedId ? "agent-row--active" : ""}`}
              key={agent.id}
              onClick={() => setSelectedId(agent.id)}
              type="button"
            >
              <span className="agent-row__avatar">
                <Bot size={19} />
              </span>
              <span>
                <strong>{agent.name}</strong>
                <small>
                  {agent.model} ·{" "}
                  {agent.provider === "local" ? "local" : "externo"}
                </small>
              </span>
              <span
                className={`status-chip status-chip--${agent.status === "active" ? "active" : "inactive"}`}
              >
                {agent.status}
              </span>
            </button>
          ))}
        </Card>
        {selected ? (
          <div className="agent-detail">
            <Card eyebrow="Perfil do agente" title={selected.name}>
              <p>{selected.description || selected.instructions}</p>
              <div className="form-actions">
                <span className="status-chip status-chip--active">
                  <Gauge size={14} /> {selected.max_output_tokens} tokens de
                  saída
                </span>
                <span className="status-chip status-chip--inactive">
                  <MessageSquare size={14} /> memória{" "}
                  {selected.memory_enabled ? "ativa" : "inativa"}
                </span>
                <Button
                  className="agent-delete-button"
                  loading={remove.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Excluir o agente ${selected.name}? O histórico será preservado.`,
                      )
                    ) {
                      remove.mutate(selected.id);
                    }
                  }}
                  variant="ghost"
                >
                  <Trash2 size={16} /> Excluir agente
                </Button>
              </div>
            </Card>
            <PermissionGuard all={["agents.configure"]}>
              <Card
                eyebrow="Princípio do menor privilégio"
                title="Ferramentas autorizadas"
              >
                <div className="agent-tool-grid">
                  {catalog.data?.map((tool) => (
                    <label
                      className={`agent-tool-option ${tool.is_sensitive ? "agent-tool-option--sensitive" : ""}`}
                      key={tool.key}
                    >
                      <input
                        checked={selectedTools.includes(tool.key)}
                        onChange={(event) =>
                          setSelectedTools((current) =>
                            event.target.checked
                              ? [...new Set([...current, tool.key])]
                              : current.filter((key) => key !== tool.key),
                          )
                        }
                        type="checkbox"
                      />
                      <span>
                        <strong>
                          {tool.is_sensitive ? (
                            <ShieldAlert size={15} />
                          ) : (
                            <LockKeyhole size={15} />
                          )}{" "}
                          {tool.name}
                        </strong>
                        <small>{tool.description}</small>
                        <small>
                          {tool.is_sensitive
                            ? "Exige confirmação humana"
                            : `Permissão: ${tool.required_permission}`}
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
                <Button
                  loading={configureTools.isPending}
                  onClick={() => configureTools.mutate()}
                  variant="secondary"
                >
                  Salvar ferramentas
                </Button>
              </Card>
            </PermissionGuard>
            <PermissionGuard all={["agents.configure"]}>
              <Card
                className="agent-policy-card"
                eyebrow="Governança contextual"
                title="Políticas de aprovação"
              >
                <p>
                  Defina quando uma ferramenta pode executar, precisa de uma
                  pessoa ou deve ser bloqueada. Publique somente depois de
                  simular a decisão.
                </p>
                <form className="agent-policy-form" onSubmit={submitPolicy}>
                  <TextField
                    label="Nome da política"
                    onChange={(event) => setPolicyName(event.target.value)}
                    required
                    value={policyName}
                  />
                  <TextField
                    label="Chave da política"
                    onChange={(event) => setPolicyKey(event.target.value)}
                    required
                    value={policyKey}
                  />
                  <label className="native-field">
                    <span>Efeito da política</span>
                    <select
                      className="agent-native-select"
                      onChange={(event) =>
                        setPolicyEffect(
                          event.target.value as
                            "allow" | "require_approval" | "deny",
                        )
                      }
                      value={policyEffect}
                    >
                      <option value="allow">Permitir</option>
                      <option value="require_approval">Exigir aprovação</option>
                      <option value="deny">Bloquear</option>
                    </select>
                  </label>
                  <TextField
                    label="Prioridade"
                    onChange={(event) => setPolicyPriority(event.target.value)}
                    required
                    type="number"
                    value={policyPriority}
                  />
                  <label className="native-field">
                    <span>Ferramenta da política</span>
                    <select
                      className="agent-native-select"
                      onChange={(event) => setPolicyToolKey(event.target.value)}
                      value={policyToolKey}
                    >
                      <option value="">Todas as ferramentas</option>
                      {catalog.data?.map((tool) => (
                        <option key={tool.key} value={tool.key}>
                          {tool.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <TextField
                    label="Campo de valor (microunidades)"
                    onChange={(event) =>
                      setPolicyAmountField(event.target.value)
                    }
                    placeholder="amount_microunits"
                    value={policyAmountField}
                  />
                  <TextField
                    label="Valor mínimo"
                    onChange={(event) => setPolicyMinAmount(event.target.value)}
                    type="number"
                    value={policyMinAmount}
                  />
                  <TextField
                    label="Valor máximo"
                    onChange={(event) => setPolicyMaxAmount(event.target.value)}
                    type="number"
                    value={policyMaxAmount}
                  />
                  <TextField
                    label="Moeda"
                    maxLength={3}
                    onChange={(event) =>
                      setPolicyCurrency(event.target.value.toUpperCase())
                    }
                    placeholder="BRL"
                    value={policyCurrency}
                  />
                  <TextField
                    label="Caminho de contexto"
                    onChange={(event) =>
                      setPolicyContextPath(event.target.value)
                    }
                    placeholder="customer.region"
                    value={policyContextPath}
                  />
                  <TextField
                    label="Valor esperado"
                    onChange={(event) =>
                      setPolicyContextValue(event.target.value)
                    }
                    placeholder="sudeste"
                    value={policyContextValue}
                  />
                  <TextField
                    label="Início da vigência"
                    onChange={(event) =>
                      setPolicyEffectiveFrom(event.target.value)
                    }
                    type="datetime-local"
                    value={policyEffectiveFrom}
                  />
                  <TextField
                    label="Fim da vigência"
                    onChange={(event) =>
                      setPolicyEffectiveUntil(event.target.value)
                    }
                    type="datetime-local"
                    value={policyEffectiveUntil}
                  />
                  <TextField
                    disabled={policyEffect !== "require_approval"}
                    label="Validade da aprovação (minutos)"
                    min={5}
                    onChange={(event) =>
                      setPolicyApprovalTtl(event.target.value)
                    }
                    required
                    type="number"
                    value={policyApprovalTtl}
                  />
                  <label className="native-field">
                    <span>Aprovador principal</span>
                    <select
                      className="agent-native-select"
                      disabled={
                        policyEffect !== "require_approval" ||
                        !canViewUsers ||
                        policyStages.length > 0
                      }
                      onChange={(event) =>
                        setPolicyAssignedUserId(event.target.value)
                      }
                      value={policyAssignedUserId}
                    >
                      <option value="">Fila geral de aprovadores</option>
                      {companyUsers.data
                        ?.filter(
                          (user) =>
                            user.user_status === "active" &&
                            user.membership_status === "active",
                        )
                        .map((user) => (
                          <option key={user.user_id} value={user.user_id}>
                            {user.name} · {user.email}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="native-field">
                    <span>Aprovador substituto</span>
                    <select
                      className="agent-native-select"
                      disabled={
                        policyEffect !== "require_approval" ||
                        !canViewUsers ||
                        !policyAssignedUserId ||
                        policyStages.length > 0
                      }
                      onChange={(event) =>
                        setPolicyEscalationUserId(event.target.value)
                      }
                      value={policyEscalationUserId}
                    >
                      <option value="">Sem escalonamento automático</option>
                      {companyUsers.data
                        ?.filter(
                          (user) =>
                            user.user_status === "active" &&
                            user.membership_status === "active" &&
                            user.user_id !== policyAssignedUserId,
                        )
                        .map((user) => (
                          <option key={user.user_id} value={user.user_id}>
                            {user.name} · {user.email}
                          </option>
                        ))}
                    </select>
                  </label>
                  <TextField
                    disabled={
                      !policyEscalationUserId || policyStages.length > 0
                    }
                    label="Escalonar após (minutos)"
                    min={5}
                    onChange={(event) =>
                      setPolicyEscalationAfter(event.target.value)
                    }
                    required={Boolean(policyEscalationUserId)}
                    type="number"
                    value={policyEscalationAfter}
                  />
                  <div className="agent-policy-stages">
                    <div className="agent-policy-stages__heading">
                      <div>
                        <strong>Cadeia de aprovação</strong>
                        <small>
                          Use etapas para decisões com separação de funções e
                          quórum.
                        </small>
                      </div>
                      <Button
                        disabled={
                          policyEffect !== "require_approval" || !canViewUsers
                        }
                        onClick={() =>
                          setPolicyStages((current) => [
                            ...current,
                            {
                              id: crypto.randomUUID(),
                              name: `Etapa ${current.length + 1}`,
                              quorum: "1",
                              approverUserIds: [],
                            },
                          ])
                        }
                        type="button"
                        variant="secondary"
                      >
                        Adicionar etapa
                      </Button>
                    </div>
                    {policyStages.map((stage, index) => (
                      <article className="agent-policy-stage" key={stage.id}>
                        <TextField
                          label={`Nome da etapa ${index + 1}`}
                          onChange={(event) =>
                            setPolicyStages((current) =>
                              current.map((item) =>
                                item.id === stage.id
                                  ? { ...item, name: event.target.value }
                                  : item,
                              ),
                            )
                          }
                          required
                          value={stage.name}
                        />
                        <TextField
                          label={`Quórum da etapa ${index + 1}`}
                          min={1}
                          onChange={(event) =>
                            setPolicyStages((current) =>
                              current.map((item) =>
                                item.id === stage.id
                                  ? { ...item, quorum: event.target.value }
                                  : item,
                              ),
                            )
                          }
                          required
                          type="number"
                          value={stage.quorum}
                        />
                        <label className="native-field">
                          <span>Participantes da etapa {index + 1}</span>
                          <select
                            aria-label={`Participantes da etapa ${index + 1}`}
                            className="agent-native-select"
                            multiple
                            onChange={(event) => {
                              const approverUserIds = Array.from(
                                event.currentTarget.selectedOptions,
                                (option) => option.value,
                              );
                              setPolicyStages((current) =>
                                current.map((item) =>
                                  item.id === stage.id
                                    ? { ...item, approverUserIds }
                                    : item,
                                ),
                              );
                            }}
                            required
                            value={stage.approverUserIds}
                          >
                            {companyUsers.data
                              ?.filter(
                                (user) =>
                                  user.user_status === "active" &&
                                  user.membership_status === "active" &&
                                  !policyStages.some(
                                    (other) =>
                                      other.id !== stage.id &&
                                      other.approverUserIds.includes(
                                        user.user_id,
                                      ),
                                  ),
                              )
                              .map((user) => (
                                <option key={user.user_id} value={user.user_id}>
                                  {user.name} · {user.email}
                                </option>
                              ))}
                          </select>
                        </label>
                        <Button
                          onClick={() =>
                            setPolicyStages((current) =>
                              current.filter((item) => item.id !== stage.id),
                            )
                          }
                          type="button"
                          variant="ghost"
                        >
                          Remover etapa
                        </Button>
                      </article>
                    ))}
                  </div>
                  <Button loading={createPolicy.isPending} type="submit">
                    Criar rascunho
                  </Button>
                </form>

                <div className="agent-policy-list">
                  {policies.data?.length === 0 ? (
                    <div className="empty-state">
                      <LockKeyhole />
                      <span>
                        Nenhuma política configurada para este agente.
                      </span>
                    </div>
                  ) : null}
                  {policies.data?.map((policy) => (
                    <article className="agent-policy-row" key={policy.id}>
                      <div>
                        <strong>{policy.name}</strong>
                        <small>
                          {policy.policy_key} · versão {policy.version} ·
                          prioridade {policy.priority}
                        </small>
                        <small>
                          {policy.tool_key || "Todas as ferramentas"} ·{" "}
                          {policy.effect === "allow"
                            ? "Permitir"
                            : policy.effect === "deny"
                              ? "Bloquear"
                              : "Exigir aprovação"}
                        </small>
                        {policy.effect === "require_approval" ? (
                          <small>
                            {policy.assigned_user_id
                              ? `Aprovador principal definido · validade ${policy.approval_ttl_minutes} min`
                              : `Fila geral · validade ${policy.approval_ttl_minutes} min`}
                            {policy.escalation_user_id &&
                            policy.escalation_after_minutes
                              ? ` · escala após ${policy.escalation_after_minutes} min`
                              : ""}
                          </small>
                        ) : null}
                        {policy.approval_stages.length ? (
                          <small>
                            {policy.approval_stages.length}{" "}
                            {policy.approval_stages.length === 1
                              ? "etapa"
                              : "etapas"}{" "}
                            · quórum configurado
                          </small>
                        ) : null}
                        {policy.effective_from || policy.effective_until ? (
                          <small>
                            Vigência:{" "}
                            {policy.effective_from
                              ? new Date(policy.effective_from).toLocaleString(
                                  "pt-BR",
                                )
                              : "imediata"}{" "}
                            até{" "}
                            {policy.effective_until
                              ? new Date(policy.effective_until).toLocaleString(
                                  "pt-BR",
                                )
                              : "sem prazo final"}
                          </small>
                        ) : null}
                      </div>
                      <div className="agent-policy-row__actions">
                        <span
                          className={`status-chip status-chip--${policy.status === "published" ? "active" : "inactive"}`}
                        >
                          {policy.status === "published"
                            ? "Publicada"
                            : policy.status === "draft"
                              ? "Rascunho"
                              : "Substituída"}
                        </span>
                        {policy.status === "draft" ? (
                          <Button
                            loading={publishPolicy.isPending}
                            onClick={() => publishPolicy.mutate(policy.id)}
                            variant="secondary"
                          >
                            Publicar
                          </Button>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>

                <div className="agent-policy-simulator">
                  <div>
                    <span className="eyebrow">Teste antes de executar</span>
                    <h3>Simular decisão</h3>
                  </div>
                  <label className="native-field">
                    <span>Ferramenta para simular</span>
                    <select
                      className="agent-native-select"
                      onChange={(event) =>
                        setSimulationToolKey(event.target.value)
                      }
                      value={simulationToolKey}
                    >
                      {catalog.data?.map((tool) => (
                        <option key={tool.key} value={tool.key}>
                          {tool.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="native-field">
                    <span>Argumentos de teste (JSON)</span>
                    <textarea
                      aria-label="Argumentos de teste (JSON)"
                      onChange={(event) =>
                        setSimulationArguments(event.target.value)
                      }
                      rows={4}
                      value={simulationArguments}
                    />
                  </label>
                  <Button
                    disabled={!simulationToolKey}
                    loading={evaluatePolicy.isPending}
                    onClick={simulatePolicy}
                    variant="secondary"
                  >
                    Simular decisão
                  </Button>
                  {policyDecision ? (
                    <div
                      className={`agent-policy-decision agent-policy-decision--${!policyDecision.allowed ? "deny" : policyDecision.requires_approval ? "approval" : "allow"}`}
                    >
                      <strong>
                        {!policyDecision.allowed
                          ? "Bloqueada"
                          : policyDecision.requires_approval
                            ? "Exige aprovação"
                            : "Permitida"}
                      </strong>
                      <span>{policyDecision.reason}</span>
                      {policyDecision.escalation_user_id &&
                      policyDecision.escalation_after_minutes ? (
                        <small>
                          Escalonamento automático após{" "}
                          {policyDecision.escalation_after_minutes} minutos.
                        </small>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </Card>
            </PermissionGuard>
            <PermissionGuard all={["agents.execute"]}>
              <Card
                className="agent-chat"
                eyebrow="Conversa auditável"
                title="Falar com o agente"
              >
                <div className="agent-chat-log">
                  {!conversationId ? (
                    <div className="empty-state">
                      <MessageSquare />
                      <span>
                        Inicie uma conversa. Para testar: /ferramenta
                        orkestral.company.summary {"{}"}
                      </span>
                    </div>
                  ) : null}
                  {messages.data?.map((item) => (
                    <div
                      className={`agent-message agent-message--${item.role}`}
                      key={item.id}
                    >
                      <strong>
                        {item.role === "user" ? "Você" : selected.name}
                      </strong>
                      <div>{item.content}</div>
                      <small>
                        {item.total_tokens
                          ? `${item.total_tokens} tokens · ${item.duration_ms ?? 0} ms`
                          : new Date(item.created_at).toLocaleTimeString(
                              "pt-BR",
                            )}
                      </small>
                    </div>
                  ))}
                </div>
                <form className="agent-composer" onSubmit={submitMessage}>
                  <textarea
                    aria-label="Mensagem"
                    onChange={(event) => setMessage(event.target.value)}
                    placeholder="Digite uma mensagem ou solicite uma ferramenta…"
                    rows={3}
                    value={message}
                  />
                  <Button loading={chat.isPending} type="submit">
                    <Send size={17} /> Enviar
                  </Button>
                </form>
              </Card>
            </PermissionGuard>
          </div>
        ) : null}
      </div>
      <div className="agent-config-grid">
        <PermissionGuard all={["agents.execute"]}>
          <Card eyebrow="Controle humano" title="Ações aguardando confirmação">
            <div className="agent-actions">
              {pending.data?.length === 0 ? (
                <div className="empty-state">
                  <Check />
                  <span>Nenhuma ação crítica pendente.</span>
                </div>
              ) : null}
              {pending.data?.map((action) => (
                <div className="agent-action" key={action.id}>
                  <div>
                    <strong>{action.tool_name}</strong>
                    <small>
                      Solicitada em{" "}
                      {new Date(action.created_at).toLocaleString("pt-BR")}
                    </small>
                  </div>
                  <div className="agent-action__buttons">
                    <Button
                      loading={decide.isPending}
                      onClick={() =>
                        decide.mutate({ action, decision: "approved" })
                      }
                    >
                      <Check size={16} /> Aprovar
                    </Button>
                    <Button
                      loading={decide.isPending}
                      onClick={() =>
                        decide.mutate({ action, decision: "rejected" })
                      }
                      variant="ghost"
                    >
                      <X size={16} /> Rejeitar
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </PermissionGuard>
        <Card eyebrow="Consumo rastreável" title="Tokens, custo e duração">
          <div className="agent-usage-list">
            {usage.data?.slice(0, 8).map((item) => (
              <div className="agent-usage" key={item.id}>
                <div>
                  <strong>{item.total_tokens} tokens</strong>
                  <small>
                    {item.provider} · {item.model}
                  </small>
                </div>
                <div>
                  <strong>
                    US$ {(item.cost_microunits / 1_000_000).toFixed(6)}
                  </strong>
                  <small>
                    {item.duration_ms} ms · {item.result_status}
                  </small>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

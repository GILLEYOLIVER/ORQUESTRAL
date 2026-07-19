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
  X,
} from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import {
  type AgentChatResponse,
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

export function AgentsPage() {
  const queryClient = useQueryClient();
  const { me } = useSession();
  const agents = useAgents();
  const canConfigure = me?.permissions.includes("agents.configure") ?? false;
  const canExecute = me?.permissions.includes("agents.execute") ?? false;
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
  const selected = agents.data?.find((agent) => agent.id === selectedId);

  useEffect(() => {
    if (!selectedId && agents.data?.[0]) setSelectedId(agents.data[0].id);
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
  };
  const create = useMutation({
    mutationFn: () =>
      request<AgentResponse>("/agents", {
        method: "POST",
        body: { name, instructions, provider, model },
      }),
    onSuccess: (agent) => {
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
  const submitAgent = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const submitMessage = (event: FormEvent) => {
    event.preventDefault();
    if (message.trim() && selectedId) chat.mutate();
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
    create.error ?? configureTools.error ?? chat.error ?? decide.error;

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

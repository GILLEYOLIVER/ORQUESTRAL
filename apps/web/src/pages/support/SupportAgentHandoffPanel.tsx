import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, GitPullRequestArrow, ShieldCheck, UserRoundCheck } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-agent-handoff.css";

type Agent = { id: string; name: string; status: string; active_version_id: string | null };
type User = { id: string; name?: string; email: string };
type AssistRun = {
  id: string;
  recommendation: "respond" | "request_information" | "human_handoff";
  reason_code: string;
  status: string;
  citation_count: number;
  context_refs: Array<{ type: string; id: string }>;
};
type Handoff = { id: string; status: "requested" | "accepted" | "rejected" };
type Props = { ticketId: string | null; onAssigned: (userId: string) => void };

const recommendationLabels = {
  respond: "Resposta pode ser preparada",
  request_information: "Solicitar mais informações",
  human_handoff: "Transferir para atendimento humano",
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a assistência.";
}

export function SupportAgentHandoffPanel({ ticketId, onAssigned }: Props) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [agentId, setAgentId] = useState("");
  const [targetUserId, setTargetUserId] = useState("");
  const [run, setRun] = useState<AssistRun | null>(null);
  const [handoff, setHandoff] = useState<Handoff | null>(null);

  const agents = useQuery({
    queryKey: ["agents", "support-assist"],
    queryFn: () => request<Agent[]>("/agents"),
  });
  const users = useQuery({
    queryKey: ["users", "support-handoff"],
    queryFn: () => request<User[]>("/users"),
  });
  const analyze = useMutation({
    mutationFn: () =>
      request<AssistRun>(`/support/agent-assist/tickets/${ticketId}/runs`, {
        method: "POST",
        body: { agent_id: agentId },
      }),
    onSuccess: setRun,
  });
  const requestHandoff = useMutation({
    mutationFn: () =>
      request<Handoff>(`/support/agent-assist/runs/${run?.id}/handoffs`, {
        method: "POST",
        body: { target_user_id: targetUserId, reason_code: "support.supervised_transfer" },
      }),
    onSuccess: setHandoff,
  });
  const decide = useMutation({
    mutationFn: (decision: "accepted" | "rejected") =>
      request<Handoff>(`/support/agent-assist/handoffs/${handoff?.id}/decision`, {
        method: "POST",
        body: { decision },
      }),
    onSuccess: async (result) => {
      setHandoff(result);
      if (result.status === "accepted") onAssigned(targetUserId);
      await queryClient.invalidateQueries({ queryKey: ["support-tickets"] });
    },
  });
  const mutationError = analyze.error ?? requestHandoff.error ?? decide.error;

  return (
    <section className="support-agent-handoff">
      <header>
        <div>
          <span className="eyebrow">Autonomia controlada</span>
          <h2>Agente e transferência humana</h2>
          <p>O agente recomenda; uma pessoa decide e assume quando necessário.</p>
        </div>
        <Button variant="secondary" onClick={() => setExpanded((value) => !value)}>
          <Bot size={17} /> {expanded ? "Recolher agente" : "Abrir agente"}
        </Button>
      </header>
      <div className="support-agent-handoff__summary">
        <article><ShieldCheck size={19} /><span>Execução</span><strong>{run?.status ?? "Não iniciada"}</strong></article>
        <article><GitPullRequestArrow size={19} /><span>Recomendação</span><strong>{run ? recommendationLabels[run.recommendation] : "Aguardando"}</strong></article>
        <article><UserRoundCheck size={19} /><span>Transferência</span><strong>{handoff?.status ?? "Nenhuma"}</strong></article>
      </div>
      {mutationError ? <Alert variant="error">{errorMessage(mutationError)}</Alert> : null}
      {expanded ? (
        <div className="support-agent-handoff__body">
          <Card eyebrow="1. Análise governada">
            <label>Agente publicado<select value={agentId} onChange={(event) => setAgentId(event.target.value)}>
              <option value="">Selecione</option>
              {agents.data?.filter((agent) => agent.status === "active" && agent.active_version_id).map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select></label>
            <PermissionGuard all={["agents.execute"]}>
              <Button disabled={!ticketId || !agentId} onClick={() => analyze.mutate()}>
                <Bot size={17} /> Analisar chamado
              </Button>
            </PermissionGuard>
          </Card>
          <Card eyebrow="2. Evidência da decisão">
            {run ? <>
              <strong>{recommendationLabels[run.recommendation]}</strong>
              <p>Código: {run.reason_code}</p>
              <p>{run.context_refs.length} referências autorizadas e {run.citation_count} fontes.</p>
            </> : <p>Execute a análise para ver a justificativa.</p>}
          </Card>
          <Card eyebrow="3. Controle humano">
            <label>Responsável humano<select value={targetUserId} onChange={(event) => setTargetUserId(event.target.value)}>
              <option value="">Selecione</option>
              {users.data?.map((user) => <option key={user.id} value={user.id}>{user.name ?? user.email}</option>)}
            </select></label>
            <PermissionGuard all={["support.tickets.update"]}>
              {!handoff ? <Button disabled={!run || !targetUserId} onClick={() => requestHandoff.mutate()}>Solicitar transferência</Button> : null}
              {handoff?.status === "requested" ? <div className="support-agent-handoff__decisions">
                <Button onClick={() => decide.mutate("accepted")}><CheckCircle2 size={17} /> Aceitar</Button>
                <Button variant="secondary" onClick={() => decide.mutate("rejected")}>Rejeitar</Button>
              </div> : null}
            </PermissionGuard>
          </Card>
        </div>
      ) : null}
    </section>
  );
}


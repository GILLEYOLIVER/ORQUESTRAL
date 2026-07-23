import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Route,
  Settings2,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-routing.css";

type Skill = {
  id: string;
  name: string;
  key: string;
  description: string | null;
  is_active: boolean;
};

type Agent = {
  user_id: string;
  user_name: string;
  status: "offline" | "available" | "busy" | "away";
  queue_id: string | null;
  max_active_tickets: number;
  active_tickets: number;
  languages: string[];
  accepted_channels: string[];
  skills: { skill_id: string; proficiency: number }[];
};

type Queue = {
  queue_id: string;
  queue_name: string;
  required_skill_ids: string[];
};

type Configuration = {
  skills: Skill[];
  agents: Agent[];
  queues: Queue[];
};

type Recommendation = {
  ticket_id: string;
  channel: string;
  language_code: string | null;
  required_skill_ids: string[];
  candidates: {
    user_id: string;
    user_name: string;
    score: number;
    active_tickets: number;
    max_active_tickets: number;
    load_percent: number;
    proficiency: number | null;
    reasons: string[];
  }[];
  explanation: string;
};

export type SupportRoutingTicket = {
  id: string;
  channel: string;
  queue_id: string | null;
  assignee_user_id: string | null;
  required_skill_id: string | null;
  language_code: string | null;
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação de roteamento.";
}

export function SupportRoutingPanel({
  ticket,
  onAssigned,
}: {
  ticket: SupportRoutingTicket | null;
  onAssigned: (userId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [skillName, setSkillName] = useState("");
  const [skillKey, setSkillKey] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [selectedQueueId, setSelectedQueueId] = useState("");
  const [languageCode, setLanguageCode] = useState("pt-br");
  const [capacity, setCapacity] = useState("5");
  const [recommendation, setRecommendation] =
    useState<Recommendation | null>(null);

  const configuration = useQuery({
    queryKey: ["support", "routing", "configuration"],
    queryFn: () =>
      request<Configuration>("/support/routing/configuration"),
  });
  const selectedAgent = useMemo(
    () =>
      configuration.data?.agents.find(
        (agent) => agent.user_id === selectedAgentId,
      ),
    [configuration.data?.agents, selectedAgentId],
  );

  const refresh = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["support", "routing", "configuration"],
    });
  };
  const createSkill = useMutation({
    mutationFn: () =>
      request<Skill>("/support/routing/skills", {
        method: "POST",
        body: {
          name: skillName,
          key: skillKey,
          description: `Especialidade de atendimento: ${skillName}`,
        },
      }),
    onSuccess: async () => {
      setSkillName("");
      setSkillKey("");
      await refresh();
    },
  });
  const configureAgent = useMutation({
    mutationFn: () =>
      request<Configuration>(`/support/routing/agents/${selectedAgentId}`, {
        method: "PUT",
        body: {
          status: "available",
          queue_id: selectedQueueId || null,
          max_active_tickets: Math.max(1, Number(capacity)),
          languages: languageCode ? [languageCode] : [],
          accepted_channels: ["web", "email", "phone", "whatsapp"],
          skills: selectedSkillId
            ? [{ skill_id: selectedSkillId, proficiency: 3 }]
            : [],
        },
      }),
    onSuccess: refresh,
  });
  const configureQueue = useMutation({
    mutationFn: () =>
      request<Configuration>(`/support/routing/queues/${selectedQueueId}`, {
        method: "PUT",
        body: {
          required_skill_ids: selectedSkillId ? [selectedSkillId] : [],
        },
      }),
    onSuccess: refresh,
  });
  const recommend = useMutation({
    mutationFn: () =>
      request<Recommendation>(
        `/support/routing/tickets/${ticket?.id}/recommend`,
        {
          method: "POST",
          body: {
            language_code: languageCode || null,
            required_skill_id: selectedSkillId || null,
          },
        },
      ),
    onSuccess: setRecommendation,
  });
  const assign = useMutation({
    mutationFn: (candidateUserId: string) =>
      request<{
        assigned_user_id: string;
        assigned_user_name: string;
      }>(`/support/routing/tickets/${ticket?.id}/assign`, {
        method: "POST",
        body: {
          language_code: languageCode || null,
          required_skill_id: selectedSkillId || null,
          candidate_user_id: candidateUserId,
        },
      }),
    onSuccess: async (result) => {
      onAssigned(result.assigned_user_id);
      await Promise.all([
        refresh(),
        queryClient.invalidateQueries({ queryKey: ["support-tickets"] }),
        queryClient.invalidateQueries({
          queryKey: ["support", "ticket-events", ticket?.id],
        }),
      ]);
    },
  });
  const mutationError =
    createSkill.error ||
    configureAgent.error ||
    configureQueue.error ||
    recommend.error ||
    assign.error;

  return (
    <section className="support-routing">
      <header>
        <div>
          <span className="eyebrow">Distribuição explicável</span>
          <h2>Roteamento inteligente</h2>
          <p>
            Encontre o atendente certo por habilidade, idioma, canal e carga.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          <Settings2 size={17} />
          {expanded ? "Recolher roteamento" : "Configurar roteamento"}
          <ChevronDown className={expanded ? "rotated" : ""} size={16} />
        </Button>
      </header>

      <div className="support-routing-summary">
        <article>
          <BrainCircuit size={19} />
          <span>Habilidades</span>
          <strong>{configuration.data?.skills.length ?? 0}</strong>
        </article>
        <article>
          <UsersRound size={19} />
          <span>Disponíveis</span>
          <strong>
            {configuration.data?.agents.filter(
              (agent) => agent.status === "available",
            ).length ?? 0}
          </strong>
        </article>
        <article>
          <Route size={19} />
          <span>Filas configuradas</span>
          <strong>
            {configuration.data?.queues.filter(
              (queue) => queue.required_skill_ids.length > 0,
            ).length ?? 0}
          </strong>
        </article>
      </div>

      {mutationError ? (
        <Alert variant="error">{errorMessage(mutationError)}</Alert>
      ) : null}

      {expanded ? (
        <div className="support-routing-body">
          <PermissionGuard all={["support.tickets.update"]}>
            <Card eyebrow="1. Crie especialidades">
              <div className="support-routing-fields">
                <label>
                  Nome da habilidade
                  <input
                    onChange={(event) => {
                      setSkillName(event.target.value);
                      setSkillKey(
                        event.target.value
                          .toLowerCase()
                          .normalize("NFD")
                          .replace(/[\u0300-\u036f]/g, "")
                          .replace(/[^a-z0-9]+/g, "-")
                          .replace(/^-|-$/g, ""),
                      );
                    }}
                    placeholder="Ex.: Financeiro"
                    value={skillName}
                  />
                </label>
                <label>
                  Identificador
                  <input
                    onChange={(event) => setSkillKey(event.target.value)}
                    placeholder="financeiro"
                    value={skillKey}
                  />
                </label>
                <Button
                  disabled={skillName.length < 2 || skillKey.length < 2}
                  loading={createSkill.isPending}
                  onClick={() => createSkill.mutate()}
                >
                  Criar habilidade
                </Button>
              </div>
            </Card>

            <Card eyebrow="2. Prepare a equipe">
              <div className="support-routing-fields">
                <label>
                  Atendente
                  <select
                    onChange={(event) =>
                      setSelectedAgentId(event.target.value)
                    }
                    value={selectedAgentId}
                  >
                    <option value="">Selecione</option>
                    {configuration.data?.agents.map((agent) => (
                      <option key={agent.user_id} value={agent.user_id}>
                        {agent.user_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Fila principal
                  <select
                    onChange={(event) => setSelectedQueueId(event.target.value)}
                    value={selectedQueueId}
                  >
                    <option value="">Todas as filas</option>
                    {configuration.data?.queues.map((queue) => (
                      <option key={queue.queue_id} value={queue.queue_id}>
                        {queue.queue_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Habilidade
                  <select
                    onChange={(event) => setSelectedSkillId(event.target.value)}
                    value={selectedSkillId}
                  >
                    <option value="">Sem exigência específica</option>
                    {configuration.data?.skills.map((skill) => (
                      <option key={skill.id} value={skill.id}>
                        {skill.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Idioma
                  <input
                    onChange={(event) => setLanguageCode(event.target.value)}
                    value={languageCode}
                  />
                </label>
                <label>
                  Capacidade simultânea
                  <input
                    min="1"
                    max="100"
                    onChange={(event) => setCapacity(event.target.value)}
                    type="number"
                    value={capacity}
                  />
                </label>
                <Button
                  disabled={!selectedAgentId}
                  loading={configureAgent.isPending}
                  onClick={() => configureAgent.mutate()}
                >
                  Disponibilizar atendente
                </Button>
                <Button
                  disabled={!selectedQueueId}
                  loading={configureQueue.isPending}
                  onClick={() => configureQueue.mutate()}
                  variant="secondary"
                >
                  Aplicar habilidade à fila
                </Button>
              </div>
              {selectedAgent ? (
                <p className="support-routing-note">
                  {selectedAgent.user_name}: {selectedAgent.active_tickets}/
                  {selectedAgent.max_active_tickets} chamados ativos.
                </p>
              ) : null}
            </Card>
          </PermissionGuard>

          <Card className="support-routing-recommendation" eyebrow="3. Distribua">
            {ticket ? (
              <>
                <div>
                  <h3>Recomendar para o chamado selecionado</h3>
                  <p>
                    A simulação não altera o chamado. A atribuição exige
                    permissão e confirmação explícita.
                  </p>
                </div>
                <Button
                  loading={recommend.isPending}
                  onClick={() => recommend.mutate()}
                >
                  <Sparkles size={16} /> Calcular recomendação
                </Button>
              </>
            ) : (
              <p>Selecione um chamado para calcular a melhor distribuição.</p>
            )}
          </Card>

          {recommendation ? (
            <div className="support-routing-candidates">
              <p>{recommendation.explanation}</p>
              {recommendation.candidates.map((candidate, index) => (
                <article key={candidate.user_id}>
                  <span className="support-routing-rank">#{index + 1}</span>
                  <div>
                    <strong>{candidate.user_name}</strong>
                    <small>
                      Pontuação {candidate.score} · carga{" "}
                      {candidate.active_tickets}/
                      {candidate.max_active_tickets}
                    </small>
                    <ul>
                      {candidate.reasons.map((reason) => (
                        <li key={reason}>
                          <CheckCircle2 size={13} /> {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <PermissionGuard all={["support.tickets.update"]}>
                    <Button
                      loading={assign.isPending}
                      onClick={() => assign.mutate(candidate.user_id)}
                      variant={index === 0 ? "primary" : "secondary"}
                    >
                      Atribuir
                    </Button>
                  </PermissionGuard>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

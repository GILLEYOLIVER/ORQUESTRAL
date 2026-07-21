import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  BrainCircuit,
  Check,
  Download,
  Gauge,
  LockKeyhole,
  MessageSquare,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  TimerReset,
  X,
} from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import {
  type AgentChatResponse,
  type AgentConversationCloseResponse,
  type AgentApprovalPolicyEvaluationResponse,
  type AgentApprovalPolicyResponse,
  type AgentMessageResponse,
  type AgentMemoryPolicyResponse,
  type AgentMemoryResponse,
  type AgentMemoryConsentRevocationResponse,
  type AgentMemoryMetadataExport,
  type AgentMemoryRiskSummary,
  type AgentMemoryRiskReport,
  type AgentMemoryResponseExercise,
  type AgentMemoryRiskSigningKey,
  type AgentMemoryExerciseSchedule,
  type AgentMemoryExerciseDue,
  type AgentMemoryCredentialRenewal,
  type AgentMemoryKeyringPolicy,
  type AgentMemoryKeyringStatus,
  type AgentMemoryLegalHoldRenewal,
  type AgentMemoryReencryptionJob,
  type AgentMemoryReencryptionLegalHold,
  type AgentMemoryReencryptionRecoveryAssessment,
  type AgentMemorySchedulerMetrics,
  type AgentMemoryVaultCredentialOption,
  type AgentMemoryVaultAvailability,
  type AgentMemoryVaultIncident,
  type AgentMemoryWorkloadIdentityRotation,
  type ManagedVaultMetric,
  type AgentResponse,
  type AgentToolCatalog,
  type AgentToolResponse,
  type AgentToolRunResponse,
  type AgentTaskMemoryIncidentResponse,
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
  const canManagePlugins = me?.permissions.includes("plugins.manage") ?? false;
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
  const [memoryDefaultRetention, setMemoryDefaultRetention] = useState("30");
  const [memoryMaxRetention, setMemoryMaxRetention] = useState("365");
  const [memoryScopes, setMemoryScopes] = useState<string[]>([
    "conversation",
    "task",
    "operational",
  ]);
  const [memoryClassifications, setMemoryClassifications] = useState<string[]>([
    "public",
    "internal",
  ]);
  const [memoryConsentRequired, setMemoryConsentRequired] = useState(true);
  const [memoryRetrievalEnabled, setMemoryRetrievalEnabled] = useState(false);
  const [memoryRetrievalLimit, setMemoryRetrievalLimit] = useState("5");
  const [memoryMaxContextTokens, setMemoryMaxContextTokens] = useState("1000");
  const [memoryMaxSharedEntries, setMemoryMaxSharedEntries] = useState("5");
  const [memoryMaxSharedCharacters, setMemoryMaxSharedCharacters] =
    useState("2000");
  const [memoryBlockedAlertThreshold, setMemoryBlockedAlertThreshold] =
    useState("3");
  const [memoryScopeRetention, setMemoryScopeRetention] = useState<
    Record<string, string>
  >({});
  const [memoryRetrievalScopes, setMemoryRetrievalScopes] = useState<string[]>(
    [],
  );
  const [memoryPurposeRetention, setMemoryPurposeRetention] = useState<
    Record<string, string>
  >({});
  const [enabledMemoryPurposes, setEnabledMemoryPurposes] = useState<string[]>(
    [],
  );
  const [memoryConsentSubjectUserId, setMemoryConsentSubjectUserId] =
    useState("");
  const [memoryConsentReference, setMemoryConsentReference] = useState("");
  const [memoryFeedback, setMemoryFeedback] = useState<string | null>(null);
  const [memoryIncidentReference, setMemoryIncidentReference] = useState("");
  const [memoryIncidentReason, setMemoryIncidentReason] = useState("");
  const [memoryIncidentQuarantineMinutes, setMemoryIncidentQuarantineMinutes] =
    useState("60");
  const [memoryIncidentSeverity, setMemoryIncidentSeverity] = useState("high");
  const [memoryIncidentQuorum, setMemoryIncidentQuorum] = useState("1");
  const [memoryIncidentReviewSlaMinutes, setMemoryIncidentReviewSlaMinutes] =
    useState("60");
  const [
    memoryIncidentResponsibleUserIds,
    setMemoryIncidentResponsibleUserIds,
  ] = useState<string[]>([]);
  const [
    memoryIncidentReassignmentReason,
    setMemoryIncidentReassignmentReason,
  ] = useState("");
  const [memoryExerciseScheduleEnabled, setMemoryExerciseScheduleEnabled] =
    useState(false);
  const [memoryExerciseCadenceHours, setMemoryExerciseCadenceHours] =
    useState("168");
  const [
    memoryExerciseHeartbeatSloMinutes,
    setMemoryExerciseHeartbeatSloMinutes,
  ] = useState("15");
  const [memoryReencryptionBatchSize, setMemoryReencryptionBatchSize] =
    useState("100");
  const [memoryReencryptionMaxRetries, setMemoryReencryptionMaxRetries] =
    useState("3");
  const [keyringExpiryWarningDays, setKeyringExpiryWarningDays] =
    useState("14");
  const [keyringAutomaticExitEnabled, setKeyringAutomaticExitEnabled] =
    useState(true);
  const [keyringAutomaticExitBatchSize, setKeyringAutomaticExitBatchSize] =
    useState("100");
  const [keyringFailureAlertThreshold, setKeyringFailureAlertThreshold] =
    useState("3");
  const [keyringSloMinutes, setKeyringSloMinutes] = useState("30");
  const [
    keyringAvailabilityRetentionDays,
    setKeyringAvailabilityRetentionDays,
  ] = useState("30");
  const [keyringOnCallUserIds, setKeyringOnCallUserIds] = useState<string[]>(
    [],
  );
  const [keyringOnCallTimezone, setKeyringOnCallTimezone] =
    useState("America/Sao_Paulo");
  const [keyringOnCallStartHour, setKeyringOnCallStartHour] = useState("0");
  const [keyringOnCallEndHour, setKeyringOnCallEndHour] = useState("24");
  const [keyringIdentityCanaryDays, setKeyringIdentityCanaryDays] =
    useState("14");
  const [
    keyringIdentityCanaryIntervalHours,
    setKeyringIdentityCanaryIntervalHours,
  ] = useState("24");
  const [credentialRenewalDays, setCredentialRenewalDays] = useState("30");
  const [credentialRenewalReason, setCredentialRenewalReason] = useState("");
  const [workloadIdentityReference, setWorkloadIdentityReference] =
    useState("");
  const [workloadIdentityRotationReason, setWorkloadIdentityRotationReason] =
    useState("");
  const [memoryVaultCredentialId, setMemoryVaultCredentialId] = useState("");
  const [memoryJobLegalHoldReason, setMemoryJobLegalHoldReason] = useState<
    "legal_claim" | "regulatory_request" | "audit_preservation"
  >("audit_preservation");
  const [memoryJobLegalReference, setMemoryJobLegalReference] = useState("");
  const [memoryJobLegalRetentionDays, setMemoryJobLegalRetentionDays] =
    useState("90");
  const [memoryJobLegalRenewalDays, setMemoryJobLegalRenewalDays] =
    useState("30");
  const [memoryJobLegalRenewalReference, setMemoryJobLegalRenewalReference] =
    useState("");
  const [memoryReencryptionRetryReason, setMemoryReencryptionRetryReason] =
    useState("");
  const [memoryReencryptionClosureCode, setMemoryReencryptionClosureCode] =
    useState<
      "missing_key" | "corrupted_material" | "budget_exhausted" | "other"
    >("budget_exhausted");
  const [memoryReencryptionClosureReason, setMemoryReencryptionClosureReason] =
    useState("");
  const [memoryRecoveryAssessment, setMemoryRecoveryAssessment] =
    useState<AgentMemoryReencryptionRecoveryAssessment | null>(null);
  const [memoryIncidentIdempotencyKey, setMemoryIncidentIdempotencyKey] =
    useState(() => crypto.randomUUID());
  const [memoryIncidentFeedback, setMemoryIncidentFeedback] = useState<
    string | null
  >(null);
  const [conversationFeedback, setConversationFeedback] = useState<
    string | null
  >(null);
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
    setConversationFeedback(null);
    setMemoryRecoveryAssessment(null);
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
  const memoryPolicy = useQuery({
    queryKey: ["agent-memory-policy", selectedId],
    queryFn: () =>
      request<AgentMemoryPolicyResponse>(`/agents/${selectedId}/memory-policy`),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memories = useQuery({
    queryKey: ["agent-memories", selectedId],
    queryFn: () =>
      request<AgentMemoryResponse[]>(`/agents/${selectedId}/memories`),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryRisk = useQuery({
    queryKey: ["agent-memory-risk", selectedId],
    queryFn: () =>
      request<AgentMemoryRiskSummary>(
        `/agents/${selectedId}/memory-risk-summary`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryIncidents = useQuery({
    queryKey: ["agent-memory-incidents", selectedId],
    queryFn: () =>
      request<AgentTaskMemoryIncidentResponse[]>(
        `/agents/${selectedId}/memory-access-incidents`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryExercises = useQuery({
    queryKey: ["agent-memory-exercises", selectedId],
    queryFn: () =>
      request<AgentMemoryResponseExercise[]>(
        `/agents/${selectedId}/memory-response-exercises`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryExerciseSchedule = useQuery({
    queryKey: ["agent-memory-exercise-schedule", selectedId],
    queryFn: () =>
      request<AgentMemoryExerciseSchedule>(
        `/agents/${selectedId}/memory-response-exercise-schedule`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memorySchedulerMetrics = useQuery({
    queryKey: ["agent-memory-scheduler-metrics", selectedId],
    queryFn: () =>
      request<AgentMemorySchedulerMetrics>(
        `/agents/${selectedId}/memory-response-exercise-scheduler-metrics`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryReencryptionJobs = useQuery({
    queryKey: ["agent-memory-reencryption-jobs", selectedId],
    queryFn: () =>
      request<AgentMemoryReencryptionJob[]>(
        `/agents/${selectedId}/memory-reencryption-jobs`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const latestMemoryReencryptionJob = memoryReencryptionJobs.data?.[0];
  const memoryVaultCredentials = useQuery({
    queryKey: ["agent-memory-vault-credentials", selectedId],
    queryFn: () =>
      request<AgentMemoryVaultCredentialOption[]>(
        `/agents/${selectedId}/memory-vault-credentials`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryKeyringStatus = useQuery({
    queryKey: ["agent-memory-keyring", selectedId],
    queryFn: () =>
      request<AgentMemoryKeyringStatus>(`/agents/${selectedId}/memory-keyring`),
    enabled: canConfigure && Boolean(selectedId),
    refetchInterval: 15_000,
  });
  const memoryKeyringPolicy = useQuery({
    queryKey: ["agent-memory-keyring-policy", me?.current_company?.id],
    queryFn: () =>
      request<AgentMemoryKeyringPolicy>("/agents/memory-keyring/policy"),
    enabled: canConfigure && Boolean(me?.current_company),
  });
  const credentialRenewals = useQuery({
    queryKey: ["agent-memory-credential-renewals", selectedId],
    queryFn: () =>
      request<AgentMemoryCredentialRenewal[]>(
        `/agents/${selectedId}/memory-keyring/credential-renewals`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryVaultAvailability = useQuery({
    queryKey: ["agent-memory-vault-availability", me?.current_company?.id],
    queryFn: () =>
      request<AgentMemoryVaultAvailability[]>(
        "/agents/memory-keyring/availability?days=7",
      ),
    enabled: canConfigure && Boolean(me?.current_company),
    refetchInterval: 60_000,
  });
  const workloadIdentityRotations = useQuery({
    queryKey: ["agent-memory-workload-identity-rotations", selectedId],
    queryFn: () =>
      request<AgentMemoryWorkloadIdentityRotation[]>(
        `/agents/${selectedId}/memory-keyring/identity-rotations`,
      ),
    enabled: canConfigure && Boolean(selectedId),
  });
  const memoryVaultIncidents = useQuery({
    queryKey: ["agent-memory-vault-incidents", selectedId],
    queryFn: () =>
      request<AgentMemoryVaultIncident[]>(
        `/agents/${selectedId}/memory-vault-incidents`,
      ),
    enabled: canConfigure && Boolean(selectedId),
    refetchInterval: 15_000,
  });
  const managedVaultMetrics = useQuery({
    queryKey: ["managed-vault-metrics", me?.current_company?.id],
    queryFn: () =>
      request<ManagedVaultMetric[]>("/plugins/managed-vault-metrics/summary"),
    enabled: canManagePlugins && Boolean(me?.current_company),
    refetchInterval: 15_000,
  });
  const memoryReencryptionLegalHolds = useQuery({
    queryKey: [
      "agent-memory-reencryption-legal-holds",
      selectedId,
      latestMemoryReencryptionJob?.id,
    ],
    queryFn: () =>
      request<AgentMemoryReencryptionLegalHold[]>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds`,
      ),
    enabled:
      canConfigure &&
      Boolean(selectedId && latestMemoryReencryptionJob) &&
      ["completed", "failed", "closed"].includes(
        latestMemoryReencryptionJob?.status ?? "",
      ),
  });
  const renewableMemoryLegalHold = memoryReencryptionLegalHolds.data?.find(
    (hold) => hold.status === "approved",
  );
  const memoryReencryptionLegalHoldRenewals = useQuery({
    queryKey: [
      "agent-memory-reencryption-legal-hold-renewals",
      selectedId,
      latestMemoryReencryptionJob?.id,
      renewableMemoryLegalHold?.id,
    ],
    queryFn: () =>
      request<AgentMemoryLegalHoldRenewal[]>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds/${renewableMemoryLegalHold?.id}/renewals`,
      ),
    enabled: canConfigure && Boolean(renewableMemoryLegalHold),
  });
  useEffect(() => {
    setMemoryRecoveryAssessment(null);
  }, [latestMemoryReencryptionJob?.id, latestMemoryReencryptionJob?.status]);
  const myMemories = useQuery({
    queryKey: ["agent-my-memories", selectedId],
    queryFn: () =>
      request<AgentMemoryResponse[]>(`/agents/${selectedId}/my-memories`),
    enabled: canExecute && Boolean(selectedId),
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
  useEffect(() => {
    if (!memoryPolicy.data) return;
    setMemoryDefaultRetention(String(memoryPolicy.data.default_retention_days));
    setMemoryMaxRetention(String(memoryPolicy.data.max_retention_days));
    setMemoryScopes(memoryPolicy.data.allowed_scopes);
    setMemoryClassifications(memoryPolicy.data.allowed_classifications);
    setMemoryConsentRequired(memoryPolicy.data.require_consent_for_user_scope);
    setMemoryRetrievalEnabled(memoryPolicy.data.retrieval_enabled);
    setMemoryRetrievalLimit(String(memoryPolicy.data.max_retrieval_entries));
    setMemoryMaxContextTokens(String(memoryPolicy.data.max_context_tokens));
    setMemoryMaxSharedEntries(
      String(memoryPolicy.data.max_shared_context_entries),
    );
    setMemoryMaxSharedCharacters(
      String(memoryPolicy.data.max_shared_context_characters),
    );
    setMemoryBlockedAlertThreshold(
      String(memoryPolicy.data.blocked_context_alert_threshold),
    );
    setMemoryScopeRetention(
      Object.fromEntries(
        memoryPolicy.data.scope_policies.map((item) => [
          item.scope,
          String(item.retention_days),
        ]),
      ),
    );
    setMemoryRetrievalScopes(
      memoryPolicy.data.scope_policies
        .filter((item) => item.retrieval_enabled)
        .map((item) => item.scope),
    );
    setMemoryPurposeRetention(
      Object.fromEntries(
        memoryPolicy.data.purpose_policies.map((item) => [
          item.purpose,
          String(item.retention_days),
        ]),
      ),
    );
    setEnabledMemoryPurposes(
      memoryPolicy.data.purpose_policies
        .filter((item) => item.enabled)
        .map((item) => item.purpose),
    );
  }, [memoryPolicy.data]);
  useEffect(() => {
    if (!memoryExerciseSchedule.data) return;
    setMemoryExerciseScheduleEnabled(memoryExerciseSchedule.data.enabled);
    setMemoryExerciseCadenceHours(
      String(memoryExerciseSchedule.data.cadence_hours),
    );
    setMemoryExerciseHeartbeatSloMinutes(
      String(memoryExerciseSchedule.data.heartbeat_slo_minutes),
    );
  }, [memoryExerciseSchedule.data]);
  useEffect(() => {
    if (!memoryKeyringPolicy.data) return;
    setKeyringExpiryWarningDays(
      String(memoryKeyringPolicy.data.expiry_warning_days),
    );
    setKeyringAutomaticExitEnabled(
      memoryKeyringPolicy.data.automatic_exit_enabled,
    );
    setKeyringAutomaticExitBatchSize(
      String(memoryKeyringPolicy.data.automatic_exit_batch_size),
    );
    setKeyringFailureAlertThreshold(
      String(memoryKeyringPolicy.data.vault_failure_alert_threshold),
    );
    setKeyringSloMinutes(String(memoryKeyringPolicy.data.vault_slo_minutes));
    setKeyringAvailabilityRetentionDays(
      String(memoryKeyringPolicy.data.availability_retention_days),
    );
    setKeyringOnCallUserIds(memoryKeyringPolicy.data.on_call_user_ids);
    setKeyringOnCallTimezone(memoryKeyringPolicy.data.on_call_timezone);
    setKeyringOnCallStartHour(
      String(memoryKeyringPolicy.data.on_call_start_hour),
    );
    setKeyringOnCallEndHour(String(memoryKeyringPolicy.data.on_call_end_hour));
    setKeyringIdentityCanaryDays(
      String(memoryKeyringPolicy.data.identity_canary_days),
    );
    setKeyringIdentityCanaryIntervalHours(
      String(memoryKeyringPolicy.data.identity_canary_interval_hours),
    );
  }, [memoryKeyringPolicy.data]);

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
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-policy", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memories", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-my-memories", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-risk", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-incidents", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-exercises", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-exercise-schedule", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-scheduler-metrics", selectedId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["agent-memory-reencryption-jobs", selectedId],
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
      setConversationFeedback(null);
      setMessage("");
      refresh();
    },
  });
  const closeConversation = useMutation({
    mutationFn: () =>
      request<AgentConversationCloseResponse>(
        `/agents/${selectedId}/conversations/${conversationId}/close`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      setConversationId(null);
      setConversationFeedback(
        result.deleted_memories
          ? `Conversa encerrada e ${result.deleted_memories} memória(s) eliminada(s).`
          : "Conversa encerrada sem memória temporária armazenada.",
      );
      refresh();
    },
    onError: (caught) => setConversationFeedback(errorMessage(caught)),
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
  const saveMemoryPolicy = useMutation({
    mutationFn: () =>
      request<AgentMemoryPolicyResponse>(
        `/agents/${selectedId}/memory-policy`,
        {
          method: "PUT",
          body: {
            default_retention_days: Number(memoryDefaultRetention),
            max_retention_days: Number(memoryMaxRetention),
            allowed_scopes: memoryScopes,
            allowed_classifications: memoryClassifications,
            require_consent_for_user_scope: memoryConsentRequired,
            retrieval_enabled: memoryRetrievalEnabled,
            max_retrieval_entries: Number(memoryRetrievalLimit),
            max_context_tokens: Number(memoryMaxContextTokens),
            max_shared_context_entries: Number(memoryMaxSharedEntries),
            max_shared_context_characters: Number(memoryMaxSharedCharacters),
            blocked_context_alert_threshold: Number(
              memoryBlockedAlertThreshold,
            ),
            scope_policies: memoryScopes.map((scope) => ({
              scope,
              retention_days: Number(
                memoryScopeRetention[scope] ?? memoryDefaultRetention,
              ),
              retrieval_enabled: memoryRetrievalScopes.includes(scope),
            })),
            purpose_policies: [
              "service",
              "personalization",
              "operations",
              "compliance",
              "analytics",
            ].map((purpose) => ({
              purpose,
              retention_days: Number(
                memoryPurposeRetention[purpose] ?? memoryDefaultRetention,
              ),
              enabled: enabledMemoryPurposes.includes(purpose),
            })),
          },
        },
      ),
    onSuccess: () => {
      setMemoryFeedback("Política de memória atualizada.");
      refresh();
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
  });
  const purgeExpiredMemories = useMutation({
    mutationFn: () =>
      request<{ deleted_count: number }>(`/agents/${selectedId}/memory-purge`, {
        method: "POST",
        body: { expired_only: true, confirm_all: false },
      }),
    onSuccess: (result) => {
      setMemoryFeedback(
        result.deleted_count
          ? `${result.deleted_count} memória(s) expirada(s) eliminada(s).`
          : "Nenhuma memória expirada encontrada.",
      );
      refresh();
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
  });
  const revokeMemoryAccessForIncident = useMutation({
    mutationFn: () =>
      request<AgentTaskMemoryIncidentResponse>(
        `/agents/${selectedId}/memory-access-incidents/revoke`,
        {
          method: "POST",
          body: {
            incident_reference: memoryIncidentReference,
            reason: memoryIncidentReason,
            quarantine_minutes: Number(memoryIncidentQuarantineMinutes),
            severity: memoryIncidentSeverity,
            required_review_quorum: Number(memoryIncidentQuorum),
            review_sla_minutes: Number(memoryIncidentReviewSlaMinutes),
            responsible_user_ids: memoryIncidentResponsibleUserIds,
            idempotency_key: memoryIncidentIdempotencyKey,
          },
        },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.already_processed
          ? "Este incidente já havia sido processado com segurança."
          : `${result.revoked_grants} autorização(ões) de memória revogada(s).`,
      );
      setMemoryIncidentReference("");
      setMemoryIncidentReason("");
      setMemoryIncidentResponsibleUserIds([]);
      setMemoryIncidentIdempotencyKey(crypto.randomUUID());
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const reviewMemoryIncident = useMutation({
    mutationFn: ({
      incidentId,
      decision,
    }: {
      incidentId: string;
      decision: "confirmed" | "dismissed";
    }) =>
      request<AgentTaskMemoryIncidentResponse>(
        `/agents/${selectedId}/memory-access-incidents/${incidentId}/review`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.review_status === "confirmed"
          ? "Incidente confirmado por revisão independente."
          : "Incidente descartado e quarentena liberada.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const reassignMemoryIncident = useMutation({
    mutationFn: (incidentId: string) =>
      request<AgentTaskMemoryIncidentResponse>(
        `/agents/${selectedId}/memory-access-incidents/${incidentId}/responsibles`,
        {
          method: "PUT",
          body: {
            responsible_user_ids: memoryIncidentResponsibleUserIds,
            reason: memoryIncidentReassignmentReason,
          },
        },
      ),
    onSuccess: () => {
      setMemoryIncidentFeedback(
        "Responsáveis atualizados com cadeia de custódia preservada.",
      );
      setMemoryIncidentReassignmentReason("");
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const escalateOverdueMemoryIncidents = useMutation({
    mutationFn: () =>
      request<{ escalated_count: number; escalated_at: string }>(
        `/agents/${selectedId}/memory-access-incidents/escalate-overdue`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.escalated_count
          ? `${result.escalated_count} revisão(ões) atrasada(s) escalonada(s).`
          : "Nenhuma revisão atrasada aguardando escalonamento.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const rotateMemoryRiskSigningKey = useMutation({
    mutationFn: () =>
      request<AgentMemoryRiskSigningKey>(
        `/agents/${selectedId}/memory-risk-signing-keys/rotate`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        `Assinatura rotacionada para a versão ${result.version}. Relatórios anteriores continuam verificáveis.`,
      );
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const exportMemoryRiskReport = useMutation({
    mutationFn: () =>
      request<AgentMemoryRiskReport>(
        `/agents/${selectedId}/memory-risk-report`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(result, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `orkestral-risco-memoria-${selectedId}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMemoryIncidentFeedback("Relatório assinado exportado com sucesso.");
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const runMemoryResponseExercise = useMutation({
    mutationFn: () =>
      request<AgentMemoryResponseExercise>(
        `/agents/${selectedId}/memory-response-exercises`,
        { method: "POST", body: { scenario: "full" } },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.status === "passed"
          ? "Exercício concluído: todos os controles responderam corretamente."
          : "Exercício encontrou um controle que exige revisão.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const saveMemoryExerciseSchedule = useMutation({
    mutationFn: () =>
      request<AgentMemoryExerciseSchedule>(
        `/agents/${selectedId}/memory-response-exercise-schedule`,
        {
          method: "PUT",
          body: {
            enabled: memoryExerciseScheduleEnabled,
            cadence_hours: Number(memoryExerciseCadenceHours),
            heartbeat_slo_minutes: Number(memoryExerciseHeartbeatSloMinutes),
          },
        },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.enabled
          ? `Agenda ativada a cada ${result.cadence_hours} hora(s).`
          : "Agenda recorrente desativada.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const runDueMemoryExercise = useMutation({
    mutationFn: () =>
      request<AgentMemoryExerciseDue>(
        `/agents/${selectedId}/memory-response-exercise-schedule/run-due`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.executed
          ? "Exercício agendado executado e registrado."
          : "A agenda ainda não atingiu o próximo horário de execução.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const startMemoryReencryption = useMutation({
    mutationFn: () =>
      request<AgentMemoryReencryptionJob>(
        `/agents/${selectedId}/memory-reencryption-jobs`,
        {
          method: "POST",
          body: {
            batch_size: Number(memoryReencryptionBatchSize),
            max_retry_attempts: Number(memoryReencryptionMaxRetries),
            key_credential_id: memoryVaultCredentialId.trim() || null,
          },
        },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.total_count
          ? `Recriptografia iniciada para ${result.total_count} memória(s).`
          : "Job criado; não há memórias para recriptografar.",
      );
      setMemoryRecoveryAssessment(null);
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const exitManagedMemoryKeyring = useMutation({
    mutationFn: () =>
      request<AgentMemoryReencryptionJob>(
        `/agents/${selectedId}/memory-keyring/exit`,
        {
          method: "POST",
          body: {
            batch_size: Number(memoryReencryptionBatchSize),
            max_retry_attempts: Number(memoryReencryptionMaxRetries),
          },
        },
      ),
    onSuccess: () => {
      setMemoryIncidentFeedback(
        "Saída segura iniciada. O vínculo só será revogado após a recriptografia.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const updateMemoryKeyringPolicy = useMutation({
    mutationFn: () =>
      request<AgentMemoryKeyringPolicy>("/agents/memory-keyring/policy", {
        method: "PUT",
        body: {
          expiry_warning_days: Number(keyringExpiryWarningDays),
          automatic_exit_enabled: keyringAutomaticExitEnabled,
          automatic_exit_batch_size: Number(keyringAutomaticExitBatchSize),
          vault_failure_alert_threshold: Number(keyringFailureAlertThreshold),
          vault_slo_minutes: Number(keyringSloMinutes),
          availability_retention_days: Number(keyringAvailabilityRetentionDays),
          on_call_user_ids: keyringOnCallUserIds,
          on_call_timezone: keyringOnCallTimezone,
          on_call_start_hour: Number(keyringOnCallStartHour),
          on_call_end_hour: Number(keyringOnCallEndHour),
          identity_canary_days: Number(keyringIdentityCanaryDays),
          identity_canary_interval_hours: Number(
            keyringIdentityCanaryIntervalHours,
          ),
        },
      }),
    onSuccess: (policy) => {
      setKeyringExpiryWarningDays(String(policy.expiry_warning_days));
      setKeyringAutomaticExitEnabled(policy.automatic_exit_enabled);
      setKeyringAutomaticExitBatchSize(
        String(policy.automatic_exit_batch_size),
      );
      setKeyringFailureAlertThreshold(
        String(policy.vault_failure_alert_threshold),
      );
      setKeyringSloMinutes(String(policy.vault_slo_minutes));
      setKeyringAvailabilityRetentionDays(
        String(policy.availability_retention_days),
      );
      setKeyringOnCallUserIds(policy.on_call_user_ids);
      setKeyringOnCallTimezone(policy.on_call_timezone);
      setKeyringOnCallStartHour(String(policy.on_call_start_hour));
      setKeyringOnCallEndHour(String(policy.on_call_end_hour));
      setKeyringIdentityCanaryDays(String(policy.identity_canary_days));
      setKeyringIdentityCanaryIntervalHours(
        String(policy.identity_canary_interval_hours),
      );
      setMemoryIncidentFeedback(
        "Política do cofre atualizada para esta empresa.",
      );
      void memoryKeyringPolicy.refetch();
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const requestCredentialRenewal = useMutation({
    mutationFn: () =>
      request<AgentMemoryCredentialRenewal>(
        `/agents/${selectedId}/memory-keyring/credential-renewals`,
        {
          method: "POST",
          body: {
            extension_days: Number(credentialRenewalDays),
            reason: credentialRenewalReason,
          },
        },
      ),
    onSuccess: () => {
      setCredentialRenewalReason("");
      setMemoryIncidentFeedback(
        "Renovação solicitada. Outro administrador precisa decidir.",
      );
      void credentialRenewals.refetch();
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const decideCredentialRenewal = useMutation({
    mutationFn: ({
      renewalId,
      decision,
    }: {
      renewalId: string;
      decision: "approved" | "rejected";
    }) =>
      request<AgentMemoryCredentialRenewal>(
        `/agents/${selectedId}/memory-keyring/credential-renewals/${renewalId}/decision`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: (renewal) => {
      setMemoryIncidentFeedback(
        renewal.status === "approved"
          ? "Validade da credencial renovada com aprovação independente."
          : "Renovação rejeitada; a política de saída segura continua ativa.",
      );
      void credentialRenewals.refetch();
      void memoryKeyringStatus.refetch();
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const requestWorkloadIdentityRotation = useMutation({
    mutationFn: () =>
      request<AgentMemoryWorkloadIdentityRotation>(
        `/agents/${selectedId}/memory-keyring/identity-rotations`,
        {
          method: "POST",
          body: {
            identity_reference: workloadIdentityReference,
            reason: workloadIdentityRotationReason,
          },
        },
      ),
    onSuccess: () => {
      setWorkloadIdentityReference("");
      setWorkloadIdentityRotationReason("");
      setMemoryIncidentFeedback(
        "Rotação solicitada. Outro administrador deve validar e aprovar.",
      );
      void workloadIdentityRotations.refetch();
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const decideWorkloadIdentityRotation = useMutation({
    mutationFn: ({
      rotationId,
      decision,
    }: {
      rotationId: string;
      decision: "approved" | "rejected";
    }) =>
      request<AgentMemoryWorkloadIdentityRotation>(
        `/agents/${selectedId}/memory-keyring/identity-rotations/${rotationId}/decision`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: (rotation) => {
      setMemoryIncidentFeedback(
        rotation.status === "approved"
          ? "Nova identidade validada no cofre e ativada."
          : "Rotação rejeitada; a identidade atual foi preservada.",
      );
      void workloadIdentityRotations.refetch();
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const assessMemoryReencryptionRecovery = useMutation({
    mutationFn: (jobId: string) =>
      request<AgentMemoryReencryptionRecoveryAssessment>(
        `/agents/${selectedId}/memory-reencryption-jobs/${jobId}/recovery-assessment`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      setMemoryRecoveryAssessment(result);
      setMemoryIncidentFeedback(
        result.status === "ready"
          ? "Diagnóstico aprovado. A retomada está liberada por 15 minutos."
          : "Diagnóstico bloqueado. Siga as orientações antes de retomar.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const retryMemoryReencryption = useMutation({
    mutationFn: (jobId: string) =>
      request<AgentMemoryReencryptionJob>(
        `/agents/${selectedId}/memory-reencryption-jobs/${jobId}/retry`,
        {
          method: "POST",
          body: { reason: memoryReencryptionRetryReason },
        },
      ),
    onSuccess: () => {
      setMemoryIncidentFeedback(
        "Job retomado a partir do último checkpoint seguro.",
      );
      setMemoryReencryptionRetryReason("");
      setMemoryRecoveryAssessment(null);
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const closeMemoryReencryption = useMutation({
    mutationFn: (jobId: string) =>
      request<AgentMemoryReencryptionJob>(
        `/agents/${selectedId}/memory-reencryption-jobs/${jobId}/close`,
        {
          method: "POST",
          body: {
            closure_code: memoryReencryptionClosureCode,
            reason: memoryReencryptionClosureReason,
          },
        },
      ),
    onSuccess: () => {
      setMemoryIncidentFeedback(
        "Job encerrado definitivamente com auditoria e material sensível protegido.",
      );
      setMemoryReencryptionClosureReason("");
      setMemoryRecoveryAssessment(null);
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const requestMemoryReencryptionLegalHold = useMutation({
    mutationFn: () =>
      request<AgentMemoryReencryptionLegalHold>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds`,
        {
          method: "POST",
          body: {
            reason_code: memoryJobLegalHoldReason,
            legal_reference: memoryJobLegalReference,
            retention_days: Number(memoryJobLegalRetentionDays),
          },
        },
      ),
    onSuccess: () => {
      setMemoryIncidentFeedback(
        "Retenção legal solicitada e aguardando decisão independente.",
      );
      setMemoryJobLegalReference("");
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const decideMemoryReencryptionLegalHold = useMutation({
    mutationFn: ({
      holdId,
      decision,
    }: {
      holdId: string;
      decision: "approved" | "rejected";
    }) =>
      request<AgentMemoryReencryptionLegalHold>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds/${holdId}/decision`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.status === "approved"
          ? "Retenção legal aprovada; o expurgo está suspenso."
          : "Retenção legal rejeitada com auditoria.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const requestMemoryReencryptionLegalHoldRenewal = useMutation({
    mutationFn: () =>
      request<AgentMemoryLegalHoldRenewal>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds/${renewableMemoryLegalHold?.id}/renewals`,
        {
          method: "POST",
          body: {
            extension_days: Number(memoryJobLegalRenewalDays),
            legal_reference: memoryJobLegalRenewalReference,
          },
        },
      ),
    onSuccess: () => {
      setMemoryJobLegalRenewalReference("");
      setMemoryIncidentFeedback(
        "Renovação solicitada e encaminhada para aprovação independente.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const decideMemoryReencryptionLegalHoldRenewal = useMutation({
    mutationFn: ({
      renewalId,
      decision,
    }: {
      renewalId: string;
      decision: "approved" | "rejected";
    }) =>
      request<AgentMemoryLegalHoldRenewal>(
        `/agents/${selectedId}/memory-reencryption-jobs/${latestMemoryReencryptionJob?.id}/legal-holds/${renewableMemoryLegalHold?.id}/renewals/${renewalId}/decision`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: (result) => {
      setMemoryIncidentFeedback(
        result.status === "approved"
          ? "Renovação aprovada e prazo ampliado."
          : "Renovação rejeitada sem alterar o prazo atual.",
      );
      refresh();
    },
    onError: (caught) => setMemoryIncidentFeedback(errorMessage(caught)),
  });
  const deleteMemory = useMutation({
    mutationFn: (memoryId: string) =>
      request<void>(`/agents/${selectedId}/memories/${memoryId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      setMemoryFeedback("Memória eliminada do banco ativo.");
      refresh();
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
  });
  const revokeMemoryConsent = useMutation({
    mutationFn: () =>
      request<AgentMemoryConsentRevocationResponse>(
        `/agents/${selectedId}/memory-consent-revocations`,
        {
          method: "POST",
          body: {
            subject_user_id: memoryConsentSubjectUserId,
            consent_reference: memoryConsentReference,
          },
        },
      ),
    onSuccess: (result) => {
      setMemoryConsentReference("");
      setMemoryFeedback(
        result.already_revoked
          ? "Consentimento já estava revogado; nenhuma memória voltou a ser utilizada."
          : `${result.deleted_count} memória(s) pessoal(is) eliminada(s) e consentimento revogado.`,
      );
      refresh();
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
  });
  const deleteMyMemory = useMutation({
    mutationFn: (memoryId: string) =>
      request<void>(`/agents/${selectedId}/my-memories/${memoryId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      setMemoryFeedback("Sua memória pessoal foi eliminada.");
      refresh();
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
  });
  const exportMyMemories = useMutation({
    mutationFn: () =>
      request<AgentMemoryMetadataExport>(
        `/agents/${selectedId}/my-memory-export`,
      ),
    onSuccess: (result) => {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(result, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `orkestral-memorias-${selectedId}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMemoryFeedback(
        `${result.total} metadado(s) de memória exportado(s), sem conteúdo protegido.`,
      );
    },
    onError: (caught) => setMemoryFeedback(errorMessage(caught)),
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
                className="agent-memory-card"
                eyebrow="Privacidade por padrão"
                title="Governança da memória"
              >
                <p>
                  Defina por quanto tempo o agente pode conservar contexto. O
                  conteúdo fica criptografado e nunca aparece em listas, eventos
                  ou auditorias.
                </p>
                {memoryFeedback ? <Alert>{memoryFeedback}</Alert> : null}
                <form
                  className="agent-policy-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    saveMemoryPolicy.mutate();
                  }}
                >
                  <TextField
                    label="Retenção padrão (dias)"
                    min={1}
                    onChange={(event) =>
                      setMemoryDefaultRetention(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryDefaultRetention}
                  />
                  <TextField
                    label="Limite máximo (dias)"
                    min={1}
                    onChange={(event) =>
                      setMemoryMaxRetention(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryMaxRetention}
                  />
                  <fieldset className="agent-memory-options">
                    <legend>Escopos permitidos</legend>
                    {[
                      ["conversation", "Conversa"],
                      ["task", "Tarefa"],
                      ["user", "Pessoa"],
                      ["company", "Empresa"],
                      ["operational", "Operacional"],
                    ].map(([value, label]) => (
                      <label key={value}>
                        <input
                          checked={memoryScopes.includes(value)}
                          onChange={(event) =>
                            setMemoryScopes((current) =>
                              event.target.checked
                                ? [...new Set([...current, value])]
                                : current.filter((item) => item !== value),
                            )
                          }
                          type="checkbox"
                        />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                  <fieldset className="agent-memory-options">
                    <legend>Classificações permitidas</legend>
                    {[
                      ["public", "Pública"],
                      ["internal", "Interna"],
                      ["confidential", "Confidencial"],
                      ["restricted", "Restrita"],
                    ].map(([value, label]) => (
                      <label key={value}>
                        <input
                          checked={memoryClassifications.includes(value)}
                          onChange={(event) =>
                            setMemoryClassifications((current) =>
                              event.target.checked
                                ? [...new Set([...current, value])]
                                : current.filter((item) => item !== value),
                            )
                          }
                          type="checkbox"
                        />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                  <label className="agent-memory-consent">
                    <input
                      checked={memoryConsentRequired}
                      onChange={(event) =>
                        setMemoryConsentRequired(event.target.checked)
                      }
                      type="checkbox"
                    />
                    Exigir referência de consentimento para memória pessoal
                  </label>
                  <label className="agent-memory-consent">
                    <input
                      checked={memoryRetrievalEnabled}
                      onChange={(event) =>
                        setMemoryRetrievalEnabled(event.target.checked)
                      }
                      type="checkbox"
                    />
                    Permitir recuperação das memórias autorizadas pelo modelo
                  </label>
                  <TextField
                    label="Máximo por consulta"
                    max={20}
                    min={1}
                    onChange={(event) =>
                      setMemoryRetrievalLimit(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryRetrievalLimit}
                  />
                  <TextField
                    label="Orçamento do contexto (tokens estimados)"
                    max={16000}
                    min={128}
                    onChange={(event) =>
                      setMemoryMaxContextTokens(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryMaxContextTokens}
                  />
                  <TextField
                    label="Máximo compartilhado por tarefa (itens)"
                    max={20}
                    min={1}
                    onChange={(event) =>
                      setMemoryMaxSharedEntries(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryMaxSharedEntries}
                  />
                  <TextField
                    label="Máximo compartilhado por tarefa (caracteres)"
                    max={16000}
                    min={64}
                    onChange={(event) =>
                      setMemoryMaxSharedCharacters(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryMaxSharedCharacters}
                  />
                  <TextField
                    label="Alertar após contextos bloqueados"
                    max={20}
                    min={2}
                    onChange={(event) =>
                      setMemoryBlockedAlertThreshold(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryBlockedAlertThreshold}
                  />
                  <fieldset className="agent-memory-options">
                    <legend>Retenção e recuperação por escopo</legend>
                    {memoryScopes.map((scope) => (
                      <div key={scope}>
                        <TextField
                          label={`${scope} · retenção (dias)`}
                          max={Number(memoryMaxRetention)}
                          min={1}
                          onChange={(event) =>
                            setMemoryScopeRetention((current) => ({
                              ...current,
                              [scope]: event.target.value,
                            }))
                          }
                          required
                          type="number"
                          value={
                            memoryScopeRetention[scope] ??
                            memoryDefaultRetention
                          }
                        />
                        <label>
                          <input
                            checked={memoryRetrievalScopes.includes(scope)}
                            onChange={(event) =>
                              setMemoryRetrievalScopes((current) =>
                                event.target.checked
                                  ? [...new Set([...current, scope])]
                                  : current.filter((item) => item !== scope),
                              )
                            }
                            type="checkbox"
                          />
                          Recuperar este escopo
                        </label>
                      </div>
                    ))}
                  </fieldset>
                  <fieldset className="agent-memory-options">
                    <legend>Retenção por finalidade</legend>
                    {[
                      ["service", "Atendimento"],
                      ["personalization", "Personalização"],
                      ["operations", "Operações"],
                      ["compliance", "Conformidade"],
                      ["analytics", "Análises"],
                    ].map(([purpose, label]) => (
                      <div key={purpose}>
                        <TextField
                          label={`${label} · retenção (dias)`}
                          max={Number(memoryMaxRetention)}
                          min={1}
                          onChange={(event) =>
                            setMemoryPurposeRetention((current) => ({
                              ...current,
                              [purpose]: event.target.value,
                            }))
                          }
                          required
                          type="number"
                          value={
                            memoryPurposeRetention[purpose] ??
                            memoryDefaultRetention
                          }
                        />
                        <label>
                          <input
                            checked={enabledMemoryPurposes.includes(purpose)}
                            onChange={(event) =>
                              setEnabledMemoryPurposes((current) =>
                                event.target.checked
                                  ? [...new Set([...current, purpose])]
                                  : current.filter((item) => item !== purpose),
                              )
                            }
                            type="checkbox"
                          />
                          Permitir esta finalidade
                        </label>
                      </div>
                    ))}
                  </fieldset>
                  <div className="form-actions">
                    <Button loading={saveMemoryPolicy.isPending} type="submit">
                      <BrainCircuit size={16} /> Salvar política
                    </Button>
                    <Button
                      loading={purgeExpiredMemories.isPending}
                      onClick={() => purgeExpiredMemories.mutate()}
                      type="button"
                      variant="secondary"
                    >
                      <TimerReset size={16} /> Eliminar expiradas
                    </Button>
                  </div>
                </form>
                {canViewUsers ? (
                  <form
                    className="agent-policy-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      revokeMemoryConsent.mutate();
                    }}
                  >
                    <label>
                      <span>Titular da memória pessoal</span>
                      <select
                        onChange={(event) =>
                          setMemoryConsentSubjectUserId(event.target.value)
                        }
                        required
                        value={memoryConsentSubjectUserId}
                      >
                        <option value="">Selecione uma pessoa</option>
                        {companyUsers.data
                          ?.filter(
                            (user) => user.membership_status === "active",
                          )
                          .map((user) => (
                            <option key={user.user_id} value={user.user_id}>
                              {user.name} · {user.email}
                            </option>
                          ))}
                      </select>
                    </label>
                    <TextField
                      label="Referência do consentimento a revogar"
                      maxLength={160}
                      onChange={(event) =>
                        setMemoryConsentReference(event.target.value)
                      }
                      required
                      value={memoryConsentReference}
                    />
                    <Button
                      loading={revokeMemoryConsent.isPending}
                      type="submit"
                      variant="secondary"
                    >
                      <ShieldAlert size={16} /> Revogar e eliminar memórias
                    </Button>
                  </form>
                ) : null}
                <div className="agent-policy-list">
                  {memories.data?.length ? (
                    memories.data.map((memory) => (
                      <article className="agent-policy-row" key={memory.id}>
                        <div>
                          <strong>
                            {memory.scope} · {memory.classification}
                          </strong>
                          <small>
                            Conteúdo protegido
                            {memory.subject_user_id
                              ? ` · titular ${
                                  companyUsers.data?.find(
                                    (user) =>
                                      user.user_id === memory.subject_user_id,
                                  )?.name ?? "identificado"
                                }`
                              : ""}
                            {memory.consent_recorded
                              ? " · consentimento registrado"
                              : ""}
                            {` · finalidade ${memory.purpose}`}
                            {memory.task_delegation_id
                              ? ` · tarefa ${memory.task_delegation_id.slice(0, 8)}`
                              : ""}
                            {" · expira em "}
                            {new Date(memory.expires_at).toLocaleString(
                              "pt-BR",
                            )}
                          </small>
                        </div>
                        <Button
                          aria-label="Eliminar memória"
                          loading={
                            deleteMemory.isPending &&
                            deleteMemory.variables === memory.id
                          }
                          onClick={() => deleteMemory.mutate(memory.id)}
                          variant="ghost"
                        >
                          <Trash2 size={16} /> Eliminar
                        </Button>
                      </article>
                    ))
                  ) : (
                    <p>Nenhuma memória ativa armazenada.</p>
                  )}
                </div>
              </Card>
            </PermissionGuard>
            <PermissionGuard all={["agents.configure"]}>
              <Card
                className={`agent-memory-risk agent-memory-risk--${memoryRisk.data?.risk_level ?? "low"}`}
                eyebrow="Resposta preventiva"
                title="Risco de memória compartilhada"
              >
                <p>
                  Autorizações vencidas deixam de funcionar automaticamente. Em
                  caso de suspeita, revogue todos os acessos ativos deste agente
                  em uma única operação auditada.
                </p>
                {memoryIncidentFeedback ? (
                  <Alert>{memoryIncidentFeedback}</Alert>
                ) : null}
                <div className="agent-memory-risk__grid">
                  <article>
                    <small>Nível atual</small>
                    <strong>
                      {
                        {
                          low: "Baixo",
                          elevated: "Atenção",
                          high: "Alto",
                          critical: "Crítico",
                        }[memoryRisk.data?.risk_level ?? "low"]
                      }
                    </strong>
                  </article>
                  <article>
                    <small>Acessos ativos</small>
                    <strong>{memoryRisk.data?.active_grants ?? 0}</strong>
                  </article>
                  <article>
                    <small>Restritos ativos</small>
                    <strong>
                      {memoryRisk.data?.restricted_active_grants ?? 0}
                    </strong>
                  </article>
                  <article>
                    <small>Aprovações pendentes</small>
                    <strong>{memoryRisk.data?.pending_approvals ?? 0}</strong>
                  </article>
                  <article>
                    <small>Aprovações vencidas</small>
                    <strong>{memoryRisk.data?.expired_approvals ?? 0}</strong>
                  </article>
                  <article>
                    <small>Bloqueios em 24 h</small>
                    <strong>
                      {(memoryRisk.data?.blocked_events_last_24h ?? 0) +
                        (memoryRisk.data?.cost_denials_last_24h ?? 0)}
                    </strong>
                  </article>
                  <article>
                    <small>Incidentes em 30 dias</small>
                    <strong>
                      {memoryRisk.data?.incidents_last_30_days ?? 0}
                    </strong>
                  </article>
                  <article>
                    <small>Acessos revogados</small>
                    <strong>
                      {memoryRisk.data?.revoked_grants_last_30_days ?? 0}
                    </strong>
                  </article>
                  <article>
                    <small>Revisões pendentes</small>
                    <strong>
                      {memoryRisk.data?.pending_incident_reviews ?? 0}
                    </strong>
                  </article>
                  <article>
                    <small>Revisões atrasadas</small>
                    <strong>
                      {memoryRisk.data?.overdue_incident_reviews ?? 0}
                    </strong>
                  </article>
                  <article>
                    <small>Quarentena</small>
                    <strong>
                      {memoryRisk.data?.quarantined ? "Ativa" : "Livre"}
                    </strong>
                  </article>
                </div>
                <div className="form-actions">
                  <Button
                    loading={exportMemoryRiskReport.isPending}
                    onClick={() => exportMemoryRiskReport.mutate()}
                    type="button"
                    variant="secondary"
                  >
                    <Download size={16} /> Exportar relatório assinado
                  </Button>
                  <Button
                    loading={runMemoryResponseExercise.isPending}
                    onClick={() => runMemoryResponseExercise.mutate()}
                    type="button"
                    variant="secondary"
                  >
                    <ShieldAlert size={16} /> Executar exercício de resposta
                  </Button>
                  <Button
                    loading={escalateOverdueMemoryIncidents.isPending}
                    onClick={() => escalateOverdueMemoryIncidents.mutate()}
                    type="button"
                    variant="secondary"
                  >
                    <TimerReset size={16} /> Escalonar revisões atrasadas
                  </Button>
                  <Button
                    loading={rotateMemoryRiskSigningKey.isPending}
                    onClick={() => rotateMemoryRiskSigningKey.mutate()}
                    type="button"
                    variant="secondary"
                  >
                    <LockKeyhole size={16} /> Rotacionar assinatura
                  </Button>
                </div>
                <form
                  className="agent-policy-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!memoryIncidentResponsibleUserIds.length) {
                      setMemoryIncidentFeedback(
                        "Selecione ao menos uma pessoa responsável pela revisão.",
                      );
                      return;
                    }
                    revokeMemoryAccessForIncident.mutate();
                  }}
                >
                  <TextField
                    label="Referência interna do incidente"
                    maxLength={160}
                    onChange={(event) =>
                      setMemoryIncidentReference(event.target.value)
                    }
                    required
                    value={memoryIncidentReference}
                  />
                  <TextField
                    label="Motivo da revogação"
                    maxLength={160}
                    onChange={(event) =>
                      setMemoryIncidentReason(event.target.value)
                    }
                    required
                    value={memoryIncidentReason}
                  />
                  <TextField
                    label="Quarentena (minutos)"
                    max={1440}
                    min={5}
                    onChange={(event) =>
                      setMemoryIncidentQuarantineMinutes(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryIncidentQuarantineMinutes}
                  />
                  <label className="native-field">
                    <span>Severidade</span>
                    <select
                      onChange={(event) => {
                        setMemoryIncidentSeverity(event.target.value);
                        if (event.target.value === "critical") {
                          setMemoryIncidentQuorum((current) =>
                            Number(current) < 2 ? "2" : current,
                          );
                        }
                      }}
                      value={memoryIncidentSeverity}
                    >
                      <option value="low">Baixa</option>
                      <option value="medium">Média</option>
                      <option value="high">Alta</option>
                      <option value="critical">Crítica</option>
                    </select>
                  </label>
                  <TextField
                    label="Quorum de revisão"
                    max={5}
                    min={memoryIncidentSeverity === "critical" ? 2 : 1}
                    onChange={(event) =>
                      setMemoryIncidentQuorum(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryIncidentQuorum}
                  />
                  <TextField
                    label="Prazo para revisão (minutos)"
                    max={1440}
                    min={5}
                    onChange={(event) =>
                      setMemoryIncidentReviewSlaMinutes(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryIncidentReviewSlaMinutes}
                  />
                  <fieldset className="agent-policy-list">
                    <legend>Responsáveis independentes pela revisão</legend>
                    {companyUsers.data
                      ?.filter(
                        (user) =>
                          user.user_id !== me?.user.id &&
                          user.user_status === "active" &&
                          user.membership_status === "active",
                      )
                      .map((user) => (
                        <label className="native-field" key={user.user_id}>
                          <input
                            checked={memoryIncidentResponsibleUserIds.includes(
                              user.user_id,
                            )}
                            onChange={(event) =>
                              setMemoryIncidentResponsibleUserIds((current) =>
                                event.target.checked
                                  ? [...current, user.user_id]
                                  : current.filter((id) => id !== user.user_id),
                              )
                            }
                            type="checkbox"
                          />
                          <span>
                            {user.name} · {user.email}
                          </span>
                        </label>
                      ))}
                    {!companyUsers.data?.some(
                      (user) =>
                        user.user_id !== me?.user.id &&
                        user.user_status === "active" &&
                        user.membership_status === "active",
                    ) ? (
                      <small>
                        Cadastre outra pessoa autorizada para realizar a revisão
                        independente.
                      </small>
                    ) : null}
                  </fieldset>
                  <Button
                    loading={revokeMemoryAccessForIncident.isPending}
                    type="submit"
                    variant="secondary"
                  >
                    <ShieldAlert size={16} /> Revogar acessos por incidente
                  </Button>
                </form>
                <TextField
                  label="Justificativa para reatribuição"
                  maxLength={160}
                  onChange={(event) =>
                    setMemoryIncidentReassignmentReason(event.target.value)
                  }
                  value={memoryIncidentReassignmentReason}
                />
                <small>
                  Para reatribuir, selecione acima os novos responsáveis e
                  informe a justificativa. Pessoas que já votaram não podem ser
                  removidas.
                </small>
                <div className="agent-policy-list">
                  {memoryIncidents.data?.length ? (
                    memoryIncidents.data.map((incident) => (
                      <article className="agent-policy-row" key={incident.id}>
                        <div>
                          <strong>
                            Incidente {incident.id.slice(0, 8)} ·{" "}
                            {incident.review_status === "pending"
                              ? "aguardando revisão"
                              : incident.review_status === "confirmed"
                                ? "confirmado"
                                : "descartado"}
                          </strong>
                          <small>
                            {incident.revoked_grants} acesso(s) revogado(s) ·
                            quarentena{" "}
                            {incident.quarantined ? "ativa" : "encerrada"}
                            {` · severidade ${incident.severity} · votos ${incident.review_count}/${incident.required_review_quorum}`}
                            {` · prazo ${new Date(incident.review_due_at).toLocaleString("pt-BR")}`}
                            {incident.sla_breached ? " · SLA vencido" : ""}
                            {incident.escalation_count
                              ? ` · escalonado ${incident.escalation_count} vez(es)`
                              : ""}
                          </small>
                          <small>
                            Responsáveis:{" "}
                            {incident.responsible_user_ids.length
                              ? incident.responsible_user_ids
                                  .map(
                                    (userId) =>
                                      companyUsers.data?.find(
                                        (user) => user.user_id === userId,
                                      )?.name ?? userId.slice(0, 8),
                                  )
                                  .join(", ")
                              : "fila autorizada legada"}
                          </small>
                        </div>
                        {incident.review_status === "pending" ? (
                          <div className="agent-policy-row__actions">
                            <Button
                              loading={reviewMemoryIncident.isPending}
                              onClick={() =>
                                reviewMemoryIncident.mutate({
                                  incidentId: incident.id,
                                  decision: "confirmed",
                                })
                              }
                              variant="secondary"
                            >
                              Confirmar
                            </Button>
                            <Button
                              loading={reviewMemoryIncident.isPending}
                              onClick={() =>
                                reviewMemoryIncident.mutate({
                                  incidentId: incident.id,
                                  decision: "dismissed",
                                })
                              }
                              variant="ghost"
                            >
                              Descartar
                            </Button>
                            <Button
                              loading={reassignMemoryIncident.isPending}
                              onClick={() => {
                                if (
                                  !memoryIncidentResponsibleUserIds.length ||
                                  memoryIncidentReassignmentReason.trim()
                                    .length < 3
                                ) {
                                  setMemoryIncidentFeedback(
                                    "Selecione responsáveis e informe uma justificativa.",
                                  );
                                  return;
                                }
                                reassignMemoryIncident.mutate(incident.id);
                              }}
                              variant="ghost"
                            >
                              Reatribuir
                            </Button>
                          </div>
                        ) : null}
                      </article>
                    ))
                  ) : (
                    <p>Nenhum incidente de memória registrado.</p>
                  )}
                </div>
                <form
                  className="agent-policy-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    saveMemoryExerciseSchedule.mutate();
                  }}
                >
                  <label className="native-field">
                    <span>Agenda recorrente de exercícios</span>
                    <input
                      checked={memoryExerciseScheduleEnabled}
                      onChange={(event) =>
                        setMemoryExerciseScheduleEnabled(event.target.checked)
                      }
                      type="checkbox"
                    />
                  </label>
                  <TextField
                    label="Intervalo entre exercícios (horas)"
                    max={720}
                    min={1}
                    onChange={(event) =>
                      setMemoryExerciseCadenceHours(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryExerciseCadenceHours}
                  />
                  <TextField
                    label="SLO do heartbeat (minutos)"
                    max={1440}
                    min={5}
                    onChange={(event) =>
                      setMemoryExerciseHeartbeatSloMinutes(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryExerciseHeartbeatSloMinutes}
                  />
                  <div className="form-actions">
                    <Button
                      loading={saveMemoryExerciseSchedule.isPending}
                      type="submit"
                      variant="secondary"
                    >
                      Salvar agenda
                    </Button>
                    <Button
                      loading={runDueMemoryExercise.isPending}
                      onClick={() => runDueMemoryExercise.mutate()}
                      type="button"
                      variant="ghost"
                    >
                      Executar se estiver no prazo
                    </Button>
                  </div>
                  <small>
                    Próxima execução:{" "}
                    {memoryExerciseSchedule.data?.next_run_at
                      ? new Date(
                          memoryExerciseSchedule.data.next_run_at,
                        ).toLocaleString("pt-BR")
                      : "não agendada"}
                  </small>
                  <small>
                    Worker: {memorySchedulerMetrics.data?.worker_passed ?? 0}
                    aprovado(s),{" "}
                    {memorySchedulerMetrics.data?.worker_failed ?? 0}
                    falho(s) · média{" "}
                    {Math.round(
                      memorySchedulerMetrics.data?.average_duration_ms ?? 0,
                    )}
                    ms
                    {(memorySchedulerMetrics.data?.overdue_seconds ?? 0) > 0
                      ? ` · atraso ${memorySchedulerMetrics.data?.overdue_seconds}s`
                      : " · sem atraso"}
                  </small>
                  <small>
                    Heartbeat:{" "}
                    {memorySchedulerMetrics.data?.heartbeat_status === "healthy"
                      ? "saudável"
                      : memorySchedulerMetrics.data?.heartbeat_status ===
                          "overdue"
                        ? "SLO vencido"
                        : memorySchedulerMetrics.data?.heartbeat_status ===
                            "waiting"
                          ? "aguardando primeira leitura"
                          : "desativado"}
                    {` · violações ${memorySchedulerMetrics.data?.slo_breach_count ?? 0}`}
                  </small>
                </form>
                <div className="agent-policy-list">
                  <strong>Exercícios recentes</strong>
                  {memoryExercises.data?.length ? (
                    memoryExercises.data.slice(0, 3).map((exercise) => (
                      <article className="agent-policy-row" key={exercise.id}>
                        <div>
                          <strong>
                            {exercise.status === "passed"
                              ? "Controles aprovados"
                              : "Revisão necessária"}
                          </strong>
                          <small>
                            {
                              Object.values(exercise.checks).filter(Boolean)
                                .length
                            }
                            /{Object.keys(exercise.checks).length} verificações
                            {` · ${exercise.duration_ms}ms · ${
                              exercise.source === "worker_schedule"
                                ? "worker"
                                : exercise.source === "manual_schedule"
                                  ? "agenda manual"
                                  : "manual"
                            } · `}
                            {new Date(exercise.created_at).toLocaleString(
                              "pt-BR",
                            )}
                          </small>
                        </div>
                      </article>
                    ))
                  ) : (
                    <p>Nenhum exercício executado.</p>
                  )}
                </div>
                <div className="agent-policy-list">
                  <strong>Proteção do keyring</strong>
                  <article className="agent-policy-row">
                    <div>
                      <strong>Política operacional da empresa</strong>
                      <small>
                        {memoryKeyringPolicy.data?.configured
                          ? "Configuração própria ativa"
                          : "Usando padrões seguros do ambiente"}
                      </small>
                    </div>
                    <span className="status-badge">
                      SLO {memoryKeyringPolicy.data?.vault_slo_minutes ?? 30}{" "}
                      min
                    </span>
                  </article>
                  <div className="agent-policy-form">
                    <TextField
                      label="Avisar antes do vencimento (dias)"
                      min={1}
                      max={90}
                      onChange={(event) =>
                        setKeyringExpiryWarningDays(event.target.value)
                      }
                      type="number"
                      value={keyringExpiryWarningDays}
                    />
                    <TextField
                      label="Lote da saída automática"
                      min={1}
                      max={500}
                      onChange={(event) =>
                        setKeyringAutomaticExitBatchSize(event.target.value)
                      }
                      type="number"
                      value={keyringAutomaticExitBatchSize}
                    />
                    <TextField
                      label="Falhas antes do alerta"
                      min={1}
                      max={20}
                      onChange={(event) =>
                        setKeyringFailureAlertThreshold(event.target.value)
                      }
                      type="number"
                      value={keyringFailureAlertThreshold}
                    />
                    <TextField
                      label="SLO de indisponibilidade (minutos)"
                      min={1}
                      max={1440}
                      onChange={(event) =>
                        setKeyringSloMinutes(event.target.value)
                      }
                      type="number"
                      value={keyringSloMinutes}
                    />
                    <TextField
                      label="Retenção da disponibilidade (dias)"
                      min={7}
                      max={365}
                      onChange={(event) =>
                        setKeyringAvailabilityRetentionDays(event.target.value)
                      }
                      type="number"
                      value={keyringAvailabilityRetentionDays}
                    />
                    <TextField
                      label="Fuso do plantão"
                      onChange={(event) =>
                        setKeyringOnCallTimezone(event.target.value)
                      }
                      placeholder="America/Sao_Paulo"
                      value={keyringOnCallTimezone}
                    />
                    <TextField
                      label="Início do plantão (hora)"
                      min={0}
                      max={23}
                      onChange={(event) =>
                        setKeyringOnCallStartHour(event.target.value)
                      }
                      type="number"
                      value={keyringOnCallStartHour}
                    />
                    <TextField
                      label="Fim do plantão (hora)"
                      min={1}
                      max={24}
                      onChange={(event) =>
                        setKeyringOnCallEndHour(event.target.value)
                      }
                      type="number"
                      value={keyringOnCallEndHour}
                    />
                    <TextField
                      label="Antecedência do canário (dias)"
                      min={1}
                      max={90}
                      onChange={(event) =>
                        setKeyringIdentityCanaryDays(event.target.value)
                      }
                      type="number"
                      value={keyringIdentityCanaryDays}
                    />
                    <TextField
                      label="Intervalo do canário (horas)"
                      min={1}
                      max={168}
                      onChange={(event) =>
                        setKeyringIdentityCanaryIntervalHours(
                          event.target.value,
                        )
                      }
                      type="number"
                      value={keyringIdentityCanaryIntervalHours}
                    />
                    <label className="agent-checkbox-card">
                      <input
                        checked={keyringAutomaticExitEnabled}
                        onChange={(event) =>
                          setKeyringAutomaticExitEnabled(event.target.checked)
                        }
                        type="checkbox"
                      />
                      <span>
                        <strong>Saída automática protegida</strong>
                        <small>
                          Recriptografa antes de revogar credenciais próximas do
                          vencimento.
                        </small>
                      </span>
                    </label>
                    <div className="agent-policy-list">
                      <strong>Equipe de plantão</strong>
                      {companyUsers.data?.map((user) => (
                        <label
                          className="agent-checkbox-card"
                          key={user.user_id}
                        >
                          <input
                            checked={keyringOnCallUserIds.includes(
                              user.user_id,
                            )}
                            onChange={(event) =>
                              setKeyringOnCallUserIds((current) =>
                                event.target.checked
                                  ? [...current, user.user_id]
                                  : current.filter((id) => id !== user.user_id),
                              )
                            }
                            type="checkbox"
                          />
                          <span>
                            <strong>{user.name}</strong>
                            <small>{user.email}</small>
                          </span>
                        </label>
                      ))}
                    </div>
                    <Button
                      loading={updateMemoryKeyringPolicy.isPending}
                      onClick={() => updateMemoryKeyringPolicy.mutate()}
                      type="button"
                      variant="secondary"
                    >
                      Salvar política do cofre
                    </Button>
                  </div>
                  <article className="agent-policy-row">
                    <div>
                      <strong>
                        {memoryKeyringStatus.data?.source === "managed"
                          ? "Cofre gerenciado ativo"
                          : "Chave do ambiente ativa"}
                      </strong>
                      <small>
                        Provedor:{" "}
                        {memoryKeyringStatus.data?.provider_code ??
                          "carregando"}
                        {memoryKeyringStatus.data?.last_resolved_at
                          ? ` · última resolução ${new Date(memoryKeyringStatus.data.last_resolved_at).toLocaleString("pt-BR")}`
                          : ""}
                        {memoryKeyringStatus.data?.credential_expires_at
                          ? ` · credencial vence ${new Date(memoryKeyringStatus.data.credential_expires_at).toLocaleDateString("pt-BR")}`
                          : " · sem vencimento configurado"}
                        {memoryKeyringStatus.data?.last_identity_canary_at
                          ? ` · último canário ${new Date(memoryKeyringStatus.data.last_identity_canary_at).toLocaleString("pt-BR")}`
                          : " · canário ainda não executado"}
                      </small>
                    </div>
                    <span className="status-badge">
                      {memoryKeyringStatus.data?.health_status ?? "verificando"}{" "}
                      · SLO{" "}
                      {memoryKeyringStatus.data?.slo_status ?? "verificando"}
                      {" · canário "}
                      {memoryKeyringStatus.data?.identity_canary_status ??
                        "verificando"}
                    </span>
                  </article>
                  {memoryKeyringStatus.data?.source === "managed" ? (
                    <>
                      <div className="agent-policy-form">
                        <TextField
                          label="Prorrogar validade (dias)"
                          min={1}
                          max={365}
                          onChange={(event) =>
                            setCredentialRenewalDays(event.target.value)
                          }
                          type="number"
                          value={credentialRenewalDays}
                        />
                        <TextField
                          label="Justificativa protegida"
                          onChange={(event) =>
                            setCredentialRenewalReason(event.target.value)
                          }
                          value={credentialRenewalReason}
                        />
                        <Button
                          disabled={credentialRenewalReason.trim().length < 4}
                          loading={requestCredentialRenewal.isPending}
                          onClick={() => requestCredentialRenewal.mutate()}
                          type="button"
                          variant="secondary"
                        >
                          Solicitar renovação
                        </Button>
                      </div>
                      {credentialRenewals.data?.map((renewal) => (
                        <article className="agent-policy-row" key={renewal.id}>
                          <div>
                            <strong>Renovação {renewal.status}</strong>
                            <small>
                              +{renewal.extension_days} dias · validade proposta{" "}
                              {new Date(
                                renewal.proposed_expires_at,
                              ).toLocaleDateString("pt-BR")}
                            </small>
                          </div>
                          {renewal.status === "pending" ? (
                            <div className="button-row">
                              <Button
                                loading={decideCredentialRenewal.isPending}
                                onClick={() =>
                                  decideCredentialRenewal.mutate({
                                    renewalId: renewal.id,
                                    decision: "approved",
                                  })
                                }
                                type="button"
                                variant="secondary"
                              >
                                Aprovar
                              </Button>
                              <Button
                                loading={decideCredentialRenewal.isPending}
                                onClick={() =>
                                  decideCredentialRenewal.mutate({
                                    renewalId: renewal.id,
                                    decision: "rejected",
                                  })
                                }
                                type="button"
                                variant="secondary"
                              >
                                Rejeitar
                              </Button>
                            </div>
                          ) : (
                            <span className="status-badge">
                              {renewal.status}
                            </span>
                          )}
                        </article>
                      ))}
                      <div className="agent-policy-form">
                        <TextField
                          label="Nova identidade da carga"
                          onChange={(event) =>
                            setWorkloadIdentityReference(event.target.value)
                          }
                          placeholder="conta-servico@projeto.iam.gserviceaccount.com"
                          value={workloadIdentityReference}
                        />
                        <TextField
                          label="Motivo da rotação"
                          onChange={(event) =>
                            setWorkloadIdentityRotationReason(
                              event.target.value,
                            )
                          }
                          value={workloadIdentityRotationReason}
                        />
                        <Button
                          disabled={
                            workloadIdentityReference.trim().length < 4 ||
                            workloadIdentityRotationReason.trim().length < 4
                          }
                          loading={requestWorkloadIdentityRotation.isPending}
                          onClick={() =>
                            requestWorkloadIdentityRotation.mutate()
                          }
                          type="button"
                          variant="secondary"
                        >
                          Solicitar rotação da identidade
                        </Button>
                      </div>
                      {workloadIdentityRotations.data?.map((rotation) => (
                        <article className="agent-policy-row" key={rotation.id}>
                          <div>
                            <strong>Identidade {rotation.status}</strong>
                            <small>
                              {rotation.provider_code} ·{" "}
                              {rotation.verified
                                ? "acesso ao cofre verificado"
                                : "aguardando validação"}
                            </small>
                          </div>
                          {rotation.status === "pending" ? (
                            <div className="button-row">
                              <Button
                                loading={
                                  decideWorkloadIdentityRotation.isPending
                                }
                                onClick={() =>
                                  decideWorkloadIdentityRotation.mutate({
                                    rotationId: rotation.id,
                                    decision: "approved",
                                  })
                                }
                                type="button"
                                variant="secondary"
                              >
                                Validar e aprovar
                              </Button>
                              <Button
                                loading={
                                  decideWorkloadIdentityRotation.isPending
                                }
                                onClick={() =>
                                  decideWorkloadIdentityRotation.mutate({
                                    rotationId: rotation.id,
                                    decision: "rejected",
                                  })
                                }
                                type="button"
                                variant="secondary"
                              >
                                Rejeitar
                              </Button>
                            </div>
                          ) : (
                            <span className="status-badge">
                              {rotation.status}
                            </span>
                          )}
                        </article>
                      ))}
                      <Button
                        disabled={Boolean(
                          memoryKeyringStatus.data.automatic_exit_status &&
                          ["pending", "running"].includes(
                            memoryKeyringStatus.data.automatic_exit_status,
                          ),
                        )}
                        loading={exitManagedMemoryKeyring.isPending}
                        onClick={() => exitManagedMemoryKeyring.mutate()}
                        type="button"
                        variant="secondary"
                      >
                        <TimerReset size={16} /> Retornar à chave do ambiente
                      </Button>
                    </>
                  ) : null}
                  {memoryVaultIncidents.data?.map((incident) => (
                    <article className="agent-policy-row" key={incident.id}>
                      <div>
                        <strong>
                          {incident.status === "open"
                            ? "Cofre indisponível"
                            : "Incidente resolvido"}
                        </strong>
                        <small>
                          {incident.provider_code} · {incident.failure_count}{" "}
                          falha(s) · última detecção{" "}
                          {new Date(incident.last_detected_at).toLocaleString(
                            "pt-BR",
                          )}
                          {incident.slo_breached ? " · SLO violado" : ""}
                        </small>
                      </div>
                      <span className="status-badge">{incident.status}</span>
                    </article>
                  ))}
                  {memoryVaultAvailability.data?.slice(0, 12).map((window) => (
                    <article
                      className="agent-policy-row"
                      key={`${window.provider_code}-${window.window_started_at}`}
                    >
                      <div>
                        <strong>
                          Disponibilidade {window.availability_percent}%
                        </strong>
                        <small>
                          {window.provider_code} · {window.successful_checks}/
                          {window.total_checks} verificações ·{" "}
                          {window.slo_breaches} violação(ões) de SLO ·{" "}
                          {new Date(window.window_started_at).toLocaleString(
                            "pt-BR",
                          )}
                        </small>
                      </div>
                    </article>
                  ))}
                  {managedVaultMetrics.data?.map((metric) => (
                    <article
                      className="agent-policy-row"
                      key={metric.provider_code}
                    >
                      <div>
                        <strong>{metric.provider_name}</strong>
                        <small>
                          {Math.round(metric.success_rate * 100)}% de sucesso ·{" "}
                          {metric.total_tests} teste(s) ·{" "}
                          {metric.average_duration_ms} ms
                        </small>
                      </div>
                      <span className="status-badge">
                        {metric.failed_tests === 0
                          ? "saudável"
                          : `${metric.failed_tests} falha(s)`}
                      </span>
                    </article>
                  ))}
                  {canManagePlugins &&
                  managedVaultMetrics.data?.length === 0 ? (
                    <small>
                      Nenhum teste de cofre registrado nesta empresa.
                    </small>
                  ) : null}
                </div>
                <form
                  className="agent-policy-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    startMemoryReencryption.mutate();
                  }}
                >
                  <strong>Rotação protegida das memórias</strong>
                  <p>
                    Depois de configurar a chave ativa e manter a anterior no
                    keyring, mova os dados em lotes antes de remover a chave
                    antiga.
                  </p>
                  <TextField
                    label="Memórias por lote"
                    max={500}
                    min={1}
                    onChange={(event) =>
                      setMemoryReencryptionBatchSize(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryReencryptionBatchSize}
                  />
                  <TextField
                    label="Máximo de retomadas"
                    max={10}
                    min={1}
                    onChange={(event) =>
                      setMemoryReencryptionMaxRetries(event.target.value)
                    }
                    required
                    type="number"
                    value={memoryReencryptionMaxRetries}
                  />
                  <label className="native-field">
                    <span>Credencial do cofre externo</span>
                    <select
                      className="agent-native-select"
                      onChange={(event) =>
                        setMemoryVaultCredentialId(event.target.value)
                      }
                      value={memoryVaultCredentialId}
                    >
                      <option value="">Nenhuma (ambiente local)</option>
                      {memoryVaultCredentials.data?.map((credential) => (
                        <option key={credential.id} value={credential.id}>
                          {credential.name} · {credential.provider_name}
                          {credential.managed_provider
                            ? " · gerenciado"
                            : " · personalizado"}
                        </option>
                      ))}
                    </select>
                    <small>
                      Somente credenciais ativas desta empresa com o campo
                      key_reference são exibidas.
                    </small>
                  </label>
                  <Button
                    loading={startMemoryReencryption.isPending}
                    type="submit"
                    variant="secondary"
                  >
                    <LockKeyhole size={16} /> Iniciar recriptografia
                  </Button>
                  {latestMemoryReencryptionJob ? (
                    <small>
                      Último job: {latestMemoryReencryptionJob.status} ·{" "}
                      {latestMemoryReencryptionJob.rotated_count}/
                      {latestMemoryReencryptionJob.total_count} protegida(s)
                      {latestMemoryReencryptionJob.error_code
                        ? ` · erro ${latestMemoryReencryptionJob.error_code}`
                        : ""}
                      {` · chaves ${latestMemoryReencryptionJob.key_provider}`}
                      {latestMemoryReencryptionJob.vault_credential_bound
                        ? " · credencial vinculada"
                        : " · sem credencial externa"}
                      {` · retomadas ${latestMemoryReencryptionJob.retry_count}/${latestMemoryReencryptionJob.max_retry_attempts}`}
                      {latestMemoryReencryptionJob.purge_after
                        ? ` · retenção até ${new Date(latestMemoryReencryptionJob.purge_after).toLocaleDateString("pt-BR")}`
                        : ""}
                    </small>
                  ) : (
                    <small>Nenhuma recriptografia solicitada.</small>
                  )}
                  {latestMemoryReencryptionJob &&
                  ["completed", "failed", "closed"].includes(
                    latestMemoryReencryptionJob.status,
                  ) ? (
                    <div className="agent-policy-list">
                      <strong>Retenção legal do job</strong>
                      <small>
                        Suspende o expurgo durante investigação, processo ou
                        auditoria. Outra pessoa autorizada deve decidir.
                      </small>
                      <label className="native-field">
                        <span>Motivo da retenção</span>
                        <select
                          className="agent-native-select"
                          onChange={(event) =>
                            setMemoryJobLegalHoldReason(
                              event.target.value as
                                | "legal_claim"
                                | "regulatory_request"
                                | "audit_preservation",
                            )
                          }
                          value={memoryJobLegalHoldReason}
                        >
                          <option value="audit_preservation">
                            Preservação para auditoria
                          </option>
                          <option value="legal_claim">Processo legal</option>
                          <option value="regulatory_request">
                            Solicitação regulatória
                          </option>
                        </select>
                      </label>
                      <TextField
                        label="Referência jurídica sigilosa"
                        maxLength={160}
                        onChange={(event) =>
                          setMemoryJobLegalReference(event.target.value)
                        }
                        value={memoryJobLegalReference}
                      />
                      <TextField
                        label="Dias de retenção"
                        max={3650}
                        min={1}
                        onChange={(event) =>
                          setMemoryJobLegalRetentionDays(event.target.value)
                        }
                        type="number"
                        value={memoryJobLegalRetentionDays}
                      />
                      <Button
                        disabled={memoryJobLegalReference.trim().length < 8}
                        loading={requestMemoryReencryptionLegalHold.isPending}
                        onClick={() =>
                          requestMemoryReencryptionLegalHold.mutate()
                        }
                        type="button"
                        variant="secondary"
                      >
                        Solicitar retenção legal
                      </Button>
                      {memoryReencryptionLegalHolds.data?.map((hold) => (
                        <article className="agent-policy-row" key={hold.id}>
                          <div>
                            <strong>
                              {hold.reason_code} · {hold.status}
                            </strong>
                            <small>
                              Até{" "}
                              {new Date(hold.expires_at).toLocaleDateString(
                                "pt-BR",
                              )}
                            </small>
                          </div>
                          {hold.status === "pending" ? (
                            <div className="button-row">
                              <Button
                                loading={
                                  decideMemoryReencryptionLegalHold.isPending
                                }
                                onClick={() =>
                                  decideMemoryReencryptionLegalHold.mutate({
                                    holdId: hold.id,
                                    decision: "approved",
                                  })
                                }
                                type="button"
                                variant="secondary"
                              >
                                Aprovar
                              </Button>
                              <Button
                                loading={
                                  decideMemoryReencryptionLegalHold.isPending
                                }
                                onClick={() =>
                                  decideMemoryReencryptionLegalHold.mutate({
                                    holdId: hold.id,
                                    decision: "rejected",
                                  })
                                }
                                type="button"
                                variant="ghost"
                              >
                                Rejeitar
                              </Button>
                            </div>
                          ) : null}
                        </article>
                      ))}
                      {renewableMemoryLegalHold ? (
                        <div className="agent-policy-list">
                          <strong>Renovar retenção aprovada</strong>
                          <small>
                            A extensão exige uma nova referência e decisão de
                            outra pessoa autorizada.
                          </small>
                          <TextField
                            label="Dias adicionais"
                            max={3650}
                            min={1}
                            onChange={(event) =>
                              setMemoryJobLegalRenewalDays(event.target.value)
                            }
                            type="number"
                            value={memoryJobLegalRenewalDays}
                          />
                          <TextField
                            label="Nova referência jurídica sigilosa"
                            maxLength={240}
                            onChange={(event) =>
                              setMemoryJobLegalRenewalReference(
                                event.target.value,
                              )
                            }
                            value={memoryJobLegalRenewalReference}
                          />
                          <Button
                            disabled={
                              memoryJobLegalRenewalReference.trim().length < 4
                            }
                            loading={
                              requestMemoryReencryptionLegalHoldRenewal.isPending
                            }
                            onClick={() =>
                              requestMemoryReencryptionLegalHoldRenewal.mutate()
                            }
                            type="button"
                            variant="secondary"
                          >
                            Solicitar renovação
                          </Button>
                          {memoryReencryptionLegalHoldRenewals.data?.map(
                            (renewal) => (
                              <article
                                className="agent-policy-row"
                                key={renewal.id}
                              >
                                <div>
                                  <strong>
                                    +{renewal.extension_days} dias ·{" "}
                                    {renewal.status}
                                  </strong>
                                  <small>
                                    Prazo proposto{" "}
                                    {new Date(
                                      renewal.proposed_expires_at,
                                    ).toLocaleDateString("pt-BR")}
                                  </small>
                                </div>
                                {renewal.status === "pending" ? (
                                  <div className="button-row">
                                    <Button
                                      loading={
                                        decideMemoryReencryptionLegalHoldRenewal.isPending
                                      }
                                      onClick={() =>
                                        decideMemoryReencryptionLegalHoldRenewal.mutate(
                                          {
                                            renewalId: renewal.id,
                                            decision: "approved",
                                          },
                                        )
                                      }
                                      type="button"
                                      variant="secondary"
                                    >
                                      Aprovar extensão
                                    </Button>
                                    <Button
                                      loading={
                                        decideMemoryReencryptionLegalHoldRenewal.isPending
                                      }
                                      onClick={() =>
                                        decideMemoryReencryptionLegalHoldRenewal.mutate(
                                          {
                                            renewalId: renewal.id,
                                            decision: "rejected",
                                          },
                                        )
                                      }
                                      type="button"
                                      variant="ghost"
                                    >
                                      Rejeitar extensão
                                    </Button>
                                  </div>
                                ) : null}
                              </article>
                            ),
                          )}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {latestMemoryReencryptionJob?.status === "failed" ? (
                    <>
                      <Button
                        loading={assessMemoryReencryptionRecovery.isPending}
                        onClick={() =>
                          assessMemoryReencryptionRecovery.mutate(
                            latestMemoryReencryptionJob.id,
                          )
                        }
                        type="button"
                        variant="secondary"
                      >
                        <ShieldAlert size={16} /> Verificar recuperação
                      </Button>
                      {memoryRecoveryAssessment ? (
                        <div className="agent-policy-list">
                          <strong>
                            Diagnóstico: {memoryRecoveryAssessment.status}
                          </strong>
                          {memoryRecoveryAssessment.instructions.map(
                            (instruction) => (
                              <small key={instruction}>{instruction}</small>
                            ),
                          )}
                        </div>
                      ) : null}
                      <TextField
                        label="Justificativa para retomar"
                        maxLength={160}
                        onChange={(event) =>
                          setMemoryReencryptionRetryReason(event.target.value)
                        }
                        value={memoryReencryptionRetryReason}
                      />
                      <Button
                        disabled={
                          memoryRecoveryAssessment?.status !== "ready" ||
                          latestMemoryReencryptionJob.retry_attempts_remaining <=
                            0
                        }
                        loading={retryMemoryReencryption.isPending}
                        onClick={() => {
                          if (memoryReencryptionRetryReason.trim().length < 3) {
                            setMemoryIncidentFeedback(
                              "Informe a justificativa antes de retomar o job.",
                            );
                            return;
                          }
                          retryMemoryReencryption.mutate(
                            latestMemoryReencryptionJob.id,
                          );
                        }}
                        type="button"
                        variant="ghost"
                      >
                        Retomar do checkpoint
                      </Button>
                      {memoryRecoveryAssessment?.status === "blocked" ||
                      latestMemoryReencryptionJob.retry_attempts_remaining ===
                        0 ? (
                        <div className="agent-policy-list">
                          <strong>Encerramento definitivo</strong>
                          <small>
                            Use somente quando a chave não puder ser recuperada
                            ou o orçamento de retomadas tiver acabado.
                          </small>
                          <label className="native-field">
                            <span>Motivo técnico</span>
                            <select
                              className="agent-native-select"
                              onChange={(event) =>
                                setMemoryReencryptionClosureCode(
                                  event.target.value as
                                    | "missing_key"
                                    | "corrupted_material"
                                    | "budget_exhausted"
                                    | "other",
                                )
                              }
                              value={memoryReencryptionClosureCode}
                            >
                              <option value="budget_exhausted">
                                Limite de retomadas esgotado
                              </option>
                              <option value="missing_key">
                                Chave histórica indisponível
                              </option>
                              <option value="corrupted_material">
                                Material criptográfico corrompido
                              </option>
                              <option value="other">Outro motivo</option>
                            </select>
                          </label>
                          <TextField
                            label="Justificativa para encerrar"
                            maxLength={160}
                            onChange={(event) =>
                              setMemoryReencryptionClosureReason(
                                event.target.value,
                              )
                            }
                            value={memoryReencryptionClosureReason}
                          />
                          <Button
                            disabled={
                              memoryReencryptionClosureReason.trim().length < 3
                            }
                            loading={closeMemoryReencryption.isPending}
                            onClick={() =>
                              closeMemoryReencryption.mutate(
                                latestMemoryReencryptionJob.id,
                              )
                            }
                            type="button"
                            variant="secondary"
                          >
                            Encerrar job com auditoria
                          </Button>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </form>
              </Card>
            </PermissionGuard>
            <PermissionGuard all={["agents.execute"]}>
              <Card
                eyebrow="Direitos do titular"
                title="Minhas memórias pessoais"
              >
                <p>
                  Revise e elimine metadados vinculados a você. O conteúdo
                  criptografado nunca é exibido nem incluído na exportação.
                </p>
                {memoryFeedback ? <Alert>{memoryFeedback}</Alert> : null}
                <Button
                  loading={exportMyMemories.isPending}
                  onClick={() => exportMyMemories.mutate()}
                  type="button"
                  variant="secondary"
                >
                  Exportar metadados
                </Button>
                <div className="agent-policy-list">
                  {myMemories.data?.length ? (
                    myMemories.data.map((memory) => (
                      <article className="agent-policy-row" key={memory.id}>
                        <div>
                          <strong>
                            {memory.purpose} · {memory.classification}
                          </strong>
                          <small>
                            Expira em{" "}
                            {new Date(memory.expires_at).toLocaleString(
                              "pt-BR",
                            )}
                          </small>
                        </div>
                        <Button
                          loading={
                            deleteMyMemory.isPending &&
                            deleteMyMemory.variables === memory.id
                          }
                          onClick={() => deleteMyMemory.mutate(memory.id)}
                          variant="ghost"
                        >
                          <Trash2 size={16} /> Eliminar minha memória
                        </Button>
                      </article>
                    ))
                  ) : (
                    <p>Nenhuma memória pessoal ativa vinculada a você.</p>
                  )}
                </div>
              </Card>
            </PermissionGuard>
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
                {conversationFeedback ? (
                  <Alert>{conversationFeedback}</Alert>
                ) : null}
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
                  {conversationId ? (
                    <Button
                      loading={closeConversation.isPending}
                      onClick={() => closeConversation.mutate()}
                      type="button"
                      variant="secondary"
                    >
                      <X size={17} /> Encerrar conversa
                    </Button>
                  ) : null}
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

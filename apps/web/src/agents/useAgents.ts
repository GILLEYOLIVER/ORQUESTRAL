import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export interface AgentResponse {
  id: string;
  name: string;
  description: string | null;
  instructions: string;
  provider: "local" | "openai_compatible";
  model: string;
  temperature: number;
  max_input_tokens: number;
  max_output_tokens: number;
  memory_enabled: boolean;
  knowledge_base_id: string | null;
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
}

export interface AgentToolCatalog {
  key: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  required_permission: string;
  is_sensitive: boolean;
}

export interface AgentToolResponse {
  id: string;
  tool_key: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  required_permission: string | null;
  is_sensitive: boolean;
  enabled: boolean;
}

export interface AgentMessageResponse {
  id: string;
  conversation_id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_call: Record<string, unknown>;
  provider: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_microunits: number;
  duration_ms: number | null;
  created_at: string;
}

export interface AgentToolRunResponse {
  id: string;
  agent_id: string;
  conversation_id: string | null;
  tool_key: string;
  tool_name: string;
  state: string;
  requires_confirmation: boolean;
  result_summary: Record<string, unknown>;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentChatResponse {
  conversation: {
    id: string;
    agent_id: string;
    title: string;
    status: string;
    closed_at: string | null;
    created_at: string;
    updated_at: string;
  };
  user_message: AgentMessageResponse;
  assistant_message: AgentMessageResponse;
  pending_actions: AgentToolRunResponse[];
}

export interface AgentConversationCloseResponse {
  conversation: AgentChatResponse["conversation"];
  deleted_memories: number;
}

export interface AgentUsageResponse {
  id: string;
  agent_id: string;
  conversation_id: string | null;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_microunits: number;
  tool_key: string | null;
  duration_ms: number;
  result_status: string;
  created_at: string;
}

export interface AgentApprovalPolicyResponse {
  id: string;
  agent_id: string;
  policy_key: string;
  version: number;
  name: string;
  status: "draft" | "published" | "retired";
  effect: "allow" | "require_approval" | "deny";
  priority: number;
  tool_key: string | null;
  amount_field: string | null;
  min_amount_microunits: number | null;
  max_amount_microunits: number | null;
  currency: string | null;
  context_conditions: Record<string, string | number | boolean | null>;
  approval_ttl_minutes: number;
  effective_from: string | null;
  effective_until: string | null;
  assigned_user_id: string | null;
  escalation_user_id: string | null;
  escalation_after_minutes: number | null;
  approval_stages: Array<{
    id: string;
    stage_order: number;
    name: string;
    quorum: number;
    approver_user_ids: string[];
  }>;
  created_at: string;
  published_at: string | null;
}

export interface AgentApprovalPolicyEvaluationResponse {
  allowed: boolean;
  requires_approval: boolean;
  policy_version_id: string | null;
  policy_key: string | null;
  reason: string;
  approval_ttl_minutes: number;
  assigned_user_id: string | null;
  escalation_user_id: string | null;
  escalation_after_minutes: number | null;
}

export interface AgentMemoryPolicyResponse {
  id: string | null;
  agent_id: string;
  default_retention_days: number;
  max_retention_days: number;
  allowed_scopes: Array<
    "conversation" | "task" | "user" | "company" | "operational"
  >;
  allowed_classifications: Array<
    "public" | "internal" | "confidential" | "restricted"
  >;
  require_consent_for_user_scope: boolean;
  retrieval_enabled: boolean;
  max_retrieval_entries: number;
  max_context_tokens: number;
  max_shared_context_entries: number;
  max_shared_context_characters: number;
  blocked_context_alert_threshold: number;
  scope_policies: Array<{
    scope: "conversation" | "task" | "user" | "company" | "operational";
    retention_days: number;
    retrieval_enabled: boolean;
  }>;
  purpose_policies: Array<{
    purpose:
      "service" | "personalization" | "operations" | "compliance" | "analytics";
    retention_days: number;
    enabled: boolean;
  }>;
  updated_at: string | null;
}

export interface AgentMemoryResponse {
  id: string;
  agent_id: string;
  scope: "conversation" | "task" | "user" | "company" | "operational";
  classification: "public" | "internal" | "confidential" | "restricted";
  source_type: "manual" | "conversation" | "task" | "tool";
  source_id: string | null;
  task_delegation_id: string | null;
  purpose:
    "service" | "personalization" | "operations" | "compliance" | "analytics";
  subject_user_id: string | null;
  consent_recorded: boolean;
  expires_at: string;
  expired: boolean;
  created_at: string;
}

export interface AgentMemoryConsentRevocationResponse {
  revocation_id: string;
  deleted_count: number;
  already_revoked: boolean;
}

export interface AgentMemoryMetadataExport {
  agent_id: string;
  generated_at: string;
  total: number;
  memories: AgentMemoryResponse[];
}

export interface AgentMemoryRiskSummary {
  agent_id: string;
  generated_at: string;
  risk_level: "low" | "elevated" | "high" | "critical";
  active_grants: number;
  restricted_active_grants: number;
  pending_approvals: number;
  expired_approvals: number;
  blocked_events_last_24h: number;
  cost_denials_last_24h: number;
  incidents_last_30_days: number;
  revoked_grants_last_30_days: number;
  pending_incident_reviews: number;
  quarantined: boolean;
  quarantine_until: string | null;
}

export interface AgentTaskMemoryIncidentResponse {
  id: string;
  agent_id: string;
  revoked_grants: number;
  quarantine_minutes: number;
  quarantine_until: string;
  quarantined: boolean;
  review_status: "pending" | "confirmed" | "dismissed";
  triggered_by_user_id: string;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  already_processed: boolean;
  created_at: string;
}

export interface AgentMemoryRiskReport {
  payload: {
    report_id: string;
    agent_id: string;
    generated_at: string;
    risk_summary: AgentMemoryRiskSummary;
    pending_incident_ids: string[];
  };
  signature_algorithm: "HMAC-SHA256";
  signature_key_id: "orkestral-memory-risk-v1";
  signature: string;
}

export function useAgents(enabled = true) {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["agents", me?.current_company?.id],
    queryFn: () => request<AgentResponse[]>("/agents"),
    enabled:
      enabled &&
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("agents.view") ?? false),
  });
}

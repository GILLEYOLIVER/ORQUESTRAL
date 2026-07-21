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
  overdue_incident_reviews: number;
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
  severity: "low" | "medium" | "high" | "critical";
  required_review_quorum: number;
  review_count: number;
  review_sla_minutes: number;
  review_due_at: string;
  sla_breached: boolean;
  escalation_count: number;
  escalated_at: string | null;
  triggered_by_user_id: string;
  responsible_user_ids: string[];
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
    sequence: number;
    previous_signature: string | null;
    signature_key_version: number;
    risk_summary: AgentMemoryRiskSummary;
    pending_incident_ids: string[];
  };
  signature_algorithm: "HMAC-SHA256";
  signature_key_id: "orkestral-memory-risk-v1";
  signature: string;
}

export interface AgentMemoryResponseExercise {
  id: string;
  agent_id: string;
  scenario: "full";
  status: "passed" | "failed";
  checks: Record<string, boolean>;
  source: "manual" | "manual_schedule" | "worker_schedule";
  duration_ms: number;
  requested_by_user_id: string;
  created_at: string;
}

export interface AgentMemoryRiskSigningKey {
  id: string;
  agent_id: string;
  version: number;
  activated_by_user_id: string;
  created_at: string;
}

export interface AgentMemoryExerciseSchedule {
  id: string | null;
  agent_id: string;
  enabled: boolean;
  cadence_hours: number;
  heartbeat_slo_minutes: number;
  next_run_at: string | null;
  last_run_at: string | null;
  last_worker_heartbeat_at: string | null;
  last_slo_alert_at: string | null;
  slo_breach_count: number;
  updated_at: string | null;
}

export interface AgentMemoryExerciseDue {
  executed: boolean;
  next_run_at: string | null;
  exercise: AgentMemoryResponseExercise | null;
}

export interface AgentMemorySchedulerMetrics {
  agent_id: string;
  worker_exercises: number;
  worker_passed: number;
  worker_failed: number;
  average_duration_ms: number;
  last_worker_run_at: string | null;
  schedule_enabled: boolean;
  next_run_at: string | null;
  overdue_seconds: number;
  heartbeat_status: "disabled" | "waiting" | "healthy" | "overdue";
  heartbeat_slo_minutes: number;
  last_worker_heartbeat_at: string | null;
  last_slo_alert_at: string | null;
  slo_breach_count: number;
}

export interface AgentMemoryReencryptionJob {
  id: string;
  agent_id: string;
  status: "pending" | "running" | "completed" | "failed" | "closed";
  target_master_key_id: string;
  key_provider: "environment" | "external";
  vault_credential_bound: boolean;
  batch_size: number;
  total_count: number;
  scanned_count: number;
  rotated_count: number;
  failed_count: number;
  retry_count: number;
  max_retry_attempts: number;
  retry_attempts_remaining: number;
  last_retry_at: string | null;
  recovery_status: "not_assessed" | "ready" | "blocked";
  last_recovery_assessment_at: string | null;
  recovery_assessed_by_user_id: string | null;
  closure_code: string | null;
  closed_at: string | null;
  closed_by_user_id: string | null;
  error_code: string | null;
  requested_by_user_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  purge_after: string | null;
  updated_at: string;
}

export interface AgentMemoryReencryptionRecoveryAssessment {
  job_id: string;
  status: "ready" | "blocked";
  checks: Record<string, boolean>;
  instructions: string[];
  retry_attempts_remaining: number;
  assessed_at: string;
}

export interface AgentMemoryVaultCredentialOption {
  id: string;
  name: string;
  plugin_code: string;
  provider_name: string;
  managed_provider: boolean;
  expires_at: string | null;
}

export interface AgentMemoryKeyringStatus {
  source: "environment" | "managed";
  provider_code: string;
  status: "active";
  health_status: "not_applicable" | "unknown" | "healthy" | "unavailable";
  activated_at: string | null;
  last_resolved_at: string | null;
  last_health_checked_at: string | null;
  credential_expires_at: string | null;
  expiry_warning_sent: boolean;
  automatic_exit_job_id: string | null;
  automatic_exit_status:
    "pending" | "running" | "completed" | "failed" | "closed" | null;
  slo_status: "not_applicable" | "within_slo" | "breached";
  identity_canary_status:
    "not_applicable" | "unknown" | "healthy" | "unavailable";
  last_identity_canary_at: string | null;
}

export interface AgentMemoryVaultIncident {
  id: string;
  provider_code: string;
  status: "open" | "resolved";
  failure_count: number;
  alerted: boolean;
  slo_breached: boolean;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
}

export interface AgentMemoryKeyringPolicy {
  expiry_warning_days: number;
  automatic_exit_enabled: boolean;
  automatic_exit_batch_size: number;
  vault_failure_alert_threshold: number;
  vault_slo_minutes: number;
  availability_retention_days: number;
  on_call_user_ids: string[];
  on_call_timezone: string;
  on_call_start_hour: number;
  on_call_end_hour: number;
  identity_canary_days: number;
  identity_canary_interval_hours: number;
  configured: boolean;
  updated_at: string | null;
}

export interface AgentMemoryVaultAvailability {
  provider_code: string;
  window_started_at: string;
  total_checks: number;
  successful_checks: number;
  failed_checks: number;
  slo_breaches: number;
  availability_percent: number;
}

export interface AgentMemoryWorkloadIdentityRotation {
  id: string;
  agent_id: string;
  provider_code: string;
  status: "pending" | "approved" | "rejected";
  requested_by_user_id: string;
  decided_by_user_id: string | null;
  verified: boolean;
  created_at: string;
  decided_at: string | null;
}

export interface AgentMemoryCredentialRenewal {
  id: string;
  agent_id: string;
  extension_days: number;
  proposed_expires_at: string;
  status: "pending" | "approved" | "rejected";
  requested_by_user_id: string;
  decided_by_user_id: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ManagedVaultMetric {
  provider_code: string;
  provider_name: string;
  total_tests: number;
  successful_tests: number;
  failed_tests: number;
  success_rate: number;
  average_duration_ms: number;
  last_tested_at: string | null;
}

export interface AgentMemoryReencryptionLegalHold {
  id: string;
  job_id: string;
  reason_code: "legal_claim" | "regulatory_request" | "audit_preservation";
  retention_days: number;
  status: "pending" | "approved" | "rejected" | "expired";
  requested_by_user_id: string;
  decided_by_user_id: string | null;
  expires_at: string;
  expiration_reminder_sent: boolean;
  created_at: string;
  decided_at: string | null;
}

export interface AgentMemoryLegalHoldRenewal {
  id: string;
  hold_id: string;
  job_id: string;
  extension_days: number;
  proposed_expires_at: string;
  status: "pending" | "approved" | "rejected";
  requested_by_user_id: string;
  decided_by_user_id: string | null;
  created_at: string;
  decided_at: string | null;
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

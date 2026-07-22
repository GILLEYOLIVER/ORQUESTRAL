import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export interface WorkflowNodeDefinition {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface WorkflowConnectionDefinition {
  id: string;
  source: string;
  target: string;
  source_handle?: string;
}

export interface WorkflowDefinition {
  nodes: WorkflowNodeDefinition[];
  connections: WorkflowConnectionDefinition[];
  variables: Record<string, unknown>;
  execution_policy?: WorkflowExecutionPolicy;
  compensation_policy?: WorkflowCompensationPolicy;
  version: 1;
}

export interface WorkflowCompensationPolicy {
  enabled: boolean;
  mode: "manual";
  on_status: Array<"error" | "canceled">;
}

export interface WorkflowExecutionPolicy {
  max_steps: number;
  timeout_seconds: number;
  concurrency_limit: number;
  on_conflict: "reject";
}

export interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
  definition: WorkflowDefinition;
  version: number;
  status: "draft" | "active" | "inactive" | "error";
  sync_status: "pending" | "synced" | "error";
  webhook_url: string;
  last_error: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreatedResponse extends WorkflowResponse {
  webhook_secret: string;
}

export interface WorkflowExecutionResponse {
  id: string;
  workflow_id: string;
  source: string;
  status: "queued" | "running" | "success" | "error" | "canceled" | "waiting";
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  error_summary: string | null;
  cancel_reason: string | null;
  provider_key: string;
  compensation_status: "not_required" | "pending" | "acknowledged";
  compensation_plan: WorkflowCompensationItem[];
  remote_cancel_status:
    "not_requested" | "unsupported" | "requested" | "confirmed" | "failed";
  duration_ms: number | null;
  cancellation_requested_at: string | null;
  canceled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface WorkflowEngineStatus {
  provider: string;
  configured: boolean;
  available: boolean;
  message: string;
  circuit_state: "closed" | "open" | "half_open";
  circuit_failures: number;
  circuit_retry_at: string | null;
}

export interface WorkflowCompensationItem {
  source_node_id: string;
  source_label: string;
  action_node_id: string;
  action_label: string;
  status: "pending" | "acknowledged";
  acknowledged_at?: string;
}

export interface WorkflowBlock {
  type: string;
  category: string;
  label: string;
  description: string;
  required_fields: string[];
  defaults: Record<string, unknown>;
}

export interface WorkflowValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  node_id: string | null;
}

export interface WorkflowValidationResponse {
  valid: boolean;
  issues: WorkflowValidationIssue[];
}

export interface WorkflowSimulationTrace {
  node_id: string;
  label: string;
  block_type: string;
  status: "simulated" | "approval_required" | "blocked_effect";
  detail: string;
  side_effect: boolean;
}

export interface WorkflowSimulationResponse {
  valid: boolean;
  publishable: boolean;
  estimated_steps: number;
  blocked_side_effects: number;
  execution_policy: WorkflowExecutionPolicy;
  compensation_policy: WorkflowCompensationPolicy;
  compensation_plan: WorkflowCompensationItem[];
  input_summary: Record<string, unknown>;
  trace: WorkflowSimulationTrace[];
  issues: WorkflowValidationIssue[];
}

export interface WorkflowMetricsResponse {
  total: number;
  success: number;
  errors: number;
  canceled: number;
  waiting: number;
  running: number;
  domain_event_executions: number;
  cancellation_requests: number;
  compensation_pending: number;
  replay_count: number;
  success_rate: number;
  average_duration_ms: number;
}

export interface EventContractOption {
  id: string;
  event_type: string;
  version: number;
  status: string;
}

export interface WorkflowVersion {
  id: string;
  version: number;
  name: string;
  description: string | null;
  definition: WorkflowDefinition;
  change_summary: string | null;
  created_at: string;
}

export interface WorkflowComparison {
  from_version: number;
  to_version: number;
  added_nodes: string[];
  removed_nodes: string[];
  changed_nodes: string[];
  connections_changed: boolean;
}

export function useWorkflows(enabled = true) {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["workflows", me?.current_company?.id],
    queryFn: () => request<WorkflowResponse[]>("/workflows"),
    enabled:
      enabled &&
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("workflows.view") ?? false),
  });
}

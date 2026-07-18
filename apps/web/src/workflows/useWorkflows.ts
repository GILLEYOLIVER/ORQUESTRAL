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
  version: 1;
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
  duration_ms: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface WorkflowEngineStatus {
  configured: boolean;
  available: boolean;
  message: string;
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

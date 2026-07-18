import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
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

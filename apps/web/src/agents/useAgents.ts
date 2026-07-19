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
    created_at: string;
    updated_at: string;
  };
  user_message: AgentMessageResponse;
  assistant_message: AgentMessageResponse;
  pending_actions: AgentToolRunResponse[];
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

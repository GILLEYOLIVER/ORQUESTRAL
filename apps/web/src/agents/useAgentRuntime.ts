import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { request } from "../lib/http";

export type RuntimeStatus = "draft" | "published" | "paused" | "retired";

export type AgentSchedule = {
  id: string;
  schedule_key: string;
  version: number;
  status: RuntimeStatus;
  name: string;
  cadence_minutes: number;
  next_run_at: string | null;
};

export type AgentEventTrigger = {
  id: string;
  trigger_key: string;
  version: number;
  status: RuntimeStatus;
  name: string;
  event_type: string;
};

export type CredentialCatalogItem = {
  id: string;
  name: string;
  usable: boolean;
};

export type CredentialBinding = {
  id: string;
  tool_key: string;
  credential_id: string;
  enabled: boolean;
};

export type RuntimeDispatch = {
  id: string;
  source_type: "schedule" | "event";
  status: "ready" | "blocked";
  reason_code: string | null;
  scheduled_for: string;
};

export type ScheduleInput = {
  schedule_key: string;
  name: string;
  objective: string;
  cadence_minutes: number;
  required_tool_keys: string[];
};

export type TriggerInput = {
  trigger_key: string;
  name: string;
  event_type: string;
  min_event_version: number;
  max_event_version: number | null;
  objective: string;
  required_tool_keys: string[];
};

export function useAgentRuntime(agentId: string | null, canConfigure: boolean) {
  const enabled = Boolean(agentId);
  const schedules = useQuery({
    queryKey: ["agent-runtime-schedules", agentId],
    queryFn: () => request<AgentSchedule[]>(`/agents/${agentId}/schedules`),
    enabled,
  });
  const triggers = useQuery({
    queryKey: ["agent-runtime-triggers", agentId],
    queryFn: () =>
      request<AgentEventTrigger[]>(`/agents/${agentId}/event-triggers`),
    enabled,
  });
  const dispatches = useQuery({
    queryKey: ["agent-runtime-dispatches", agentId],
    queryFn: () =>
      request<RuntimeDispatch[]>(`/agents/${agentId}/runtime-dispatches`),
    enabled,
    refetchInterval: 30_000,
  });
  const credentials = useQuery({
    queryKey: ["agent-runtime-credentials"],
    queryFn: () =>
      request<CredentialCatalogItem[]>("/agents/runtime/credential-catalog"),
    enabled: enabled && canConfigure,
  });
  const bindings = useQuery({
    queryKey: ["agent-runtime-bindings", agentId],
    queryFn: () =>
      request<CredentialBinding[]>(`/agents/${agentId}/credential-bindings`),
    enabled: enabled && canConfigure,
  });
  return { bindings, credentials, dispatches, schedules, triggers };
}

export function useAgentRuntimeActions(agentId: string | null) {
  const queryClient = useQueryClient();
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-schedules", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-triggers", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-bindings", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-dispatches", agentId],
      }),
    ]);

  const createSchedule = useMutation({
    mutationFn: (payload: ScheduleInput) =>
      request<AgentSchedule>(`/agents/${agentId}/schedules`, {
        method: "POST",
        body: payload,
      }),
    onSuccess: refresh,
  });
  const publishSchedule = useMutation({
    mutationFn: (scheduleId: string) =>
      request<AgentSchedule>(
        `/agents/${agentId}/schedules/${scheduleId}/publish`,
        {
          method: "POST",
        },
      ),
    onSuccess: refresh,
  });
  const pauseSchedule = useMutation({
    mutationFn: (scheduleId: string) =>
      request<AgentSchedule>(
        `/agents/${agentId}/schedules/${scheduleId}/pause`,
        {
          method: "POST",
        },
      ),
    onSuccess: refresh,
  });
  const createTrigger = useMutation({
    mutationFn: (payload: TriggerInput) =>
      request<AgentEventTrigger>(`/agents/${agentId}/event-triggers`, {
        method: "POST",
        body: payload,
      }),
    onSuccess: refresh,
  });
  const publishTrigger = useMutation({
    mutationFn: (triggerId: string) =>
      request<AgentEventTrigger>(
        `/agents/${agentId}/event-triggers/${triggerId}/publish`,
        {
          method: "POST",
        },
      ),
    onSuccess: refresh,
  });
  const pauseTrigger = useMutation({
    mutationFn: (triggerId: string) =>
      request<AgentEventTrigger>(
        `/agents/${agentId}/event-triggers/${triggerId}/pause`,
        {
          method: "POST",
        },
      ),
    onSuccess: refresh,
  });
  const bindCredential = useMutation({
    mutationFn: ({
      toolKey,
      credentialId,
    }: {
      toolKey: string;
      credentialId: string;
    }) =>
      request<CredentialBinding>(
        `/agents/${agentId}/credential-bindings/${encodeURIComponent(toolKey)}`,
        { method: "PUT", body: { credential_id: credentialId, enabled: true } },
      ),
    onSuccess: refresh,
  });
  return {
    bindCredential,
    createSchedule,
    createTrigger,
    pauseSchedule,
    pauseTrigger,
    publishSchedule,
    publishTrigger,
  };
}

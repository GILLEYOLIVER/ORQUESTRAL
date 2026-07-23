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
  required_tool_keys: string[];
  tool_arguments: Record<string, Record<string, unknown>>;
  execution_mode: "shadow" | "live";
  canary_percentage: number;
  next_run_at: string | null;
};

export type AgentEventTrigger = {
  id: string;
  trigger_key: string;
  version: number;
  status: RuntimeStatus;
  name: string;
  event_type: string;
  required_tool_keys: string[];
  tool_arguments: Record<string, Record<string, unknown>>;
  execution_mode: "shadow" | "live";
  canary_percentage: number;
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
  source_type: "schedule" | "event" | "retry";
  retry_of_dispatch_id: string | null;
  status:
    | "ready"
    | "blocked"
    | "processing"
    | "awaiting_approval"
    | "simulated"
    | "completed"
    | "failed";
  reason_code: string | null;
  error_code: string | null;
  execution_mode: "shadow" | "live";
  canary_percentage: number;
  attempt_count: number;
  agent_run_id: string | null;
  scheduled_for: string;
};

export type DispatchReview = {
  id: string;
  interrupted_dispatch_id: string;
  replacement_dispatch_id: string | null;
  decision: "close" | "retry";
  status: "closed" | "pending_approval" | "approved";
  reason: string;
  requested_by_user_id: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DispatchReviewSummary = {
  pending: number;
  overdue: number;
  closed: number;
  approved: number;
  repeat_interruptions: number;
  average_decision_minutes: number | null;
  oldest_pending_minutes: number | null;
  retry_rate_percent: number;
  sla_minutes: number;
  escalation_minutes: number;
  policy_version: number | null;
};

export type DispatchReviewSLAPolicy = {
  id: string;
  agent_id: string;
  version: number;
  status: "draft" | "published" | "retired";
  name: string;
  sla_minutes: number;
  escalation_minutes: number;
  acknowledgement_minutes: number;
  on_call_user_ids: string[];
  on_call_timezone: string;
  on_call_start_hour: number;
  on_call_end_hour: number;
  on_call_weekdays: number[];
  on_call_shifts: DispatchReviewShift[];
  holiday_calendar: DispatchReviewHoliday[];
  minimum_coverage: number;
  created_at: string;
  published_at: string | null;
};

export type DispatchReviewShift = {
  user_id: string;
  weekdays: number[];
  start_hour: number;
  end_hour: number;
};

export type DispatchReviewHoliday = {
  date: string;
  name: string;
  coverage_required: boolean;
};

export type DispatchReviewCoverage = {
  valid: boolean;
  minimum_coverage: number;
  required_slots: number;
  covered_slots: number;
  issues: Array<{
    code: string;
    message: string;
    weekday: number | null;
    hour: number | null;
    user_id: string | null;
  }>;
};

export type DispatchReviewAssignment = {
  id: string;
  agent_id: string;
  review_id: string;
  previous_assignment_id: string | null;
  assigned_to_user_id: string;
  assigned_by_user_id: string | null;
  acknowledged_by_user_id: string | null;
  source: "on_call" | "manual" | "fallback";
  status: "pending" | "acknowledged" | "reassigned" | "closed";
  reason_code: string;
  assigned_at: string;
  acknowledged_at: string | null;
  ended_at: string | null;
};

export type CompanyUserOption = {
  user_id: string;
  name: string;
  email: string;
  membership_status: string;
};

export type DispatchReviewOnCallException = {
  id: string;
  agent_id: string;
  policy_id: string;
  user_id: string;
  status: "active" | "cancelled";
  reason: string;
  starts_at: string;
  ends_at: string;
  created_at: string;
};

export type DispatchReviewOnCallHandoff = {
  id: string;
  agent_id: string;
  policy_id: string;
  from_user_id: string;
  to_user_id: string;
  requested_by_user_id: string;
  responded_by_user_id: string | null;
  status: "pending" | "accepted" | "rejected" | "cancelled" | "expired";
  reason: string;
  starts_at: string;
  ends_at: string;
  responded_at: string | null;
  created_at: string;
};

export type ScheduleInput = {
  schedule_key: string;
  name: string;
  objective: string;
  cadence_minutes: number;
  required_tool_keys: string[];
  tool_arguments: Record<string, Record<string, unknown>>;
  execution_mode: "shadow" | "live";
  canary_percentage: number;
};

export type TriggerInput = {
  trigger_key: string;
  name: string;
  event_type: string;
  min_event_version: number;
  max_event_version: number | null;
  objective: string;
  required_tool_keys: string[];
  tool_arguments: Record<string, Record<string, unknown>>;
  execution_mode: "shadow" | "live";
  canary_percentage: number;
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
  const reviews = useQuery({
    queryKey: ["agent-runtime-dispatch-reviews", agentId],
    queryFn: () =>
      request<DispatchReview[]>(
        `/agents/${agentId}/runtime-dispatch-reviews`,
      ),
    enabled,
    refetchInterval: 30_000,
  });
  const reviewSummary = useQuery({
    queryKey: ["agent-runtime-dispatch-review-summary", agentId],
    queryFn: () =>
      request<DispatchReviewSummary>(
        `/agents/${agentId}/runtime-dispatch-reviews/summary`,
      ),
    enabled,
    refetchInterval: 30_000,
  });
  const reviewPolicies = useQuery({
    queryKey: ["agent-runtime-dispatch-review-sla-policies", agentId],
    queryFn: () =>
      request<DispatchReviewSLAPolicy[]>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies`,
      ),
    enabled,
  });
  const activeReviewPolicyId =
    reviewPolicies.data?.find((policy) => policy.status === "published")?.id ?? null;
  const onCallExceptions = useQuery({
    queryKey: ["agent-runtime-review-on-call-exceptions", agentId, activeReviewPolicyId],
    queryFn: () =>
      request<DispatchReviewOnCallException[]>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/` +
          `${activeReviewPolicyId}/on-call-exceptions`,
      ),
    enabled: enabled && Boolean(activeReviewPolicyId),
  });
  const onCallHandoffs = useQuery({
    queryKey: ["agent-runtime-review-on-call-handoffs", agentId, activeReviewPolicyId],
    queryFn: () =>
      request<DispatchReviewOnCallHandoff[]>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/` +
          `${activeReviewPolicyId}/on-call-handoffs`,
      ),
    enabled: enabled && Boolean(activeReviewPolicyId),
  });
  const reviewAssignments = useQuery({
    queryKey: ["agent-runtime-dispatch-review-assignments", agentId],
    queryFn: () =>
      request<DispatchReviewAssignment[]>(
        `/agents/${agentId}/runtime-dispatch-review-assignments`,
      ),
    enabled,
    refetchInterval: 30_000,
  });
  const companyUsers = useQuery({
    queryKey: ["company-users"],
    queryFn: () => request<CompanyUserOption[]>("/company/users"),
    enabled: enabled && canConfigure,
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
  return {
    bindings,
    companyUsers,
    credentials,
    dispatches,
    reviews,
    reviewPolicies,
    reviewAssignments,
    reviewSummary,
    schedules,
    triggers,
    activeReviewPolicyId,
    onCallExceptions,
    onCallHandoffs,
  };
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
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-dispatch-reviews", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-dispatch-review-summary", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-dispatch-review-sla-policies", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-dispatch-review-assignments", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-review-on-call-exceptions", agentId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["agent-runtime-review-on-call-handoffs", agentId],
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
  const reviewDispatch = useMutation({
    mutationFn: ({
      dispatchId,
      decision,
      reason,
      idempotencyKey,
    }: {
      dispatchId: string;
      decision: "close" | "retry";
      reason: string;
      idempotencyKey: string;
    }) =>
      request<DispatchReview>(
        `/agents/${agentId}/runtime-dispatches/${dispatchId}/reviews`,
        {
          method: "POST",
          body: {
            decision,
            reason,
            idempotency_key: idempotencyKey,
          },
        },
      ),
    onSuccess: refresh,
  });
  const approveDispatchRetry = useMutation({
    mutationFn: ({
      reviewId,
      idempotencyKey,
    }: {
      reviewId: string;
      idempotencyKey: string;
    }) =>
      request<DispatchReview>(
        `/agents/${agentId}/runtime-dispatch-reviews/${reviewId}/approve-retry`,
        {
          method: "POST",
          body: { idempotency_key: idempotencyKey },
        },
      ),
    onSuccess: refresh,
  });
  const createReviewSLAPolicy = useMutation({
    mutationFn: (payload: {
      name: string;
      sla_minutes: number;
      escalation_minutes: number;
      acknowledgement_minutes: number;
      on_call_user_ids: string[];
      on_call_timezone: string;
      on_call_start_hour: number;
      on_call_end_hour: number;
      on_call_weekdays: number[];
      on_call_shifts: DispatchReviewShift[];
      holiday_calendar: DispatchReviewHoliday[];
      minimum_coverage: number;
    }) =>
      request<DispatchReviewSLAPolicy>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies`,
        { method: "POST", body: payload },
      ),
    onSuccess: refresh,
  });
  const publishReviewSLAPolicy = useMutation({
    mutationFn: (policyId: string) =>
      request<DispatchReviewSLAPolicy>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/publish`,
        { method: "POST" },
      ),
    onSuccess: refresh,
  });
  const validateReviewSLAPolicy = useMutation({
    mutationFn: (policyId: string) =>
      request<DispatchReviewCoverage>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/coverage`,
      ),
  });
  const acknowledgeReviewAssignment = useMutation({
    mutationFn: ({ reviewId, assignmentId }: { reviewId: string; assignmentId: string }) =>
      request<DispatchReviewAssignment>(
        `/agents/${agentId}/runtime-dispatch-reviews/${reviewId}/assignments/` +
          `${assignmentId}/acknowledge`,
        { method: "POST" },
      ),
    onSuccess: refresh,
  });
  const reassignReview = useMutation({
    mutationFn: ({
      reviewId,
      assignedToUserId,
      reason,
    }: {
      reviewId: string;
      assignedToUserId: string;
      reason: string;
    }) =>
      request<DispatchReviewAssignment>(
        `/agents/${agentId}/runtime-dispatch-reviews/${reviewId}/reassign`,
        {
          method: "POST",
          body: { assigned_to_user_id: assignedToUserId, reason },
        },
      ),
    onSuccess: refresh,
  });
  const createOnCallException = useMutation({
    mutationFn: ({
      policyId,
      userId,
      reason,
      startsAt,
      endsAt,
    }: {
      policyId: string;
      userId: string;
      reason: string;
      startsAt: string;
      endsAt: string;
    }) =>
      request<DispatchReviewOnCallException>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/` +
          "on-call-exceptions",
        {
          method: "POST",
          body: { user_id: userId, reason, starts_at: startsAt, ends_at: endsAt },
        },
      ),
    onSuccess: refresh,
  });
  const cancelOnCallException = useMutation({
    mutationFn: ({ policyId, exceptionId }: { policyId: string; exceptionId: string }) =>
      request<DispatchReviewOnCallException>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/` +
          `on-call-exceptions/${exceptionId}/cancel`,
        { method: "POST" },
      ),
    onSuccess: refresh,
  });
  const createOnCallHandoff = useMutation({
    mutationFn: ({
      policyId,
      fromUserId,
      toUserId,
      reason,
      startsAt,
      endsAt,
    }: {
      policyId: string;
      fromUserId: string;
      toUserId: string;
      reason: string;
      startsAt: string;
      endsAt: string;
    }) =>
      request<DispatchReviewOnCallHandoff>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/` +
          "on-call-handoffs",
        {
          method: "POST",
          body: {
            from_user_id: fromUserId,
            to_user_id: toUserId,
            reason,
            starts_at: startsAt,
            ends_at: endsAt,
            idempotency_key: crypto.randomUUID(),
          },
        },
      ),
    onSuccess: refresh,
  });
  const respondOnCallHandoff = useMutation({
    mutationFn: ({
      policyId,
      handoffId,
      decision,
    }: {
      policyId: string;
      handoffId: string;
      decision: "accept" | "reject";
    }) =>
      request<DispatchReviewOnCallHandoff>(
        `/agents/${agentId}/runtime-dispatch-review-sla-policies/${policyId}/` +
          `on-call-handoffs/${handoffId}/respond`,
        { method: "POST", body: { decision } },
      ),
    onSuccess: refresh,
  });
  return {
    acknowledgeReviewAssignment,
    approveDispatchRetry,
    bindCredential,
    createReviewSLAPolicy,
    createOnCallException,
    createOnCallHandoff,
    createSchedule,
    createTrigger,
    pauseSchedule,
    pauseTrigger,
    publishSchedule,
    publishReviewSLAPolicy,
    validateReviewSLAPolicy,
    publishTrigger,
    reassignReview,
    cancelOnCallException,
    respondOnCallHandoff,
    reviewDispatch,
  };
}

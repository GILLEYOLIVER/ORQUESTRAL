import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export interface NotificationItem {
  id: string;
  event_type: string;
  title: string;
  message: string;
  severity: "info" | "success" | "warning" | "error";
  resource_type: string | null;
  resource_id: string | null;
  data: Record<string, unknown>;
  delivery_status: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface NotificationSummary {
  unread_count: number;
  pending_approvals: number;
}

export interface NotificationPreference {
  event_type: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  whatsapp_recipient: string | null;
  reminders_enabled: boolean;
  email_channel_configured: boolean;
  whatsapp_channel_configured: boolean;
}

export interface ApprovalAction {
  id: string;
  actor_user_id: string | null;
  action: string;
  comment: string | null;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  source_type: "workflow" | "agent" | "generic";
  requested_by_user_id: string | null;
  assigned_user_id: string | null;
  workflow_id: string | null;
  workflow_execution_id: string | null;
  agent_tool_run_id: string | null;
  title: string;
  description: string;
  context: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "cancelled" | "expired";
  reminder_at: string | null;
  expires_at: string | null;
  decided_at: string | null;
  created_at: string;
  actions: ApprovalAction[];
}

export interface ApprovalDelegation {
  id: string;
  delegator_user_id: string;
  delegate_user_id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  status: "active" | "revoked";
  effective: boolean;
  created_at: string;
  revoked_at: string | null;
}

function useNotificationAccess(enabled = true) {
  const { me, status } = useSession();
  return (
    enabled && status === "authenticated" && Boolean(me?.current_company?.id)
  );
}

export function useNotificationSummary(enabled = true) {
  const canLoad = useNotificationAccess(enabled);
  return useQuery({
    queryKey: ["notification-summary"],
    queryFn: () => request<NotificationSummary>("/notifications/summary"),
    enabled: canLoad,
    refetchInterval: 30_000,
  });
}

export function useNotifications() {
  const canLoad = useNotificationAccess();
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => request<NotificationItem[]>("/notifications"),
    enabled: canLoad,
  });
}

export function useNotificationPreferences() {
  const canLoad = useNotificationAccess();
  return useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () =>
      request<NotificationPreference[]>("/notifications/preferences"),
    enabled: canLoad,
  });
}

export function useApprovals(enabled: boolean) {
  const canLoad = useNotificationAccess(enabled);
  return useQuery({
    queryKey: ["approvals"],
    queryFn: () =>
      request<ApprovalRequest[]>("/notifications/approvals?status=pending"),
    enabled: canLoad,
  });
}

export function useApprovalDelegations(enabled: boolean) {
  const canLoad = useNotificationAccess(enabled);
  return useQuery({
    queryKey: ["approval-delegations"],
    queryFn: () =>
      request<ApprovalDelegation[]>("/notifications/approval-delegations"),
    enabled: canLoad,
  });
}

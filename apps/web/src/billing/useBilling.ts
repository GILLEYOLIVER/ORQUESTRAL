import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export type UsageMetric =
  | "users"
  | "agents"
  | "workflows"
  | "workflow_executions"
  | "tokens"
  | "storage_bytes"
  | "integrations"
  | "documents"
  | "api_calls";

export interface PlanResponse {
  id: string;
  name: string;
  description: string | null;
  price: string;
  billing_cycle: "monthly" | "yearly";
  limits: Partial<Record<UsageMetric, number | null>>;
  status: "active" | "inactive" | "archived";
  created_at: string;
  updated_at: string;
}

export interface SubscriptionResponse {
  id: string;
  company_id: string;
  plan: PlanResponse;
  status: string;
  started_at: string;
  trial_ends_at: string | null;
  current_period_start: string;
  current_period_end: string;
  cancelled_at: string | null;
}

export interface LimitResponse {
  metric: UsageMetric;
  label: string;
  used: number;
  limit: number | null;
  remaining: number | null;
  percentage: number | null;
  exceeded: boolean;
}

export interface BillingOverview {
  enforcement_enabled: boolean;
  subscription: SubscriptionResponse | null;
  limits: LimitResponse[];
  generated_at: string;
}

export function useBillingOverview() {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["billing-overview", me?.current_company?.id],
    queryFn: () => request<BillingOverview>("/billing/overview"),
    enabled:
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("billing.view") ?? false),
  });
}

export function usePlans() {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["billing-plans"],
    queryFn: () => request<PlanResponse[]>("/billing/plans"),
    enabled:
      status === "authenticated" &&
      (me?.permissions.includes("billing.view") ?? false),
  });
}

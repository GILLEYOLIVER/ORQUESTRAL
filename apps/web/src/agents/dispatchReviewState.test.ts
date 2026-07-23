import { describe, expect, it } from "vitest";

import type { RuntimeDispatch } from "./useAgentRuntime";
import { dispatchSourceLabel, requiresDispatchReview } from "./dispatchReviewState";

const interrupted: RuntimeDispatch = {
  id: "dispatch-1",
  source_type: "schedule",
  retry_of_dispatch_id: null,
  status: "failed",
  reason_code: "execution_interrupted_manual_review",
  error_code: "execution_interrupted_manual_review",
  execution_mode: "live",
  canary_percentage: 10,
  attempt_count: 1,
  agent_run_id: "run-1",
  scheduled_for: "2026-07-22T22:00:00Z",
};

describe("estado de revisão de despacho", () => {
  it("exige revisão somente para interrupção incerta", () => {
    expect(requiresDispatchReview(interrupted)).toBe(true);
    expect(
      requiresDispatchReview({ ...interrupted, error_code: "tool_execution_failed" }),
    ).toBe(false);
  });

  it("identifica a linhagem de repetição para o administrador", () => {
    expect(dispatchSourceLabel("retry")).toBe("Repetição autorizada");
  });
});

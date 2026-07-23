import { describe, expect, it } from "vitest";

import { parseRuntimeToolArguments } from "./runtimeToolArguments";
import type { DispatchReviewSLAPolicy } from "./useAgentRuntime";

describe("parseRuntimeToolArguments", () => {
  it("aceita argumentos tipados somente para ferramentas autorizadas", () => {
    expect(
      parseRuntimeToolArguments(
        '{"orkestral.company.summary": {}}',
        ["orkestral.company.summary"],
      ),
    ).toEqual({ "orkestral.company.summary": {} });
  });

  it("bloqueia JSON que injeta uma ferramenta fora da agenda", () => {
    expect(() =>
      parseRuntimeToolArguments('{"admin.dangerous": {}}', [
        "orkestral.company.summary",
      ]),
    ).toThrow("não está na lista autorizada");
  });

  it("bloqueia argumentos que nao sejam objetos", () => {
    expect(() =>
      parseRuntimeToolArguments('{"orkestral.company.summary": "segredo"}', [
        "orkestral.company.summary",
      ]),
    ).toThrow("devem ser um objeto JSON");
  });
});

describe("DispatchReviewSLAPolicy", () => {
  it("mantém o contrato versionado exibido pela central operacional", () => {
    const policy: DispatchReviewSLAPolicy = {
      id: "policy-1",
      agent_id: "agent-1",
      version: 2,
      status: "published",
      name: "Plantão crítico",
      sla_minutes: 15,
      escalation_minutes: 45,
      acknowledgement_minutes: 10,
      on_call_user_ids: ["user-1"],
      on_call_timezone: "America/Sao_Paulo",
      on_call_start_hour: 8,
      on_call_end_hour: 18,
      on_call_weekdays: [0, 1, 2, 3, 4],
      on_call_shifts: [
        {
          user_id: "user-1",
          weekdays: [0, 1, 2, 3, 4],
          start_hour: 8,
          end_hour: 18,
        },
      ],
      holiday_calendar: [
        {
          date: "2026-09-07",
          name: "Independência do Brasil",
          coverage_required: false,
        },
      ],
      minimum_coverage: 1,
      created_at: "2026-07-22T12:00:00Z",
      published_at: "2026-07-22T12:05:00Z",
    };

    expect(policy.escalation_minutes).toBeGreaterThan(policy.sla_minutes);
    expect(policy.status).toBe("published");
    expect(policy.on_call_user_ids).toHaveLength(1);
    expect(policy.on_call_weekdays).toEqual([0, 1, 2, 3, 4]);
    expect(policy.on_call_shifts).toHaveLength(1);
    expect(policy.holiday_calendar[0].coverage_required).toBe(false);
  });
});

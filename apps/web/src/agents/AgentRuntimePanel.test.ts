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
      created_at: "2026-07-22T12:00:00Z",
      published_at: "2026-07-22T12:05:00Z",
    };

    expect(policy.escalation_minutes).toBeGreaterThan(policy.sla_minutes);
    expect(policy.status).toBe("published");
  });
});

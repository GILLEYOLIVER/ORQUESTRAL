import { describe, expect, it } from "vitest";

import { parseRuntimeToolArguments } from "./runtimeToolArguments";

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

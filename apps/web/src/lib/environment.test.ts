import { describe, expect, it } from "vitest";

import { resolveEnvironment } from "./environment";

describe("resolveEnvironment", () => {
  it("mantem os recursos completos no ambiente local por padrao", () => {
    expect(resolveEnvironment({})).toEqual({
      remoteDevelopment: false,
      n8nEnabled: true,
      objectStorageEnabled: true,
    });
  });

  it("ativa o aviso remoto e desativa integracoes indisponiveis", () => {
    expect(
      resolveEnvironment({
        VITE_REMOTE_DEVELOPMENT: "true",
        VITE_N8N_ENABLED: "false",
        VITE_OBJECT_STORAGE_ENABLED: "false",
      }),
    ).toEqual({
      remoteDevelopment: true,
      n8nEnabled: false,
      objectStorageEnabled: false,
    });
  });
});

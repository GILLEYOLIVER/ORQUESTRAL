import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MeResponse } from "@orkestral/shared-types";
import { PermissionGuard } from "../components/PermissionGuard";
import { SessionContext, type SessionContextValue } from "../session/context";

function renderGuard(permissions: string[]) {
  const session: SessionContextValue = {
    developmentLogin: vi.fn(),
    getAccessToken: () => "token-em-memoria",
    login: vi.fn(),
    logout: vi.fn(),
    me: { permissions } as MeResponse,
    refreshProfile: vi.fn(),
    selectCompany: vi.fn(),
    status: "authenticated",
  };
  return render(
    <SessionContext.Provider value={session}>
      <PermissionGuard
        all={["roles.view"]}
        fallback={<span>Acesso negado</span>}
      >
        <span>Conteúdo autorizado</span>
      </PermissionGuard>
    </SessionContext.Provider>,
  );
}

describe("PermissionGuard", () => {
  it("exibe o conteúdo quando a permissão está ativa", () => {
    renderGuard(["roles.view"]);
    expect(screen.getByText("Conteúdo autorizado")).toBeInTheDocument();
  });

  it("usa o fallback quando a permissão está ausente", () => {
    renderGuard(["users.view"]);
    expect(screen.getByText("Acesso negado")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo autorizado")).not.toBeInTheDocument();
  });
});

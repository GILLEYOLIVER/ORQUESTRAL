import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { MeResponse } from "@orkestral/shared-types";
import { LoginPage } from "../pages/LoginPage";
import { SessionContext, type SessionContextValue } from "../session/context";

vi.mock("../lib/http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/http")>();
  return {
    ...actual,
    request: vi.fn().mockResolvedValue({ enabled: true }),
  };
});

const profile: MeResponse = {
  access_mode: "standard",
  current_company: {
    id: "6a818688-1d95-4fac-9c2d-b64b3317dbaa",
    language: "pt-BR",
    legal_name: "Empresa Teste Ltda.",
    slug: "empresa-teste",
    status: "active",
    timezone: "America/Sao_Paulo",
    trade_name: "Empresa Teste",
  },
  memberships: [],
  permissions: ["company:manage"],
  requires_company_selection: false,
  user: {
    email: "teste@empresa.com.br",
    id: "a851b9bc-a83d-41ad-978c-8dabba888ced",
    is_platform_admin: false,
    last_login_at: null,
    name: "Pessoa Teste",
    status: "active",
  },
};

function renderLogin(overrides: Partial<SessionContextValue> = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const session: SessionContextValue = {
    developmentLogin: vi.fn().mockResolvedValue(profile),
    getAccessToken: () => null,
    login: vi.fn().mockResolvedValue(profile),
    loginWithReadOnlyLink: vi.fn().mockResolvedValue(profile),
    logout: vi.fn().mockResolvedValue(undefined),
    me: null,
    refreshProfile: vi.fn().mockResolvedValue(null),
    selectCompany: vi.fn().mockResolvedValue(undefined),
    status: "anonymous",
    ...overrides,
  };
  return render(
    <QueryClientProvider client={client}>
      <SessionContext.Provider value={session}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </SessionContext.Provider>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  it("valida os campos em português", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(
      await screen.findByText("Informe um e-mail válido."),
    ).toBeInTheDocument();
    expect(screen.getByText("Informe sua senha.")).toBeInTheDocument();
  });

  it("envia as credenciais sem persistir tokens no navegador", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue(profile);
    renderLogin({ login });
    await user.type(
      screen.getByLabelText("E-mail corporativo"),
      "teste@empresa.com.br",
    );
    await user.type(screen.getByLabelText("Senha"), "segredo-temporario");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(login).toHaveBeenCalledWith(
      "teste@empresa.com.br",
      "segredo-temporario",
    );
    expect(window.localStorage).toHaveLength(0);
    expect(window.sessionStorage).toHaveLength(0);
  });

  it("acessa o administrador local sem solicitar credenciais", async () => {
    const user = userEvent.setup();
    const developmentLogin = vi.fn().mockResolvedValue(profile);
    renderLogin({ developmentLogin });
    await user.click(
      await screen.findByRole("button", {
        name: "Acessar como administrador",
      }),
    );
    expect(developmentLogin).toHaveBeenCalledOnce();
  });

  it("exige credenciais administrativas antes de gerar link", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(
      screen.getByRole("button", { name: "Gerar link de acesso" }),
    );
    expect(
      screen.getByRole("dialog", {
        name: "Confirme sua identidade de administrador",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail do administrador")).toBeRequired();
    expect(screen.getByLabelText("Senha do administrador")).toBeRequired();
    expect(
      screen.queryByRole("button", { name: "Gerar token seguro" }),
    ).not.toBeInTheDocument();
  });
});

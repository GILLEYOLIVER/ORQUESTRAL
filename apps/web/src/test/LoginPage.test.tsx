import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LoginPage } from "../pages/LoginPage";

function renderLogin() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
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

  it("informa claramente que não existe autenticação simulada", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.type(
      screen.getByLabelText("E-mail corporativo"),
      "teste@empresa.com.br",
    );
    await user.type(screen.getByLabelText("Senha"), "segredo-temporario");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(
      await screen.findByText(/Nenhuma credencial foi enviada ou armazenada/),
    ).toBeInTheDocument();
    expect(window.localStorage).toHaveLength(0);
    expect(window.sessionStorage).toHaveLength(0);
  });
});

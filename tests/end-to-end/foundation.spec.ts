import { expect, test, type Page } from "@playwright/test";

async function accessDevelopmentAdmin(page: Page) {
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Acessar como administrador" })
    .click();

  await page.waitForURL(/\/(app|selecionar-empresa)$/);
  if (new URL(page.url()).pathname === "/selecionar-empresa") {
    await page
      .getByRole("button", { name: /Orkestral Desenvolvimento/ })
      .click();
  }
  await expect(page).toHaveURL(/\/app$/);
}

test("front-end e health checks estão acessíveis", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Automação empresarial/ }),
  ).toBeVisible();

  const health = await request.get("/health");
  expect(health.ok()).toBeTruthy();
  await expect
    .poll(async () => (await request.get("/ready")).status())
    .toBe(200);
});

test("administrador local entra sem credenciais, acessa o tenant e encerra a sessão", async ({
  page,
}) => {
  await accessDevelopmentAdmin(page);
  await expect(
    page.getByText("Orkestral Desenvolvimento", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Empresas" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Usuários" })).toBeVisible();
  await page.getByRole("link", { name: "Papéis" }).click();
  await expect(
    page.getByRole("heading", { name: "Papéis e permissões" }),
  ).toBeVisible();
  await expect(page.getByText("Proprietário", { exact: true })).toBeVisible();
  await expect(page.getByText("Membro", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/app");
  await expect(page).toHaveURL(/\/login$/);
});

test("clientes veem linguagem comercial na área de plano e consumo", async ({
  page,
}) => {
  await accessDevelopmentAdmin(page);

  await page.getByRole("link", { name: "Plano e consumo" }).click();
  await expect(page).toHaveURL(/\/app\/plano$/);
  await expect(
    page.getByRole("heading", { name: "Plano e consumo" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Catálogo comercial" }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/Fase\s+\d+/i);
});

test("administrador cria e exclui logicamente um agente", async ({ page }) => {
  const agentName = `Agente descartável ${Date.now()}`;
  await accessDevelopmentAdmin(page);
  await page.getByRole("link", { name: "Agentes" }).click();

  const sidebar = page.locator(".sidebar");
  await expect(sidebar).toHaveCSS("position", "sticky");
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect
    .poll(async () => Math.round((await sidebar.boundingBox())?.y ?? -1))
    .toBe(0);
  await page.evaluate(() => window.scrollTo(0, 0));

  const createAgentForm = page.locator("form").filter({
    has: page.getByRole("button", { name: "Criar agente" }),
  });
  await createAgentForm
    .getByRole("textbox", { name: "Nome", exact: true })
    .fill(agentName);
  await createAgentForm.getByRole("button", { name: "Criar agente" }).click();
  const createdAgent = page.getByRole("button", {
    name: new RegExp(agentName),
  });
  await expect(createdAgent).toBeVisible();
  await createdAgent.click();
  await expect(
    page.getByRole("heading", { name: agentName, exact: true }),
  ).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Excluir agente" }).click();
  await expect(createdAgent).toHaveCount(0);
});

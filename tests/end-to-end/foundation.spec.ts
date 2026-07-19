import { expect, test } from "@playwright/test";

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
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Acessar como administrador" })
    .click();

  await expect(page).toHaveURL(/\/app$/);
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
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Acessar como administrador" })
    .click();

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

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

test("administrador publica schema e opera registro no Orkestral Studio", async ({
  page,
}) => {
  const suffix = Date.now();
  const entityKey = `e2e_asset_${suffix}`;
  const entityLabel = `Ativo E2E ${suffix}`;
  const entityPlural = `Ativos E2E ${suffix}`;
  const recordName = `Registro temporário ${suffix}`;

  await accessDevelopmentAdmin(page);
  await page.getByRole("link", { name: "Orkestral Studio" }).click();
  await expect(
    page.getByRole("heading", { name: "Orkestral Studio" }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/Fase\s+\d+/i);

  await page.getByRole("button", { name: "Nova entidade" }).click();
  await page.getByLabel("Chave técnica").fill(entityKey);
  await page.getByLabel("Nome no singular").fill(entityLabel);
  await page.getByLabel("Nome no plural").fill(entityPlural);
  await page.getByLabel("Chave", { exact: true }).fill("name");
  await page.getByLabel("Nome", { exact: true }).fill("Nome");
  await page.getByLabel("Obrigatório", { exact: true }).check();
  await page.getByRole("button", { name: "Salvar rascunho" }).click();

  await expect(page.getByRole("heading", { name: entityPlural })).toBeVisible();
  await page.getByRole("button", { name: "Validar versão" }).click();
  await expect(
    page.getByRole("button", { name: "Publicar versão" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Publicar versão" }).click();

  await expect(
    page.getByText("Dados publicados", { exact: true }),
  ).toBeVisible();
  await page.getByLabel(/^Nome/).fill(recordName);
  await page.getByRole("button", { name: `Criar ${entityLabel}` }).click();
  const recordRow = page.getByRole("row").filter({ hasText: recordName });
  await expect(recordRow).toBeVisible();
  await recordRow.getByRole("button", { name: "Excluir" }).click();
  await expect(recordRow).toHaveCount(0);
});

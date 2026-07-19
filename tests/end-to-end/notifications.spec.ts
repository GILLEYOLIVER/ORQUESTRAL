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

test("administrador acompanha notificações, aprovações e preferências", async ({
  page,
}) => {
  await accessDevelopmentAdmin(page);

  await page.getByRole("link", { name: "Central de atenção" }).click();

  await expect(page).toHaveURL(/\/app\/notificacoes$/);
  await expect(
    page.getByRole("heading", { name: "Decisões humanas no ritmo certo." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Como você quer ser avisado" }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/Fase\s+\d+/i);
});

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

async function removeAgentIfPresent(page: Page, name: string | RegExp) {
  const agent = page.getByRole("button", { name });
  const count = await agent.count();
  if (count === 0) return;
  await agent.first().click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Excluir agente" }).click();
  await expect(agent).toHaveCount(count - 1);
}

test("administrador publica e simula política de aprovação de agente", async ({
  page,
}) => {
  const suffix = Date.now();
  const agentName = `Agente de política ${suffix}`;
  const policyName = `Aprovação segura ${suffix}`;
  const policyKey = `approval.safe.${suffix}`;

  await accessDevelopmentAdmin(page);
  await page.getByRole("link", { name: "Agentes" }).click();
  while (
    (await page.getByRole("button", { name: /Agente de política/ }).count()) > 0
  ) {
    await removeAgentIfPresent(page, /Agente de política/);
  }
  try {
    await page
      .getByRole("textbox", { name: "Nome", exact: true })
      .fill(agentName);
    await page.getByRole("button", { name: "Criar agente" }).click();
    await page.getByRole("button", { name: new RegExp(agentName) }).click();

    const policyCard = page
      .getByRole("heading", { name: "Políticas de aprovação" })
      .locator("..")
      .locator("..");
    await expect(policyCard).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Governança da memória" }),
    ).toBeVisible();
    await policyCard
      .getByRole("textbox", { name: "Nome da política" })
      .fill(policyName);
    await policyCard
      .getByRole("textbox", { name: "Chave da política" })
      .fill(policyKey);
    await policyCard
      .getByLabel("Efeito da política")
      .selectOption("require_approval");
    await policyCard
      .getByLabel("Ferramenta da política")
      .selectOption("orkestral.company.summary");
    await expect(policyCard.getByLabel("Aprovador principal")).toBeVisible();
    await expect(
      policyCard.getByRole("spinbutton", {
        name: "Validade da aprovação (minutos)",
      }),
    ).toHaveValue("60");
    await expect(policyCard.getByLabel("Início da vigência")).toBeVisible();
    await expect(policyCard.getByLabel("Fim da vigência")).toBeVisible();
    await expect(policyCard.getByLabel("Aprovador substituto")).toBeDisabled();
    await policyCard.getByRole("button", { name: "Adicionar etapa" }).click();
    await expect(
      policyCard.getByRole("textbox", { name: "Nome da etapa 1" }),
    ).toHaveValue("Etapa 1");
    await policyCard
      .getByLabel("Participantes da etapa 1")
      .selectOption({ index: 0 });
    await policyCard.getByRole("button", { name: "Criar rascunho" }).click();

    const policyRow = policyCard.locator(".agent-policy-row", {
      hasText: policyName,
    });
    await expect(policyRow.getByText("Rascunho")).toBeVisible();
    await expect(policyRow.getByText(/1 etapa/)).toBeVisible();
    await policyRow.getByRole("button", { name: "Publicar" }).click();
    await expect(policyRow.getByText("Publicada")).toBeVisible();

    await policyCard.getByRole("button", { name: "Simular decisão" }).click();
    await expect(
      policyCard.getByText("Exige aprovação", { exact: true }),
    ).toBeVisible();
  } finally {
    await removeAgentIfPresent(page, new RegExp(agentName));
  }
});

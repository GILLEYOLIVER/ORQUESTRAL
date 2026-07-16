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

import { expect, test } from "@playwright/test";

test("renders synthetic analysis and connects to the M0 backend", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "合成科技样本" })).toBeVisible();
  await expect(page.getByText("SYNTHETIC_MOCK").first()).toBeVisible();
  await expect(page.getByText("PAPER_TRADE_ONLY")).toBeVisible();
  await expect(page.getByText(/仅用于界面与契约验证/)).toBeVisible();
  await expect(page.getByText("后端在线 · v0.1.0")).toBeVisible();
});

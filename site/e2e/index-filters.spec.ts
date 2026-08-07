import { test, expect } from "@playwright/test";
import { gotoIndex } from "./helpers";

test.describe("Index filters", () => {
  test("category chip selection updates active state", async ({ page }) => {
    await gotoIndex(page);

    const mammalsChip = page.getByRole("radio", { name: /^Mammals/ });
    await mammalsChip.click();

    await expect(mammalsChip).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("radio", { name: /^All/ })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    const visibleCards = page.locator(".card:not([hidden])");
    await expect(visibleCards.first()).toBeVisible();
    const count = await visibleCards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(count, 3); i++) {
      await expect(visibleCards.nth(i)).toHaveAttribute("data-category", "Mammals");
    }
  });

  test("category chip keyboard navigation updates selection", async ({ page }) => {
    await gotoIndex(page);

    const allChip = page.getByRole("radio", { name: /^All/ });
    await allChip.focus();
    await page.keyboard.press("ArrowRight");

    const birdsChip = page.getByRole("radio", { name: /^Birds/ });
    await expect(birdsChip).toHaveAttribute("aria-checked", "true");
    await expect(birdsChip).toBeFocused();

    const visibleCards = page.locator(".card:not([hidden])");
    await expect(visibleCards.first()).toHaveAttribute("data-category", "Birds");
  });

  test("search filter updates filter status announcement", async ({ page }) => {
    await gotoIndex(page);

    await page.getByLabel("Search").fill("wolf");

    const filterStatus = page.locator("#filter-status");
    await expect(filterStatus).not.toBeEmpty({ timeout: 5_000 });
    await expect(filterStatus).toContainText(/Showing \d+ of \d+ recordings/);
    await expect(filterStatus).toContainText("Search: wolf");
  });
});

import { test, expect } from "@playwright/test";
import { gotoAbout } from "./helpers";

test.describe("About page", () => {
  test("spectrogram example link opens the featured clip page", async ({ page }) => {
    await gotoAbout(page);

    await page
      .getByRole("link", {
        name: /Fox Sparrow Song With Thunder and Swainson's Thrush \(seconds 18–29\)/,
      })
      .click();

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Fox Sparrow Song With Thunder and Swainson's Thrush",
    );
  });

  test("Denali tree fall link opens the featured clip page", async ({ page }) => {
    await gotoAbout(page);

    await page.getByRole("link", { name: /this Denali monitoring site recording/ }).click();

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("If a Tree Falls");
  });
});

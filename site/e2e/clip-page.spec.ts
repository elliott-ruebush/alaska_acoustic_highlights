import { test, expect } from "@playwright/test";
import { CLIP_WITH_SITE_PHOTO, gotoClip, mockClipAudio } from "./helpers";

test.describe("Clip page", () => {
  test("skip link moves focus into the player region", async ({ page }) => {
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);

    const skipLink = page.getByRole("link", { name: "Skip to player controls" });
    await expect(skipLink).toHaveAttribute("href", "#audio-player");

    await skipLink.focus();
    await page.keyboard.press("Enter");

    await expect(page.locator("#audio-player")).toBeFocused();
    await expect(page.locator("#audio-player")).toBeVisible();
  });

  test("Space toggles play when focus is in the player region", async ({ page }) => {
    await mockClipAudio(page);
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);

    await page.locator("#audio-player").focus();
    await page.keyboard.press("Space");

    await expect(page.getByRole("button", { name: "Pause" })).toBeVisible({ timeout: 30_000 });
  });

  test("seek slider becomes enabled after player loads", async ({ page }) => {
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);

    const seekSlider = page.getByRole("slider", { name: "Playback position" });
    await expect(seekSlider).toBeDisabled();

    await page.getByRole("button", { name: "Play" }).click();
    await expect(seekSlider).toBeEnabled({ timeout: 30_000 });
  });
});

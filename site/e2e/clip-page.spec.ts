import { test, expect } from "@playwright/test";
import { CLIP_WITH_SITE_PHOTO, gotoClip } from "./helpers";

test.describe("Clip page", () => {
  test("skip link targets the audio player", async ({ page }) => {
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);

    const skipLink = page.getByRole("link", { name: "Skip to audio player" });
    await expect(skipLink).toHaveAttribute("href", "#audio-player");
    await expect(page.locator("#audio-player")).toBeVisible();
  });

  test("seek slider becomes enabled after player loads", async ({ page }) => {
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);

    const seekSlider = page.getByRole("slider", { name: "Playback position" });
    await expect(seekSlider).toBeDisabled();

    await page.getByRole("button", { name: "Play" }).click();
    await expect(seekSlider).toBeEnabled({ timeout: 30_000 });
  });
});

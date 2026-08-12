import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/** Clip with a site photo for dialog and player tests. */
export const CLIP_WITH_SITE_PHOTO = "denabicr_20130809_020959";

/** Minimal valid MP3 for mocking audio in CI when highlights assets are absent. */
const MINIMAL_MP3 = Buffer.from(
  "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRwmHAAAAAAD/+1DEAAAGAAGn9AAAIAAANIAAAAQAAANIAAAAA",
  "base64",
);

/**
 * Navigate using relative paths so Playwright respects Astro base path.
 * Leading-slash URLs resolve to the server root, not baseURL.
 */
export async function gotoIndex(page: Page) {
  await page.goto("./");
}

export async function gotoAbout(page: Page) {
  await page.goto("./about/");
}

export async function gotoClip(page: Page, clipId: string) {
  await page.goto(`./clips/${clipId}/`);
}

/** Intercept clip audio only when the real asset is missing (e.g. CI without highlights). */
export async function mockClipAudio(page: Page) {
  await page.route("**/highlights/audio/**", async (route) => {
    const response = await route.fetch();
    if (response.ok()) {
      await route.fulfill({ response });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "audio/mpeg",
      body: MINIMAL_MP3,
    });
  });
}

/**
 * Run WCAG 2.x accessibility scan.
 * Card spectrogram thumbnails use alt="" (decorative); exclude them from image-alt
 * checks since the link name comes from the card heading.
 */
export async function runAxeScan(page: Page) {
  return new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("#recordings-grid .card img")
    .analyze();
}

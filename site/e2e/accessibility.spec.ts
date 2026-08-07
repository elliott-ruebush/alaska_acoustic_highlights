import { test, expect } from "@playwright/test";
import {
  CLIP_WITH_SITE_PHOTO,
  gotoAbout,
  gotoClip,
  gotoIndex,
  runAxeScan,
} from "./helpers";

test.describe("Accessibility", () => {
  test("index page has no axe violations", async ({ page }) => {
    await gotoIndex(page);
    const results = await runAxeScan(page);
    expect(results.violations).toEqual([]);
  });

  test("about page has no axe violations", async ({ page }) => {
    await gotoAbout(page);
    const results = await runAxeScan(page);
    expect(results.violations).toEqual([]);
  });

  test("clip page has no axe violations", async ({ page }) => {
    await gotoClip(page, CLIP_WITH_SITE_PHOTO);
    const results = await runAxeScan(page);
    expect(results.violations).toEqual([]);
  });
});

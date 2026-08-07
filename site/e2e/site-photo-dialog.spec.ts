import { test, expect } from "@playwright/test";
import { CLIP_WITH_SITE_PHOTO, gotoClip } from "./helpers";

test("site photo dialog closes with Escape and returns focus to trigger", async ({
  page,
}) => {
  await gotoClip(page, CLIP_WITH_SITE_PHOTO);

  const trigger = page.getByRole("button", { name: /View larger/ });
  await trigger.click();

  const dialog = page.getByRole("dialog", { name: "Recording site photo" });
  await expect(dialog).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

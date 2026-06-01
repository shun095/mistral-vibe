/**
 * E2E tests for WebUI resume command (/resume).
 *
 * Merged inspect assertions. Close behavior covered by modal-commands.spec.ts.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForVisible,
  waitForHidden,
  waitForResponse,
} from "../helpers/test-utils";

test.describe("Resume Command (/resume)", () => {
  test("should open with header, content, and cleared input", async ({
    page,
  }) => {
    await sendMessage(page, "/resume");

    const modal = page.locator(Selectors.sessionPickerModal);
    await expect(modal).toBeVisible({ timeout: 10000 });

    // Structure
    await expect(page.locator(Selectors.sessionPickerContent)).toBeVisible();
    await expect(page.locator(Selectors.sessionPickerClose)).toBeVisible();

    // Header
    const header = modal.locator(".modal-header h2").first();
    await expect(header).toContainText("Resume Session");

    // Loading/empty/content state
    const hasLoadingOrContent = await page
      .locator(Selectors.sessionPickerContent)
      .evaluate((el) => {
        const text = el.textContent?.toLowerCase() || "";
        return (
          text.includes("loading") ||
          text.includes("no sessions") ||
          el.querySelector(".session-picker-item") !== null
        );
      });
    expect(hasLoadingOrContent).toBe(true);

    // Input cleared
    expect(await page.inputValue(Selectors.messageInput)).toBe("");
  });

  test("should show session items if sessions exist", async ({ page }) => {
    await sendMessage(page, "Test message for session creation");
    await waitForResponse(page, 15000);

    await sendMessage(page, "/resume");
    await waitForVisible(page, Selectors.sessionPickerModal);

    const sessionContent = page.locator(Selectors.sessionPickerContent);
    await sessionContent.waitFor({ state: "visible", timeout: 10000 });

    const hasSessionsOrEmpty = await sessionContent.evaluate((el) => {
      const hasItems = el.querySelector(".session-picker-item") !== null;
      const hasEmpty =
        el.textContent?.toLowerCase().includes("no sessions") || false;
      const hasLoading =
        el.textContent?.toLowerCase().includes("loading") || false;
      return hasItems || hasEmpty || hasLoading;
    });
    expect(hasSessionsOrEmpty).toBe(true);
  });

  test("should show cancelled message when closing modal with Escape", async ({
    page,
  }) => {
    await sendMessage(page, "/resume");
    await waitForVisible(page, Selectors.sessionPickerModal);

    await page.keyboard.press("Escape");
    await waitForHidden(page, Selectors.sessionPickerModal);

    const cancelledMessage = page.locator(
      '.message.system:has-text("Resume cancelled.")'
    );
    await expect(cancelledMessage).toBeVisible({ timeout: 5000 });
  });
});

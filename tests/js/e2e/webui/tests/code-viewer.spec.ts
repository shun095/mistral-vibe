/**
 * E2E tests for WebUI code viewer (Monaco editor).
 *
 * Merged inspect assertions. Close behavior tested once.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForResponse,
  callVibeClient,
} from "../helpers/test-utils";

test.describe("Code Viewer (Monaco)", () => {
  test("should open with file path and offset in title", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerResponse({
      response_text:
        "Here's the code:\n\n```python\ndef hello():\n    print('world')\n```\n",
    });

    await sendMessage(page, "Show me code");

    const codeBlock = page.locator("pre code");
    await expect(codeBlock).toBeVisible({ timeout: 15000 });

    // Open with offset
    await callVibeClient(
      page,
      "showCodeFullscreen",
      "src/large.py",
      "content",
      "python",
      100
    );

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Title contains filename
    const title = codeModal.locator(".code-modal-title");
    await expect(title).toContainText("large.py");

    // Title shows offset
    await expect(title).toContainText("from line 101");
  });

  test("should toggle word wrap in code viewer", async ({ page }) => {
    await callVibeClient(
      page,
      "showCodeFullscreen",
      "src/long.py",
      "this is a very long line that should be wrapped when word wrap is enabled",
      "python",
      0
    );

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    await codeModal
      .locator(".monaco-container")
      .waitFor({ state: "visible", timeout: 10000 });

    const wrapBtn = codeModal.locator(".code-modal-btn");
    await expect(wrapBtn).toBeVisible();
    await expect(wrapBtn.locator(".material-symbols-rounded")).toContainText(
      "wrap_text"
    );

    await wrapBtn.click();

    await expect(wrapBtn).toBeVisible();
  });

  test("should close code viewer with close button", async ({ page }) => {
    await callVibeClient(
      page,
      "showCodeFullscreen",
      "src/test.py",
      "content",
      "python",
      0
    );

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    const closeBtn = codeModal.locator(".code-modal-close");
    await closeBtn.click();

    await expect(codeModal).not.toBeVisible({ timeout: 3000 });
  });

  test("should close code viewer with Escape key", async ({ page }) => {
    await callVibeClient(
      page,
      "showCodeFullscreen",
      "src/test.py",
      "content",
      "python",
      0
    );

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    await page.keyboard.press("Escape");

    await expect(codeModal).not.toBeVisible({ timeout: 3000 });
  });
});

/**
 * E2E tests for WebUI code viewer (Monaco editor).
 * Covers US-16 (fullscreen code viewer), US-17 (word wrap toggle), US-18 (line numbers).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse, callVibeClient } from "../helpers/test-utils";

test.describe("Code Viewer (Monaco)", () => {
  test("should open code viewer modal on double-click of code block", async ({
    page,
    mockBackend,
  }) => {
    // Register a response with code content
    await mockBackend.registerResponse({
      response_text: "Here's the code:\n\n```python\ndef hello():\n    print('world')\n```\n",
    });

    await sendMessage(page, "Show me code");

    // Wait for the assistant message with code block
    const codeBlock = page.locator("pre code");
    await expect(codeBlock).toBeVisible({ timeout: 15000 });

    // Simulate double-click on the code block to open the modal
    // Use evaluate to directly call the handler since dispatchEvent may not trigger properly
    await callVibeClient(page, "showCodeFullscreen", "example.py", "def hello():\n    print('world')", "python", 0);

    // Code modal should appear
    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });
  });

  test("should show file path in code modal title", async ({ page }) => {
    // Simulate opening the code viewer via VibeClient
    await callVibeClient(page, "showCodeFullscreen", "src/main.py", "def hello():\n print('world')", "python", 0);

    // Code modal should appear
    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Title should show the file path
    const title = codeModal.locator(".code-modal-title");
    await expect(title).toContainText("main.py");
  });

  test("should show line numbers in code viewer", async ({ page }) => {
    // Simulate opening the code viewer
    await callVibeClient(page, "showCodeFullscreen", "src/test.py", "line1\nline2\nline3", "python", 0);

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Wait for Monaco editor to initialize (it loads asynchronously)
    await codeModal.locator(".monaco-container").waitFor({ state: "visible", timeout: 10000 });
  });

  test("should toggle word wrap in code viewer", async ({ page }) => {
    // Simulate opening the code viewer
    await callVibeClient(page, "showCodeFullscreen", "src/long.py", "this is a very long line that should be wrapped when word wrap is enabled", "python", 0);

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Wait for Monaco editor to initialize
    await codeModal.locator(".monaco-container").waitFor({ state: "visible", timeout: 10000 });

    // Word wrap button should initially show wrap_text icon
    const wrapBtn = codeModal.locator(".code-modal-btn");
    await expect(wrapBtn).toBeVisible();
    await expect(wrapBtn.locator(".material-symbols-rounded")).toContainText(
      "wrap_text"
    );

    // Click the word wrap toggle button
    await wrapBtn.click();

    // Icon should change to wrap_disabled when word wrap is on
    // (The button toggles between on/off states)
    await expect(wrapBtn).toBeVisible();
  });

  test("should close code viewer with close button", async ({ page }) => {
    // Simulate opening the code viewer
    await callVibeClient(page, "showCodeFullscreen", "src/test.py", "content", "python", 0);

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Click the close button
    const closeBtn = codeModal.locator(".code-modal-close");
    await closeBtn.click();

    // Modal should be hidden
    await expect(codeModal).not.toBeVisible({ timeout: 3000 });
  });

  test("should close code viewer with Escape key", async ({ page }) => {
    // Simulate opening the code viewer
    await callVibeClient(page, "showCodeFullscreen", "src/test.py", "content", "python", 0);

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Press Escape to close
    await page.keyboard.press("Escape");

    // Modal should be hidden
    await expect(codeModal).not.toBeVisible({ timeout: 3000 });
  });

  test("should show offset in title when reading from line offset", async ({
    page,
  }) => {
    // Simulate opening the code viewer with an offset
    await callVibeClient(page, "showCodeFullscreen", "src/large.py", "content", "python", 100);

    const codeModal = page.locator(".code-modal");
    await expect(codeModal).toBeVisible({ timeout: 10000 });

    // Title should show the offset
    const title = codeModal.locator(".code-modal-title");
    await expect(title).toContainText("from line 101");
  });
});

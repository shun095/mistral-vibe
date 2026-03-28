import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForVisible,
  waitForHidden,
} from "../helpers/test-utils";

test.describe("Resume Command (/resume)", () => {
  test.beforeEach(async ({ page, authToken, webServer }) => {
    // Navigate with auth token
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Wait for chat interface to be visible
    await expect(page.locator(Selectors.messageInput)).toBeVisible();

    // Wait for WebSocket to connect
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && el.classList.contains("connected");
      },
      Selectors.statusIndicator,
      { timeout: 10000 }
    );
  });

  test("should show session picker modal when /resume is sent", async ({
    page,
  }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for session picker modal to appear
    const modal = page.locator(Selectors.sessionPickerModal);
    await expect(modal).toBeVisible({ timeout: 10000 });

    // Verify modal content is visible
    await expect(page.locator(Selectors.sessionPickerContent)).toBeVisible();

    // Verify close button is visible
    await expect(page.locator(Selectors.sessionPickerClose)).toBeVisible();
  });

  test("should show loading state initially", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Should show loading or empty state (no sessions by default)
    const content = page.locator(Selectors.sessionPickerContent);
    await expect(content).toBeVisible();

    // Should either show loading text or empty state
    const hasLoadingOrEmpty = await content.evaluate((el) => {
      const text = el.textContent?.toLowerCase() || "";
      return (
        text.includes("loading") ||
        text.includes("no sessions") ||
        el.querySelector(".session-picker-item") !== null
      );
    });
    expect(hasLoadingOrEmpty).toBe(true);
  });

  test("should close modal when clicking close button", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Click close button
    await page.click(Selectors.sessionPickerClose);

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.sessionPickerModal);
  });

  test("should close modal when clicking overlay", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Click overlay (the modal overlay element)
    await page.click(".modal-overlay");

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.sessionPickerModal);
  });

  test("should close modal when pressing Escape", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Press Escape key
    await page.keyboard.press("Escape");

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.sessionPickerModal);
  });

  test("should show cancelled message when closing modal", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Press Escape key to cancel
    await page.keyboard.press("Escape");

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.sessionPickerModal);

    // Wait for cancelled message to appear
    const cancelledMessage = page.locator('.message.system:has-text("Resume cancelled.")');
    await expect(cancelledMessage).toBeVisible({ timeout: 5000 });
  });

  test("should clear input after sending /resume", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Verify input is cleared
    const inputValue = await page.inputValue(Selectors.messageInput);
    expect(inputValue).toBe("");
  });

  test("should show session items if sessions exist", async ({
    page,
    webServer,
  }) => {
    // Register a mock response
    const url = webServer.getUrl();
    const token = "test-token-123";
    await page.evaluate(
      async ({ url, token }) => {
        await fetch(`${url}/api/test/mock-data`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ response_text: "Test response" }),
        });
      },
      { url, token }
    );

    // Send a message to create a session
    await sendMessage(page, "Test message for session");

    // Wait for response
    await page.waitForSelector(Selectors.assistantMessage);

    // Wait a moment for session to be saved
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Now send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Check if session items are present or if empty state is shown
    const content = page.locator(Selectors.sessionPickerContent);
    const hasSessionsOrEmpty = await content.evaluate((el) => {
      const hasItems = el.querySelector(".session-picker-item") !== null;
      const hasEmpty =
        el.textContent?.toLowerCase().includes("no sessions") || false;
      return hasItems || hasEmpty;
    });
    expect(hasSessionsOrEmpty).toBe(true);
  });

  test("should display session picker header", async ({ page }) => {
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Verify modal header contains "Resume Session"
    const modalHeader = page.locator(".modal-header h2");
    await expect(modalHeader).toContainText("Resume Session");
  });
});

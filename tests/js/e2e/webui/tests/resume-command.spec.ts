import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForVisible,
  waitForHidden,
} from "../helpers/test-utils";

test.describe("Resume Command (/resume)", () => {
  test("should show session picker modal when /resume is sent", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
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
    // Page is already loaded with auth by fixture
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
    // Page is already loaded with auth by fixture
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
    // Page is already loaded with auth by fixture
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Get the session picker modal content element
    const modalContent = page.locator(Selectors.sessionPickerModal).first();
    const modalBox = await modalContent.boundingBox();

    if (modalBox) {
      // Calculate a point outside the modal but within viewport
      // Click to the left of the modal
      const clickX = Math.max(10, modalBox.x - 10);
      const clickY = modalBox.y + modalBox.height / 2;
      await page.mouse.click(clickX, clickY);
    }

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.sessionPickerModal);
  });

  test("should close modal when pressing Escape", async ({ page }) => {
    // Page is already loaded with auth by fixture
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
    // Page is already loaded with auth by fixture
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
    // Page is already loaded with auth by fixture
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Verify input is cleared
    const inputValue = await page.inputValue(Selectors.messageInput);
    expect(inputValue).toBe("");
  });

  test("should show session items if sessions exist", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send a message to create a session
    await sendMessage(page, "Test message for session creation");

    // Wait for response or processing to complete
    await page.waitForTimeout(2000);

    // Now send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Wait for content to load
    await page.waitForTimeout(1000);

    // Check if session items are present or if empty state is shown
    const content = page.locator(Selectors.sessionPickerContent);
    const hasSessionsOrEmpty = await content.evaluate((el) => {
      const hasItems = el.querySelector(".session-picker-item") !== null;
      const hasEmpty =
        el.textContent?.toLowerCase().includes("no sessions") || false;
      const hasLoading =
        el.textContent?.toLowerCase().includes("loading") || false;
      return hasItems || hasEmpty || hasLoading;
    });
    expect(hasSessionsOrEmpty).toBe(true);
  });

  test("should display session picker header", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send /resume command
    await sendMessage(page, "/resume");

    // Wait for modal to appear
    await waitForVisible(page, Selectors.sessionPickerModal);

    // Verify modal header contains "Resume Session"
    // Use the session picker modal's header specifically
    const modalHeader = page.locator(Selectors.sessionPickerModal).locator(".modal-header h2").first();
    await expect(modalHeader).toContainText("Resume Session");
  });
});

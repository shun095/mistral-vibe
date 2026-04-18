/**
 * Common test utilities for WebUI E2E tests.
 */

import { Page, Locator } from "@playwright/test";

/**
 * Common CSS selectors for WebUI elements.
 */
export const Selectors = {
  // Status indicator
  statusIndicator: "#status-dot",
  contextProgress: "#context-progress",

  // Chat interface
  messageInput: "#message-input",
  sendButton: "#send-btn",
  messageContainer: "#messages",
  userMessage: ".message.user",
  assistantMessage: ".message.assistant",
  bashCommand: ".message.bash-command",
  systemMessage: ".message.system",

  // Tool approval
  approvalPopup: ".approval-popup",

  // Loading states
  processingIndicator: "#processing-indicator",

  // Image attachment
  attachImageBtn: "#attach-image-btn",
  imagePreviewContainer: "#image-preview-container",

  // Session picker
  sessionPickerModal: "#session-picker-modal",
  sessionPickerContent: "#session-picker-content",
  sessionPickerClose: "#session-picker-close",
  sessionPickerItem: ".session-picker-item",

  // Prompt history
  promptHistoryBtn: "#prompt-history-btn",
  promptHistoryModal: "#prompt-history-modal",
  promptHistoryContent: "#prompt-history-content",
  promptHistoryClose: "#prompt-history-close",
  promptHistorySearch: "#prompt-history-search",
  promptHistoryItem: ".prompt-history-item",

  // Toggle all cards
  toggleCardsBtn: "#toggle-cards-btn",

  // Interrupt/Stop button
  interruptBtn: "#interrupt-btn",

  // Logout button
  logoutBtn: "#logout-btn",

  // Theme toggle
  themeToggle: "#theme-toggle",
};

/**
 * Wait for element to be visible.
 */
export async function waitForVisible(
  page: Page,
  selector: string,
  timeout: number = 10000
): Promise<Locator> {
  const locator = page.locator(selector);
  await locator.waitFor({ state: "visible", timeout });
  return locator;
}

/**
 * Wait for element to be hidden.
 */
export async function waitForHidden(
  page: Page,
  selector: string,
  timeout: number = 10000
): Promise<void> {
  const locator = page.locator(selector);
  await locator.waitFor({ state: "hidden", timeout });
}

/**
 * Send a message through the chat interface.
 */
export async function sendMessage(page: Page, message: string): Promise<void> {
  await page.fill(Selectors.messageInput, message);
  await page.click(Selectors.sendButton);
}

/**
 * Set the agent processing state via vibeClient.
 * Used by E2E tests that need to simulate processing state changes.
 */
export async function setProcessingState(page: Page, processing: boolean): Promise<void> {
  await page.evaluate((state: boolean) => {
    const vibeClient = (window as any).vibeClient;
    if (vibeClient && vibeClient.updateProcessingState) {
      vibeClient.updateProcessingState(state);
    }
  }, processing);
}

/**
 * Wait for assistant response.
 * Returns the most recent assistant message.
 */
export async function waitForResponse(
  page: Page,
  timeout: number = 15000
): Promise<Locator> {
  // Wait for a new assistant message to appear
  const locator = page.locator(Selectors.assistantMessage).last();
  await locator.waitFor({ state: "visible", timeout });
  return locator;
}

/**
 * Get the last assistant message text.
 */
export async function getLastMessageText(page: Page): Promise<string> {
  const lastMessage = page.locator(Selectors.assistantMessage).last();
  const text = await lastMessage.textContent();
  return text ?? "";
}

/**
 * Wait for connected status.
 */
export async function waitForConnected(
  page: Page,
  timeout: number = 10000
): Promise<void> {
  await page.waitForFunction(
    (selector) => {
      const el = document.querySelector(selector);
      return el && el.classList.contains("connected");
    },
    Selectors.statusIndicator,
    { timeout }
  );
}

/**
 * Clear conversation history using /clear command.
 */
export async function clearHistory(page: Page): Promise<void> {
  await sendMessage(page, "/clear");
  // Wait for the clear command to be processed
  await waitForResponse(page, 5000);
}

/**
 * Reset test state by interrupting any ongoing processing and reloading the page.
 * This ensures clean state between tests.
 */
export async function resetTestState(
  page: Page,
  webServerUrl: string
): Promise<void> {
  // Check if page is closed before trying to reset
  if (page.isClosed()) {
    return;
  }

  try {
    // CRITICAL: Click interrupt button FIRST if processing is ongoing
    // This stops the processing and should close any approval popup
    const interruptBtn = page.locator(Selectors.interruptBtn);
    const isInterruptVisible = await interruptBtn.isVisible().catch(() => false);

    if (isInterruptVisible) {
      console.log("Reset: interrupt button visible, clicking it to stop processing...");
      try {
        await interruptBtn.click({ timeout: 3000 });
        console.log("Reset: clicked interrupt button");
        // Wait for processing to stop and popup to close
        await page.waitForTimeout(1000);
      } catch {
        console.log("Reset: failed to click interrupt button");
      }
    }

    // After interrupting, check if approval popup is still visible and close it
    const approvalPopup = page.locator(Selectors.approvalPopup);
    const isApprovalVisible = await approvalPopup.isVisible().catch(() => false);

    if (isApprovalVisible) {
      console.log("Reset: approval popup still visible after interrupt, closing it...");
      // Try No button first (most reliable way to dismiss)
      const noButton = approvalPopup.locator('.popup-btn.no:has-text("No")').first();
      try {
        await noButton.click({ timeout: 2000 });
        console.log("Reset: clicked No button on approval popup");
        await page.waitForTimeout(500);
      } catch {
        // Try close button
        const closeButton = approvalPopup.locator('.popup-close, .modal-close').first();
        try {
          await closeButton.click({ timeout: 2000 });
          console.log("Reset: clicked close button on approval popup");
          await page.waitForTimeout(500);
        } catch {
          console.log("Reset: could not close popup, will reload anyway");
        }
      }
    }

    // Just reload the page - don't use /clear as it consumes mock responses

    // Reload page - cookie-based auth will persist
    console.log("Reset: reloading page...");
    await page.goto(webServerUrl, {
      timeout: 10000,
      waitUntil: "domcontentloaded"
    });
  } catch (navigateError) {
    console.warn("Reset: navigation failed:", String(navigateError));
    return;
  }

  // Check if page is still open before waiting
  if (page.isClosed()) {
    return;
  }

  // Wait for chat interface to be visible
  try {
    await page.locator(Selectors.messageInput).waitFor({ state: "visible", timeout: 8000 });

    // Wait for WebSocket to connect
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && el.classList.contains("connected");
      },
      Selectors.statusIndicator,
      { timeout: 8000 }
    );

    // Wait for message input to be enabled (not disabled)
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && !el.hasAttribute("disabled");
      },
      Selectors.messageInput,
      { timeout: 8000 }
    );

    console.log("Reset: page ready after reload");
  } catch (error) {
    // Log but don't fail - the next test's page fixture setup will handle readiness
    console.warn("Reset: page readiness check failed:", String(error));
  }
}

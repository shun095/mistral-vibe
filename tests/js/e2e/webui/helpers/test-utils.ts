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

  // Session picker
  sessionPickerModal: "#session-picker-modal",
  sessionPickerContent: "#session-picker-content",
  sessionPickerClose: "#session-picker-close",
  sessionPickerItem: ".session-picker-item",
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

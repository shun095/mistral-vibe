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

  // Prompt history
  promptHistoryBtn: "#prompt-history-btn",
  promptHistoryModal: "#prompt-history-modal",
  promptHistoryContent: "#prompt-history-content",
  promptHistoryClose: "#prompt-history-close",
  promptHistorySearch: "#prompt-history-search",
  promptHistoryItem: ".prompt-history-item",
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

/**
 * Clear conversation history using /clear command.
 */
export async function clearHistory(page: Page): Promise<void> {
  await sendMessage(page, "/clear");
  // Wait for the clear command to be processed
  await waitForResponse(page, 5000);
}

/**
 * Reset test state by clearing history and reloading the page.
 * This is faster than restarting the server.
 */
export async function resetTestState(
  page: Page,
  webServerUrl: string,
  authToken: string
): Promise<void> {
  // Check if page is closed before trying to reset
  if (page.isClosed()) {
    return;
  }

  // Skip clearing history in teardown - just reload to get fresh state
  // This speeds up teardown significantly

  // Reload page with auth token to get fresh state
  try {
    await page.goto(`${webServerUrl}/?token=${authToken}`, { timeout: 5000 });
  } catch {
    // Ignore navigation errors in teardown
    return;
  }

  // Check if page is still open before waiting
  if (page.isClosed()) {
    return;
  }

  // Wait for chat interface to be visible with short timeout
  try {
    await page.locator(Selectors.messageInput).waitFor({ state: "visible", timeout: 5000 });
  } catch {
    // Ignore if page doesn't load in time - next test will handle it
  }

  // Skip waiting for WebSocket connection to speed up test teardown
  // The next test will wait for WebSocket connection in its setup
}

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  setProcessingState,
  waitForResponse,
} from "../helpers/test-utils";

test.describe("Basic Chat Flow", () => {
  test("should hide interrupt button when agent is idle", async ({ page }) => {
    // Interrupt button should not be visible when idle
    const interruptBtn = page.locator(Selectors.interruptBtn);
    await expect(interruptBtn).not.toBeVisible();
  });

  test("should show interrupt button when agent is processing", async ({
    page,
  }) => {
    await setProcessingState(page, true);

    // Interrupt button should be visible during processing
    const interruptBtn = page.locator(Selectors.interruptBtn);
    await expect(interruptBtn).toBeVisible({ timeout: 5000 });

    // Send button should be hidden during processing
    const sendBtn = page.locator(Selectors.sendButton);
    await expect(sendBtn).not.toBeVisible({ timeout: 5000 });

    await setProcessingState(page, false);
  });

  test("should request interrupt when interrupt button is clicked", async ({
    page,
  }) => {
    await setProcessingState(page, true);

    // Click the interrupt button
    const interruptBtn = page.locator(Selectors.interruptBtn);
    await expect(interruptBtn).toBeVisible({ timeout: 5000 });
    await interruptBtn.click();

    // Verify interrupt was requested (system message appears)
    const systemMsg = page.locator(Selectors.systemMessage).last();
    await expect(systemMsg).toHaveText(/Interrupt requested/i, {
      timeout: 5000,
    });

    await setProcessingState(page, false);
  });
  test("should display the chat interface", async ({ page }) => {
    await expect(page.locator(Selectors.messageContainer)).toBeVisible();
    await expect(page.locator(Selectors.messageInput)).toBeVisible();
    await expect(page.locator(Selectors.messageInput)).toBeEnabled();
  });

  test("should send a message and receive a response", async ({
    page,
    mockBackend,
  }) => {
    // Register mock response BEFORE sending message
    await mockBackend.registerResponse({
      response_text: "This is a test response!",
    });

    // Send a message
    await sendMessage(page, "Hello");

    // Wait for and verify response (use last() to get the most recent message)
    const response = page.locator(Selectors.assistantMessage).last();
    await expect(response).toBeVisible({ timeout: 15000 });
    await expect(response).toContainText("This is a test response!");
  });

  test("should handle multiple messages in sequence", async ({
    page,
    mockBackend,
  }) => {
    // Register multiple mock responses
    await mockBackend.registerResponse({
      response_text: "First response",
    });
    await mockBackend.registerResponse({
      response_text: "Second response",
    });
    await mockBackend.registerResponse({
      response_text: "Third response",
    });

    // Send first message
    await sendMessage(page, "Message 1");
    let response = await waitForResponse(page);
    await expect(response).toContainText("First response");

    // Send second message
    await sendMessage(page, "Message 2");
    response = await waitForResponse(page);
    await expect(response).toContainText("Second response");

    // Send third message
    await sendMessage(page, "Message 3");
    response = await waitForResponse(page);
    await expect(response).toContainText("Third response");
  });

  test("should display user messages", async ({ page }) => {
    await sendMessage(page, "Test message from user");

    // Verify user message is displayed
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("Test message from user");
  });
});

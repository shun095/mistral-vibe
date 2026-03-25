import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForResponse,
} from "../helpers/test-utils";

test.describe("Basic Chat Flow", () => {
  test.beforeEach(async ({ page, authToken, webServer }) => {
    // Navigate with auth token
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Wait for chat interface to be visible
    await expect(page.locator(Selectors.messageInput)).toBeVisible();

    // Wait for WebSocket to connect (status should show "Connected")
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && el.textContent === "Connected";
      },
      "#status",
      { timeout: 10000 }
    );
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

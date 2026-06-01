/**
 * E2E tests for message history persistence.
 * Covers US-12: View full message history including past tool calls and results.
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForConnected } from "../helpers/test-utils";

test.describe("Message History Persistence", () => {
  test("should replay messages after page reload", async ({
    page,
    mockBackend,
  }) => {
    // Register mock response
    await mockBackend.registerResponse({
      response_text: "History test response",
    });

    // Send a message
    await sendMessage(page, "History test message");

    // Wait for assistant response
    const assistantMsg = page.locator(Selectors.assistantMessage).last();
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });
    await expect(assistantMsg).toContainText("History test response");

    // Verify user message is present
    const userMsg = page.locator(Selectors.userMessage).last();
    await expect(userMsg).toContainText("History test message");

    // Reload the page
    await page.reload({ waitUntil: "load" });

    // Wait for WebSocket to reconnect
    await waitForConnected(page, 10000);

    // Verify messages are replayed after reload
    const assistantMsgAfterReload = page.locator(Selectors.assistantMessage);
    await expect(assistantMsgAfterReload).toBeVisible({ timeout: 15000 });
    await expect(assistantMsgAfterReload).toContainText("History test response");

    const userMsgAfterReload = page.locator(Selectors.userMessage);
    await expect(userMsgAfterReload).toBeVisible({ timeout: 15000 });
    await expect(userMsgAfterReload).toContainText("History test message");
  });

  test("should replay tool call events after page reload", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call that creates a collapsible card
    await mockBackend.registerToolCall(
      "grep",
      JSON.stringify({
        pattern: "test_pattern",
        path: ".",
      })
    );

    // Send a message to trigger the tool call
    await sendMessage(page, "Search for pattern");

    // Wait for tool call card to appear
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Verify tool name is displayed
    const toolName = toolCard.locator(".tool-name");
    await expect(toolName).toBeVisible();

    // Reload the page
    await page.reload({ waitUntil: "load" });

    // Wait for WebSocket to reconnect
    await waitForConnected(page, 10000);

    // Verify tool call card is replayed after reload
    const toolCardAfterReload = page.locator(".message.tool-call");
    await expect(toolCardAfterReload).toBeVisible({ timeout: 15000 });
    const toolNameAfterReload = toolCardAfterReload.locator(".tool-name");
    await expect(toolNameAfterReload).toBeVisible();
  });

  test("should display system messages after reload", async ({
    page,
    mockBackend,
  }) => {
    // Register mock response
    await mockBackend.registerResponse({
      response_text: "System message test",
    });

    // Send a message
    await sendMessage(page, "System message test");

    // Wait for response
    const assistantMsg = page.locator(Selectors.assistantMessage).last();
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    // Reload the page
    await page.reload({ waitUntil: "load" });

    // Wait for WebSocket to reconnect
    await waitForConnected(page, 10000);

    // Welcome system message should still be present
    const systemMessage = page.locator(Selectors.systemMessage);
    await expect(systemMessage).toBeVisible({ timeout: 15000 });
  });
});

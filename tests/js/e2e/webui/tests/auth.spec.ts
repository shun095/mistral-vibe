import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Authentication", () => {
  test("should show disconnected status on load", async ({ page, webServer }) => {
    await page.goto(webServer.getUrl());

    // Status should show disconnected
    const status = page.locator(Selectors.statusIndicator);
    await expect(status).toBeVisible();
    await expect(status).toHaveText("Disconnected");
  });

  test("should accept token from URL and attempt connection", async ({
    page,
    authToken,
    webServer,
  }) => {
    // Navigate with token in URL
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // The page should load and attempt to connect
    // Status indicator should be visible
    await expect(page.locator(Selectors.statusIndicator)).toBeVisible();

    // Chat interface should be accessible
    await expect(page.locator(Selectors.messageInput)).toBeVisible();
    await expect(page.locator(Selectors.sendButton)).toBeVisible();
  });

  test("should show system message when disconnected", async ({ page, webServer }) => {
    await page.goto(webServer.getUrl());

    // Should show system welcome message
    const systemMessage = page.locator(Selectors.systemMessage);
    await expect(systemMessage).toBeVisible();
    await expect(systemMessage).toContainText("Welcome to Mistral Vibe");
  });

  test("should have send button disabled when input is empty", async ({
    page,
    webServer,
  }) => {
    await page.goto(webServer.getUrl());

    // Send button should be disabled when input is empty
    await expect(page.locator(Selectors.sendButton)).toBeDisabled();

    // Type something - send button should become enabled
    await page.fill(Selectors.messageInput, "Test message");
    await expect(page.locator(Selectors.sendButton)).toBeEnabled();
  });
});

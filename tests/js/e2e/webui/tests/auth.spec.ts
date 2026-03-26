import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Authentication", () => {
  test("should redirect to login page without auth", async ({ page, webServer }) => {
    await page.goto(webServer.getUrl());

    // Should redirect to login page
    await expect(page).toHaveURL(/.*\/login$/);

    // Login box should be visible
    const loginBox = page.locator(".login-box");
    await expect(loginBox).toBeVisible();
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
    await expect(page.locator(Selectors.statusIndicator)).toBeVisible({ timeout: 15000 });

    // Chat interface should be accessible
    await expect(page.locator(Selectors.messageInput)).toBeVisible({ timeout: 15000 });
    await expect(page.locator(Selectors.sendButton)).toBeVisible({ timeout: 15000 });
  });

  test("should show system message when authenticated", async ({ page, authToken, webServer }) => {
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Should show system welcome message (may take a moment to load)
    const systemMessage = page.locator(Selectors.systemMessage);
    await expect(systemMessage).toBeVisible({ timeout: 15000 });
    await expect(systemMessage).toContainText("Welcome to Mistral Vibe");
  });

  test("should have send button disabled when input is empty", async ({
    page,
    authToken,
    webServer,
  }) => {
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Wait for chat interface to load
    await expect(page.locator(Selectors.messageInput)).toBeVisible({ timeout: 15000 });

    // Send button should be disabled when input is empty
    await expect(page.locator(Selectors.sendButton)).toBeDisabled();

    // Type something - send button should become enabled
    await page.locator(Selectors.messageInput).type("Test message", { delay: 10 });
    await expect(page.locator(Selectors.sendButton)).toBeEnabled({ timeout: 5000 });
  });
});

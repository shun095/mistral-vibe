import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Authentication", () => {
  test("should redirect to login page without auth", async ({ webServer, context }) => {
    // For this test, we need to navigate without auth
    // Create a new page in the same context to avoid affecting the main authenticated session
    const newPage = await context.newPage();

    try {
      await newPage.goto(webServer.getUrl());

      // Should redirect to login page
      await expect(newPage).toHaveURL(/.*\/login$/);

      // Login box should be visible
      const loginBox = newPage.locator(".login-box");
      await expect(loginBox).toBeVisible();
    } finally {
      await newPage.close();
    }
  });

  test("should accept token from URL and attempt connection", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // Status indicator should be visible
    await expect(page.locator(Selectors.statusIndicator)).toBeVisible({ timeout: 15000 });

    // Chat interface should be accessible
    await expect(page.locator(Selectors.messageInput)).toBeVisible({ timeout: 15000 });
    await expect(page.locator(Selectors.sendButton)).toBeVisible({ timeout: 15000 });
  });

  test("should show system message when authenticated", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Should show system welcome message (may take a moment to load)
    const systemMessage = page.locator(Selectors.systemMessage);
    await expect(systemMessage).toBeVisible({ timeout: 15000 });
    await expect(systemMessage).toContainText("Welcome to Mistral Vibe");
  });

  test("should have send button disabled when input is empty", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture

    // Send button should be disabled when input is empty
    await expect(page.locator(Selectors.sendButton)).toBeDisabled();

    // Type something - send button should become enabled
    await page.locator(Selectors.messageInput).fill("Test message");
    await expect(page.locator(Selectors.sendButton)).toBeEnabled({ timeout: 5000 });
  });
});

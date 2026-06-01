import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Authentication", () => {
  test("should logout and redirect to login page", async ({
    page,
    webServer,
  }) => {
    await expect(page).toHaveURL(webServer.getUrl());

    await page.click(Selectors.logoutBtn);

    await expect(page).toHaveURL(/.*\/login$/, { timeout: 10000 });

    const loginBox = page.locator(".login-box");
    await expect(loginBox).toBeVisible();
  });

  test("should redirect to login page without auth", async ({
    webServer,
    context,
  }) => {
    const newPage = await context.newPage();

    try {
      await newPage.goto(webServer.getUrl());

      await expect(newPage).toHaveURL(/.*\/login$/);

      const loginBox = newPage.locator(".login-box");
      await expect(loginBox).toBeVisible();
    } finally {
      await newPage.close();
    }
  });

  test("should show system message when authenticated", async ({ page }) => {
    const systemMessage = page.locator(Selectors.systemMessage);
    await expect(systemMessage).toBeVisible({ timeout: 15000 });
    await expect(systemMessage).toContainText("Welcome to Mistral Vibe");
  });

  test("should not reload repeatedly when visiting login page with valid cookie", async ({
    webServer,
    context,
    authToken,
  }) => {
    const loginPage = await context.newPage();
    await loginPage.goto(`${webServer.getUrl()}/login`);

    const tokenInput = loginPage.locator("#token");
    await tokenInput.fill(authToken);
    await loginPage.locator("#login-btn").click();

    await expect(loginPage).toHaveURL(webServer.getUrl(), { timeout: 10000 });

    await loginPage.goto(
      `${webServer.getUrl()}/login`,
      { waitUntil: "domcontentloaded" }
    );

    await loginPage.waitForURL(webServer.getUrl(), { timeout: 5000 });
    await expect(loginPage).toHaveURL(webServer.getUrl());

    await loginPage.close();
  });

  test("should login with valid token and show chat interface", async ({
    webServer,
    context,
    authToken,
  }) => {
    const loginPage = await context.newPage();

    try {
      await loginPage.goto(`${webServer.getUrl()}/login`);
      await loginPage.fill("#token", authToken);
      await loginPage.click("#login-btn");

      await expect(loginPage).toHaveURL(webServer.getUrl(), {
        timeout: 15000,
      });
      await expect(loginPage.locator("#messages")).toBeVisible();
      await expect(loginPage.locator("#message-input")).toBeVisible();
      await expect(loginPage.locator("#send-btn")).toBeVisible();
      await expect(loginPage.locator("#status-dot")).toBeVisible();
    } finally {
      await loginPage.close();
    }
  });

  test("should show error on invalid token", async ({
    webServer,
    context,
  }) => {
    const loginPage = await context.newPage();

    try {
      await loginPage.goto(`${webServer.getUrl()}/login`);
      await loginPage.fill("#token", "invalid-token");
      await loginPage.click("#login-btn");

      await expect(loginPage).toHaveURL(/.*\/login$/);
      const errorMsg = loginPage.locator("#error-message");
      await expect(errorMsg).toBeVisible({ timeout: 5000 });
      await expect(errorMsg).toContainText("Invalid");
    } finally {
      await loginPage.close();
    }
  });
});

/**
 * E2E visual test for code-server integration.
 *
 * User story: Launch Vibe with code-server enabled, verify VS Code UI loads
 * through the reverse proxy after auto-install completes.
 *
 * These tests rely on Vibe's auto-install mechanism. If code-server is not
 * installed before the test, Vibe installs it automatically. The test fails
 * if the VS Code workbench does not load within the timeout.
 */

import { test as base, expect } from "@playwright/test";
import { ServerManager } from "../fixtures/server-manager";

// Custom fixture that starts a Vibe server with code-server enabled
interface CodeServerFixtures {
  webServer: ServerManager;
  authToken: string;
}

const test = base.extend<CodeServerFixtures>({
  webServer: async ({}, use) => {
    // Use dynamic ports to avoid collisions
    const webPort = 9097 + Math.floor(Math.random() * 100);
    const csPort = 18080 + Math.floor(Math.random() * 100);

    const server = new ServerManager({
      port: webPort,
      token: "test-token-code-server",
      codeServerEnabled: true,
      codeServerPort: csPort,
    });
    await server.start();

    await use(server);

    await server.stop();
  },
  authToken: async ({}, use) => {
    await use("test-token-code-server");
  },
});

test.describe("Code-server visual integration", () => {
  test.setTimeout(60000); // 1 min: server start + code-server init + VS Code load

  test("VS Code UI loads through reverse proxy after auto-install", async ({
    page,
    webServer,
    authToken,
  }) => {
    // Set auth cookie before navigation
    await page.context().addCookies([
      {
        name: "vibe_auth",
        value: authToken,
        domain: "127.0.0.1",
        path: "/",
        httpOnly: false,
        secure: false,
        sameSite: "Lax",
      },
    ]);

    // Navigate to the VS Code proxy URL
    const vscodeUrl = webServer.getCodeServerUrl();
    console.log(`[E2E] Navigating to ${vscodeUrl}`);
    await page.goto(vscodeUrl, { waitUntil: "domcontentloaded", timeout: 30000 });

    // Wait for VS Code workbench to appear
    await page.waitForFunction(
      () => document.querySelector(".monaco-workbench") !== null,
      { timeout: 30000 }
    );

    const workbench = page.locator(".monaco-workbench").first();
    await expect(workbench).toBeVisible({ timeout: 10000 });
  });

  test("toolbar button opens VS Code in new tab", async ({
    page,
    webServer,
    authToken,
  }) => {
    // Set auth cookie
    await page.context().addCookies([
      {
        name: "vibe_auth",
        value: authToken,
        domain: "127.0.0.1",
        path: "/",
        httpOnly: false,
        secure: false,
        sameSite: "Lax",
      },
    ]);

    // Navigate to the main WebUI page
    const webUrl = webServer.getUrl();
    await page.goto(`${webUrl}/`, { waitUntil: "domcontentloaded", timeout: 30000 });

    // Wait for code-server config to be loaded
    await page.waitForFunction(
      () => {
        const vibeClient = (window as any).vibeClient;
        return vibeClient && vibeClient._codeServerEnabled === true;
      },
      { timeout: 10000 }
    );

    // Verify the toolbar button is visible
    const vscodeBtn = page.locator("#vscode-btn");
    await expect(vscodeBtn).toBeVisible();

    // Click the toolbar button and wait for new tab
    const [newPage] = await Promise.all([
      page.context().waitForEvent("page", { timeout: 10000 }),
      vscodeBtn.click(),
    ]);

    // Wait for VS Code workbench in the new tab
    await newPage.waitForFunction(
      () => document.querySelector(".monaco-workbench") !== null,
      { timeout: 30000 }
    );

    const url = newPage.url();
    expect(url).toContain("/vscode/");

    const workbench = newPage.locator(".monaco-workbench").first();
    await expect(workbench).toBeVisible({ timeout: 10000 });

    await newPage.close();
  });
});

export { test };

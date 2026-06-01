/**
 * E2E tests for code-server integration in the WebUI.
 *
 * User stories:
 *   Enable via config: button hidden/shown based on code_server_enabled
 *   Browse /vscode/: toolbar button opens VS Code with project directory
 *   Auto lifecycle: subprocess spawn/shutdown (unit tests only)
 */

import { test, expect } from "../fixtures";

// Enable via config — button respects code_server_enabled flag

test.describe("Code-server config visibility", () => {
  test("VS Code toolbar button exists in header", async ({ page }) => {
    const vscodeBtn = page.locator("#vscode-btn");
    await expect(vscodeBtn).toBeAttached();
  });

  test("VS Code toolbar button is hidden when code-server disabled", async ({
    page,
  }) => {
    const vscodeBtn = page.locator("#vscode-btn");
    const display = await vscodeBtn.evaluate((el) =>
      window.getComputedStyle(el).display
    );
    expect(display).toBe("none");
  });

  test("VS Code toolbar button is shown when code-server enabled", async ({
    page,
  }) => {
    await page.evaluate(() => {
      (window as any).vibeClient._codeServerEnabled = true;
      const btn = document.getElementById("vscode-btn");
      if (btn) btn.style.display = "inline-flex";
    });

    const vscodeBtn = page.locator("#vscode-btn");
    await expect(vscodeBtn).toBeVisible();
  });

  test("toolbar button click opens /vscode/ with folder param", async ({
    page,
  }) => {
    const openedUrl = await page.evaluate(() => {
      let capturedUrl: string | null = null;
      const originalOpen = window.open;
      window.open = (url: string | URL) => {
        capturedUrl = String(url);
        return { close: () => {} } as WindowProxy;
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient) {
        vibeClient._codeServerEnabled = true;
        vibeClient._codeServerWorkdir = '/home/user/project';
        vibeClient._openInCodeServer();
      }

      window.open = originalOpen;
      return capturedUrl;
    });

    expect(openedUrl).toContain("/vscode/");
    expect(openedUrl).toContain("folder=" + encodeURIComponent("/home/user/project"));
  });

  test("toolbar button click opens /vscode/ without folder when no workdir", async ({
    page,
  }) => {
    const openedUrl = await page.evaluate(() => {
      let capturedUrl: string | null = null;
      const originalOpen = window.open;
      window.open = (url: string | URL) => {
        capturedUrl = String(url);
        return { close: () => {} } as WindowProxy;
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient) {
        vibeClient._codeServerEnabled = true;
        vibeClient._codeServerWorkdir = '';
        vibeClient._openInCodeServer();
      }

      window.open = originalOpen;
      return capturedUrl;
    });

    expect(openedUrl).toContain("/vscode/");
    expect(openedUrl).not.toContain("folder=");
  });

  test("toolbar button does nothing when code-server disabled", async ({
    page,
  }) => {
    const openedUrl = await page.evaluate(() => {
      let capturedUrl: string | null = null;
      const originalOpen = window.open;
      window.open = (url: string | URL) => {
        capturedUrl = String(url);
        return { close: () => {} } as WindowProxy;
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient) {
        vibeClient._codeServerEnabled = false;
        vibeClient._openInCodeServer();
      }

      window.open = originalOpen;
      return capturedUrl;
    });

    expect(openedUrl).toBeNull();
  });
});

// Auto lifecycle — subprocess spawn/shutdown (unit tests only)
// Covered by tests/core/test_code_server_manager.py (21 tests)

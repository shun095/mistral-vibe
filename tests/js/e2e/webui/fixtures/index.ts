/**
 * Custom Playwright fixtures for WebUI E2E tests.
 */

import { test as base, Page } from "@playwright/test";
import { ServerManager } from "./server-manager";
import { MockBackendClient } from "./mock-backend";
import { Selectors, waitForConnected, setLogPort } from "../helpers/test-utils";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

// Pre-allocated ports from global setup
const portsFile = os.tmpdir() + "/vibe-e2e-ports.json";
let preAllocatedPorts: number[] = [];
let portsLoaded = false;

function getPreAllocatedPorts(): number[] {
  if (portsLoaded) {
    return preAllocatedPorts;
  }
  try {
    const data = fs.readFileSync(portsFile, "utf-8");
    preAllocatedPorts = JSON.parse(data);
    portsLoaded = true;
  } catch {
    // Fallback: will generate ports based on worker index
    portsLoaded = true;
  }
  return preAllocatedPorts;
}

export interface WebUIFixtures {
  webServer: ServerManager;
  mockBackend: MockBackendClient;
  authToken: string;
}

// Extend the base test with our custom fixtures
export const test = base.extend<WebUIFixtures & { page: Page }>({
  // Server fixture - start a fresh server for each test to ensure clean state
  // This is important for tool approval tests where server state must be isolated
  webServer: async ({}, use, testInfo) => {
    // Get pre-allocated port for this worker
    const workerIndex = testInfo.workerIndex;
    const availablePorts = getPreAllocatedPorts();
    let port: number;

    if (availablePorts.length > 0 && workerIndex < availablePorts.length) {
      // Use pre-allocated port
      port = availablePorts[workerIndex];
    } else {
      // Fallback: use worker index offset
      port = 9093 + workerIndex;
    }

    // Create a fresh server for each test
    const server = new ServerManager({
      port,
      token: "test-token-123",
    });
    await server.start();

    await use(server);

    // Stop the server after each test to ensure clean state
    await server.stop();
  },

  // Mock backend client fixture - always available
  mockBackend: async ({ webServer }, use) => {
    const mockBackend = new MockBackendClient(
      webServer.getUrl(),
      webServer.getToken()
    );

    await use(mockBackend);
    // No teardown - reset is handled in page fixture
  },

  // Page fixture with automatic state reset between tests
  // Depends on mockBackend to ensure mock data is reset before and after each test
  page: async ({ page, webServer, authToken, mockBackend }, use, testInfo) => {
    // Set port for diagnostic logs — all E2E logs use this as correlation key
    setLogPort(webServer.getPort());

    // Capture browser console logs
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
    });

    // Reset mock data BEFORE navigating to ensure clean state
    await mockBackend.reset();

    // Login via the login page to set the cookie
    await page.goto(`${webServer.getUrl()}/login`);
    await page.locator("#token").fill(authToken);
    await page.locator("#login-btn").click();

    // Wait for page to redirect and message input to be visible
    await page.locator(Selectors.messageInput).waitFor({ state: "visible", timeout: 15000 });

    // Wait for WebSocket to connect
    await waitForConnected(page, 10000);

    // Wait for message input to be enabled (not disabled)
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && !el.hasAttribute("disabled");
      },
      Selectors.messageInput,
      { timeout: 10000 }
    );

    // Diagnostic: log page state if there are unexpected messages after fresh connect.
    // The server sends 'reset' → clears DOM → streams history → 'connected'.
    // A fresh server should have no history, so only the welcome message should exist.
    // If tool-call cards appear here, it indicates cross-test contamination.
    const pageState = await page.evaluate(() => {
      const container = document.getElementById('messages');
      if (!container) return { error: 'messages container not found' };
      const messages = Array.from(container.querySelectorAll('.message'));
      return {
        totalMessages: messages.length,
        toolCalls: messages.filter(m => m.classList.contains('tool-call')).map(m => ({
          toolName: m.querySelector('.tool-name')?.textContent?.trim(),
          status: m.querySelector('.tool-status')?.textContent?.trim(),
          collapsed: m.classList.contains('collapsed'),
        })),
        systemMessages: messages.filter(m => m.classList.contains('system')).map(m => m.textContent?.slice(0, 80)),
        assistantMessages: messages.filter(m => m.classList.contains('assistant')).length,
        userMessages: messages.filter(m => m.classList.contains('user')).length,
        containerInnerHTML: container.innerHTML.slice(0, 500),
      };
    });

    if (pageState.toolCalls?.length > 0) {
      console.error(
        `[E2E] [${webServer.getPort()}] stale tool-cards: ${JSON.stringify(pageState.toolCalls)}`
      );
    }

    await use(page);

    // Write console logs to test-results directory
    if (consoleLogs.length > 0) {
      const outputDir = testInfo.outputDir || "test-results";
      const logPath = path.join(outputDir, "console.log");
      fs.writeFileSync(logPath, consoleLogs.join("\n") + "\n", "utf-8");
    }

    // No state reset needed — server is stopped/started between tests,
    // so server-side state is already clean. Next test gets a fresh page
    // via the login flow above.
  },

  // Auth token fixture
  authToken: async ({}, use) => {
    await use("test-token-123");
  },
});

// Re-export Playwright types
export { expect } from "@playwright/test";
export type { Page };

/**
 * Custom Playwright fixtures for WebUI E2E tests.
 */

import { test as base, Page, APIRequestContext, test as playwrightTest } from "@playwright/test";
import { ServerManager } from "./server-manager";
import { MockBackendClient } from "./mock-backend";
import { resetTestState, Selectors, waitForConnected } from "../helpers/test-utils";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

// Coverage data collection (enabled when COVERAGE=1)
const COLLECT_COVERAGE = process.env.COVERAGE === "1";
const COVERAGE_DIR = ".coverage-e2e";

function saveCoverage(page: Page): void {
  if (!COLLECT_COVERAGE) return;
  const testInfo = playwrightTest.info();
  fs.mkdirSync(COVERAGE_DIR, { recursive: true });
  const workerIndex = testInfo.workerIndex ?? 0;
  const testIndex = testInfo.retry ?? 0;
  const fileName = `worker-${workerIndex}-test-${testIndex}.json`;
  const filePath = path.join(COVERAGE_DIR, fileName);
  page.coverage.stopJSCoverage().then((coverage) => {
    fs.writeFileSync(filePath, JSON.stringify(coverage), "utf-8");
  }).catch(() => {
    // Coverage may have been stopped already
  });
}

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
  page: async ({ page, webServer, authToken, mockBackend }, use) => {
    // Start JS coverage before each test (if enabled)
    if (COLLECT_COVERAGE) {
      await page.coverage.startJSCoverage({ resetOnNavigation: false });
    }

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

    await use(page);

    // Stop coverage after test (if enabled)
    if (COLLECT_COVERAGE) {
      saveCoverage(page);
    }

    // After test, reset mock data and page state
    // This ensures the next test starts with clean state
    try {
      // Reset mock data before page reload
      await mockBackend.reset();

      // Check if page is still open before trying to reset
      if (!page.isClosed()) {
        await resetTestState(page, webServer.getUrl());
        // resetTestState() already waits for page readiness, no need to wait again here
      }
    } catch (error) {
      // Ignore errors - page might be closed by the test
      const errorMsg = String(error);
      if (!errorMsg.includes("page is closed") && !errorMsg.includes("Target page")) {
        console.warn("Failed to reset test state:", error);
      }
    }
  },

  // Auth token fixture
  authToken: async ({}, use) => {
    await use("test-token-123");
  },
});

// Re-export Playwright types
export { expect } from "@playwright/test";
export type { Page, APIRequestContext };

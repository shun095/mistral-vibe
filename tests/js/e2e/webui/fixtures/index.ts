/**
 * Custom Playwright fixtures for WebUI E2E tests.
 */

import { test as base, Page, APIRequestContext } from "@playwright/test";
import { ServerManager } from "./server-manager";
import { MockBackendClient } from "./mock-backend";
import { resetTestState, Selectors } from "../helpers/test-utils";

export interface WebUIFixtures {
  webServer: ServerManager;
  mockBackend: MockBackendClient;
  authToken: string;
}

// Cache server instances per worker to avoid restart between tests
export const workerServers = new Map<number, ServerManager>();

// Cleanup all servers when process exits
process.on("exit", () => {
  console.log("Process exit: stopping all servers...");
  workerServers.forEach((server) => {
    try {
      // Note: This is synchronous, so we can't await
      // The servers will be killed when the process exits anyway
      console.log(`Stopping server on port ${server.getPort()}...`);
    } catch (error) {
      console.warn("Failed to stop server:", error);
    }
  });
});

// Extend the base test with our custom fixtures
export const test = base.extend<WebUIFixtures & { page: Page }>({
  // Server fixture - starts once per worker, stops after all tests
  // Uses unique port per worker to enable parallel execution across browsers
  // Cached per worker to avoid restart between tests
  webServer: async ({}, use, testInfo) => {
    // Use workerIndex as the cache key
    const workerIndex = testInfo.workerIndex;

    // Check if we already have a server for this worker
    let server = workerServers.get(workerIndex);

    if (!server) {
      // Create server manager with a starting port
      // ServerManager will find an available port automatically
      const startPort = 9093 + workerIndex;
      server = new ServerManager({
        port: startPort,
        token: "test-token-123",
      });
      await server.start(); // This will find available port if startPort is in use
      workerServers.set(workerIndex, server);
      console.log(`Worker ${workerIndex} started server on port ${server.getPort()}`);
    }

    await use(server);

    // Don't stop the server here - it will be reused for next test in same worker
    // Server will be stopped when the worker shuts down
  },

  // Page fixture with automatic state reset between tests
  page: async ({ page, webServer, authToken }, use) => {
    // Navigate to the app with auth token
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Wait for initial load
    await page.locator(Selectors.messageInput).waitFor({ state: "visible", timeout: 15000 });

    await use(page);

    // After test, reset state for next test using /clear + reload
    // This is much faster than restarting the server
    try {
      // Check if page is still open before trying to reset
      if (!page.isClosed()) {
        await resetTestState(page, webServer.getUrl(), authToken);
      }
    } catch (error) {
      // Ignore errors - page might be closed by the test
      // console.warn("Failed to reset test state:", error);
    }
  },

  // Mock backend client fixture
  mockBackend: async ({ webServer }, use) => {
    const mockBackend = new MockBackendClient(
      webServer.getUrl(),
      webServer.getToken()
    );

    // Reset mock data before each test
    await mockBackend.reset();

    await use(mockBackend);

    // Cleanup after each test
    await mockBackend.reset();
  },

  // Auth token fixture
  authToken: async ({}, use) => {
    await use("test-token-123");
  },
});

// Re-export Playwright types
export { expect } from "@playwright/test";
export type { Page, APIRequestContext };

/**
 * Custom Playwright fixtures for WebUI E2E tests.
 */

import { test as base, Page, APIRequestContext } from "@playwright/test";
import { ServerManager } from "./server-manager";
import { MockBackendClient } from "./mock-backend";

export interface WebUIFixtures {
  webServer: ServerManager;
  mockBackend: MockBackendClient;
  authToken: string;
}

// Extend the base test with our custom fixtures
export const test = base.extend<WebUIFixtures>({
  // Server fixture - starts before tests, stops after
  webServer: async ({}, use) => {
    const server = new ServerManager({
      port: 9093,
      token: "test-token-123",
    });

    await server.start();
    await use(server);
    await server.stop();
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

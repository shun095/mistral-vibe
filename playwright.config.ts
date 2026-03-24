import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for Mistral Vibe WebUI E2E tests.
 *
 * Run tests with:
 *   npm run test:e2e              # Run all tests
 *   npm run test:e2e:ui           # Run with UI
 *   npm run test:e2e:debug        # Run with debugger
 *   npm run test:e2e:headed       # Run with visible browser
 */
export default defineConfig({
  testDir: "./tests/js/e2e/webui",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 120000, // 120 seconds for tests (server startup can be slow)
  expect: {
    timeout: 30000, // 30 seconds for expect assertions
  },
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["list"],
  ],
  outputDir: "test-results/webui",

  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});

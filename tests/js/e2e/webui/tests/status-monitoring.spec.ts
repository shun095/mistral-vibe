/**
 * E2E tests for status and monitoring features.
 *
 * Merged context progress and processing indicator assertions.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  updateContextProgress,
  setProcessingState,
  callVibeClient,
} from "../helpers/test-utils";

test.describe("Status & Monitoring", () => {
  test("should show connected status dot on page load", async ({ page }) => {
    const statusDot = page.locator(Selectors.statusIndicator);
    await expect(statusDot).toBeVisible();
    await expect(statusDot).toHaveClass(/connected/);
  });

  test("should hide processing indicator when agent is idle", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerResponse({ response_text: "Done!" });

    const processingIndicator = page.locator(Selectors.processingIndicator);

    await sendMessage(page, "Simple message");

    const assistantMsg = page.locator(Selectors.assistantMessage);
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    await expect(processingIndicator).not.toBeVisible();
  });

  test("should show context progress bar with correct color and text", async ({
    page,
  }) => {
    const contextProgress = page.locator(Selectors.contextProgress);

    // 90% → red/high
    await updateContextProgress(page, 90000, 100000);
    await expect(contextProgress).toBeVisible({ timeout: 10000 });
    await expect(contextProgress).toHaveClass(/high/);
    await expect(contextProgress).toHaveText(/90%\s*\n\s*\(90k\/100k tokens\)/);

    // 80% → yellow/medium
    await updateContextProgress(page, 80000, 100000);
    await expect(contextProgress).toHaveClass(/medium/);
    await expect(contextProgress).toHaveText(/80%\s*\n\s*\(80k\/100k tokens\)/);

    // 50% → green/low
    await updateContextProgress(page, 50000, 100000);
    await expect(contextProgress).toHaveClass(/low/);
    await expect(contextProgress).toHaveText(/50%\s*\n\s*\(50k\/100k tokens\)/);
  });

  test("should show processing indicator with spinner and percentage", async ({
    page,
  }) => {
    await setProcessingState(page, true);

    const processingIndicator = page.locator(Selectors.processingIndicator);
    await expect(processingIndicator).toBeVisible({ timeout: 5000 });

    // Spinner visible
    await expect(
      processingIndicator.locator(".processing-spinner")
    ).toBeVisible();

    // Percentage display
    await callVibeClient(page, "updateProcessingIndicator", 75);
    await expect(
      processingIndicator.locator(".processing-percentage")
    ).toHaveText("75%");

    await setProcessingState(page, false);
  });
});

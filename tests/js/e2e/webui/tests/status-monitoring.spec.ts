/**
 * E2E tests for status and monitoring features.
 * Covers US-23 (WebSocket status), US-24 (token usage), US-25 (processing indicator).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, updateContextProgress, setProcessingState, callVibeClient } from "../helpers/test-utils";

test.describe("Status & Monitoring", () => {
  test("should show connected status dot on page load", async ({ page }) => {
    const statusDot = page.locator(Selectors.statusIndicator);
    await expect(statusDot).toBeVisible();
    // Green class indicates connected state
    await expect(statusDot).toHaveClass(/connected/);
  });

  test("should hide processing indicator when agent is idle", async ({
    page,
    mockBackend,
  }) => {
    // Register a simple response
    await mockBackend.registerResponse({ response_text: "Done!" });

    const processingIndicator = page.locator(
      Selectors.processingIndicator
    );

    await sendMessage(page, "Simple message");

    // Wait for response to complete
    const assistantMsg = page.locator(Selectors.assistantMessage);
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    // Processing indicator should be hidden after response
    await expect(processingIndicator).not.toBeVisible();
  });

  test("should show context progress bar when usage data is received", async ({
    page,
    mockBackend,
  }) => {
    // Register a response with usage data
    await mockBackend.registerResponse({
      response_text: "Response with usage",
      usage: { prompt_tokens: 100, completion_tokens: 50 },
    });

    const contextProgress = page.locator(
      Selectors.contextProgress
    );

    await sendMessage(page, "Check usage");

    // Context progress bar should be visible after receiving usage data
    await expect(contextProgress).toBeVisible({ timeout: 10000 });
  });

  test("should update context progress color based on token percentage", async ({
    page,
  }) => {
    const contextProgress = page.locator(
      Selectors.contextProgress
    );

    // Test red color (high: >= 90%)
    await updateContextProgress(page, 90000, 100000);

    // Should have 'high' class for >= 90% usage (red)
    await expect(contextProgress).toHaveClass(/high/);
    await expect(contextProgress).toHaveText(/90% \(90k\/100k tokens\)/);

    // Test yellow color (medium: 75-89%)
    await updateContextProgress(page, 80000, 100000);

    // Should have 'medium' class for 75-89% usage (yellow)
    await expect(contextProgress).toHaveClass(/medium/);
    await expect(contextProgress).toHaveText(/80% \(80k\/100k tokens\)/);

    // Test green color (low: < 75%)
    await updateContextProgress(page, 50000, 100000);

    // Should have 'low' class for < 75% usage (green)
    await expect(contextProgress).toHaveClass(/low/);
    await expect(contextProgress).toHaveText(/50% \(50k\/100k tokens\)/);
  });

  test("should show processing indicator during agent processing", async ({
    page,
  }) => {
    // Simulate agent processing state
    await setProcessingState(page, true);

    const processingIndicator = page.locator(
      Selectors.processingIndicator
    );

    // Processing indicator should be visible during processing
    await expect(processingIndicator).toBeVisible({ timeout: 5000 });

    // Processing spinner should be visible
    const spinner = processingIndicator.locator(".processing-spinner");
    await expect(spinner).toBeVisible();

    // Reset to idle state
    await setProcessingState(page, false);
  });

  test("should show percentage overlay on processing indicator during processing", async ({
    page,
  }) => {
    // Simulate agent processing state
    await setProcessingState(page, true);

    const processingIndicator = page.locator(
      Selectors.processingIndicator
    );

    // Update the percentage display
    await callVibeClient(page, "updateProcessingIndicator", 75);

    // Percentage span should show the percentage
    const percentageSpan = processingIndicator.locator(".processing-percentage");
    await expect(percentageSpan).toHaveText("75%");

    // Reset to idle state
    await setProcessingState(page, false);
  });
});

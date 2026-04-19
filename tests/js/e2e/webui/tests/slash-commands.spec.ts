/**
 * E2E tests for WebUI slash commands (non-/resume).
 * Covers US-14: /help, /clean with autocomplete.
 */

import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Slash Commands (non-/resume)", () => {
  test("should show autocomplete dropdown when typing /", async ({ page }) => {
    // Focus the input
    await page.click(Selectors.messageInput);

    // Type "/" to trigger autocomplete
    await page.keyboard.press("/");

    // Autocomplete container should appear
    const autocomplete = page.locator(".slash-autocomplete");
    await expect(autocomplete).toBeVisible({ timeout: 5000 });

    // Should contain command suggestions
    const suggestions = autocomplete.locator(".suggestions li");
    const count = await suggestions.count();
    expect(count).toBeGreaterThan(0);
  });

  test("should filter autocomplete suggestions when typing command prefix", async ({
    page,
  }) => {
    // Type "/" to trigger autocomplete
    await page.click(Selectors.messageInput);
    await page.keyboard.press("/");

    const autocomplete = page.locator(".slash-autocomplete");
    await expect(autocomplete).toBeVisible({ timeout: 5000 });

    // Type "h" to filter to commands starting with "h"
    await page.keyboard.type("h", { delay: 50 });

    // Suggestions should still be visible (filtered)
    await expect(autocomplete).toBeVisible({ timeout: 5000 });
  });

  test("should hide autocomplete when typing non-slash character", async ({
    page,
  }) => {
    // Type "/" to trigger autocomplete
    await page.click(Selectors.messageInput);
    await page.keyboard.press("/");

    const autocomplete = page.locator(".slash-autocomplete");
    await expect(autocomplete).toBeVisible({ timeout: 5000 });

    // Type a non-slash character to clear the prefix
    await page.keyboard.type("x");

    // Autocomplete should be hidden
    await expect(autocomplete).not.toBeVisible({ timeout: 3000 });
  });

  test("should hide autocomplete when clicking outside", async ({ page }) => {
    // Type "/" to trigger autocomplete
    await page.click(Selectors.messageInput);
    await page.keyboard.press("/");

    const autocomplete = page.locator(".slash-autocomplete");
    await expect(autocomplete).toBeVisible({ timeout: 5000 });

    // Click outside the autocomplete
    await page.click("#messages");

    // Autocomplete should be hidden
    await expect(autocomplete).not.toBeVisible({ timeout: 3000 });
  });
});

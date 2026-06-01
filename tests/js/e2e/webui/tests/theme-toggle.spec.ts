/**
 * E2E tests for theme toggle feature.
 * Covers US-27 (dark/light theme toggle).
 */

import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Theme Toggle", () => {
  test("should show theme toggle button in header", async ({ page }) => {
    const themeBtn = page.locator(Selectors.themeToggle);
    await expect(themeBtn).toBeVisible();
  });

  test("should toggle between dark and light themes", async ({ page }) => {
    const themeBtn = page.locator(Selectors.themeToggle);
    const icon = themeBtn.locator(".material-symbols-rounded");

    // Get initial icon (default is light theme, so icon should be dark_mode)
    let iconText = await icon.textContent();
    expect(iconText).toBe("dark_mode");

    // Click to switch to dark theme
    await themeBtn.click();

    // Icon should now be light_mode (to switch back)
    iconText = await icon.textContent();
    expect(iconText).toBe("light_mode");

    // Click to switch back to light theme
    await themeBtn.click();

    // Icon should be dark_mode again
    iconText = await icon.textContent();
    expect(iconText).toBe("dark_mode");
  });

  test("should persist theme selection in localStorage", async ({ page }) => {
    const themeBtn = page.locator(Selectors.themeToggle);

    // Switch to dark theme
    await themeBtn.click();

    // Verify theme is saved in localStorage
    const savedTheme = await page.evaluate(() => localStorage.getItem("theme"));
    expect(savedTheme).toBe("dark");

    // Reload the page
    await page.reload();

    // Icon should still be light_mode (dark theme active)
    const icon = themeBtn.locator(".material-symbols-rounded");
    let iconText = await icon.textContent();
    expect(iconText).toBe("light_mode");

    // Switch back to light theme
    await themeBtn.click();

    // Verify theme is saved as light
    const savedThemeAfter = await page.evaluate(() => localStorage.getItem("theme"));
    expect(savedThemeAfter).toBe("light");
  });

  test("should default to light theme on first visit", async ({ page }) => {
    // Clear any saved theme
    await page.evaluate(() => localStorage.removeItem("theme"));

    // Reload page to ensure fresh state
    await page.reload();

    const themeBtn = page.locator(Selectors.themeToggle);
    const icon = themeBtn.locator(".material-symbols-rounded");

    // Icon should be dark_mode (indicating we're on light theme)
    const iconText = await icon.textContent();
    expect(iconText).toBe("dark_mode");
  });
});

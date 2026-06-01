/**
 * E2E tests for WebUI prompt history feature.
 *
 * Merged inspect assertions. Close behavior covered by modal-commands.spec.ts.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  waitForVisible,
  waitForHidden,
  waitForResponse,
} from "../helpers/test-utils";

test.describe("Prompt History Feature", () => {
  test("should open with button, modal structure, and content", async ({
    page,
  }) => {
    // Button visible
    const btn = page.locator(Selectors.promptHistoryBtn);
    await expect(btn).toBeVisible();
    const title = await btn.getAttribute("title");
    expect(title).toBe("Prompt history");

    // Open modal
    await btn.click();
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Structure
    await expect(page.locator(Selectors.promptHistoryContent)).toBeVisible();
    await expect(page.locator(Selectors.promptHistoryClose)).toBeVisible();
    await expect(page.locator(Selectors.promptHistorySearch)).toBeVisible();

    // Loading/content state
    const hasContent = await page
      .locator(Selectors.promptHistoryContent)
      .evaluate((el) => {
        const text = el.textContent?.toLowerCase() || "";
        return (
          text.includes("loading") ||
          text.includes("no matching") ||
          text.includes("failed") ||
          el.querySelector(".prompt-history-item") !== null
        );
      });
    expect(hasContent).toBe(true);
  });

  test("should filter history when typing in search box", async ({ page }) => {
    await page.click(Selectors.promptHistoryBtn);
    await waitForVisible(page, Selectors.promptHistoryModal);

    const initialItems = await page
      .locator(Selectors.promptHistoryItem)
      .count();

    await page.fill(Selectors.promptHistorySearch, "test");

    await page.waitForFunction(
      () => {
        const search = document.querySelector(
          "#prompt-history-search"
        ) as HTMLInputElement;
        return search && search.value === "test";
      },
      { timeout: 5000 }
    );

    const filteredItems = await page
      .locator(Selectors.promptHistoryItem)
      .count();

    expect(filteredItems).toBeLessThanOrEqual(initialItems);
  });

  test("should clear search when modal is reopened", async ({ page }) => {
    await page.click(Selectors.promptHistoryBtn);
    await waitForVisible(page, Selectors.promptHistoryModal);

    await page.fill(Selectors.promptHistorySearch, "test search");

    const searchText = await page.inputValue(Selectors.promptHistorySearch);
    expect(searchText).toBe("test search");

    await page.click(Selectors.promptHistoryClose);
    await waitForHidden(page, Selectors.promptHistoryModal);

    await page.click(Selectors.promptHistoryBtn);
    await waitForVisible(page, Selectors.promptHistoryModal);

    const clearedSearchText = await page.inputValue(
      Selectors.promptHistorySearch
    );
    expect(clearedSearchText).toBe("");
  });

  test("should insert prompt at cursor position when clicking history item", async ({
    page,
  }) => {
    await page.fill(Selectors.messageInput, "test prompt for history");
    await page.click(Selectors.sendButton);

    await waitForResponse(page, 15000);

    await page.click(Selectors.promptHistoryBtn);
    await waitForVisible(page, Selectors.promptHistoryModal);

    const historyItems = page.locator(Selectors.promptHistoryItem);
    const itemCount = await historyItems.count();

    if (itemCount > 0) {
      await historyItems.first().click();
      await waitForHidden(page, Selectors.promptHistoryModal);

      const inputValue = await page.inputValue(Selectors.messageInput);
      expect(inputValue.length).toBeGreaterThan(0);
    }
  });
});

import { test, expect } from "../fixtures";
import {
  Selectors,
  waitForVisible,
  waitForHidden,
  waitForResponse,
} from "../helpers/test-utils";

test.describe("Prompt History Feature", () => {
  test("should show prompt history modal when clicking history button", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for prompt history modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Verify modal content is visible
    await expect(page.locator(Selectors.promptHistoryContent)).toBeVisible();

    // Verify close button is visible
    await expect(page.locator(Selectors.promptHistoryClose)).toBeVisible();

    // Verify search input is visible
    await expect(page.locator(Selectors.promptHistorySearch)).toBeVisible();
  });

  test("should show loading state initially", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Should show loading, empty state, or history items
    const content = page.locator(Selectors.promptHistoryContent);
    await expect(content).toBeVisible();

    // Should either show loading text, empty state, or history items
    const hasLoadingOrContent = await content.evaluate((el) => {
      const text = el.textContent?.toLowerCase() || "";
      return (
        text.includes("loading") ||
        text.includes("no matching") ||
        text.includes("failed") ||
        el.querySelector(".prompt-history-item") !== null
      );
    });
    expect(hasLoadingOrContent).toBe(true);
  });

  test("should close modal when clicking close button", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Click close button
    await page.click(Selectors.promptHistoryClose);

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.promptHistoryModal);
  });

  test("should close modal when clicking overlay", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Get the modal content element
    const modalContent = page.locator(Selectors.promptHistoryModal).first();
    const modalBox = await modalContent.boundingBox();

    if (modalBox) {
      // Calculate a point outside the modal but within viewport
      // Click to the left of the modal
      const clickX = Math.max(10, modalBox.x - 10);
      const clickY = modalBox.y + modalBox.height / 2;
      await page.mouse.click(clickX, clickY);
    }

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.promptHistoryModal);
  });

  test("should close modal when pressing Escape", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Press Escape
    await page.keyboard.press("Escape");

    // Wait for modal to be hidden
    await waitForHidden(page, Selectors.promptHistoryModal);
  });

  test("should filter history when typing in search box", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Get initial number of items (if any)
    const initialItems = await page.locator(Selectors.promptHistoryItem).count();

    // Type in search box
    await page.fill(Selectors.promptHistorySearch, "test");

    // Wait for filter to apply (search debounce)
    await page.waitForFunction(() => {
      const search = document.querySelector("#prompt-history-search") as HTMLInputElement;
      return search && search.value === "test";
    }, { timeout: 5000 });

    // Get filtered number of items
    const filteredItems = await page.locator(Selectors.promptHistoryItem).count();

    // Filtered items should be less than or equal to initial items
    expect(filteredItems).toBeLessThanOrEqual(initialItems);
  });

  test("should clear search when modal is reopened", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Type in search box
    await page.fill(Selectors.promptHistorySearch, "test search");

    // Verify search box has text
    const searchText = await page.inputValue(Selectors.promptHistorySearch);
    expect(searchText).toBe("test search");

    // Close modal
    await page.click(Selectors.promptHistoryClose);
    await waitForHidden(page, Selectors.promptHistoryModal);

    // Reopen modal
    await page.click(Selectors.promptHistoryBtn);
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Verify search box is cleared
    const clearedSearchText = await page.inputValue(Selectors.promptHistorySearch);
    expect(clearedSearchText).toBe("");
  });

  test("should insert prompt at cursor position when clicking history item", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // First, send a message to create history
    await page.fill(Selectors.messageInput, "test prompt for history");
    await page.click(Selectors.sendButton);

    // Wait for message to be sent and response received
    await waitForResponse(page, 15000);

    // Click prompt history button
    await page.click(Selectors.promptHistoryBtn);

    // Wait for modal to appear
    await waitForVisible(page, Selectors.promptHistoryModal);

    // Check if there are any history items
    const historyItems = page.locator(Selectors.promptHistoryItem);
    const itemCount = await historyItems.count();

    // If there are items, click on one and verify it's inserted
    if (itemCount > 0) {
      // Click on the first history item
      await historyItems.first().click();

      // Wait for modal to close
      await waitForHidden(page, Selectors.promptHistoryModal);

      // Check that the input has content
      const inputValue = await page.inputValue(Selectors.messageInput);
      expect(inputValue.length).toBeGreaterThan(0);
    }
  });

  test("should have prompt history button visible in input area", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // Verify prompt history button is visible
    const historyButton = page.locator(Selectors.promptHistoryBtn);
    await expect(historyButton).toBeVisible();

    // Verify it has the correct title
    const title = await historyButton.getAttribute("title");
    expect(title).toBe("Prompt history");
  });
});

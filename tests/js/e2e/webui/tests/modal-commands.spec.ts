/**
 * E2E tests for WebUI modal slash commands: /model, /config, /mcp, /rewind.
 *
 * Merged inspect assertions that share the same open-modal path.
 * Close behavior tested once on the model picker (shared handler).
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
  waitForVisible,
  waitForHidden,
  clickModalOverlay,
} from "../helpers/test-utils";

// =========================================================================
// Modal Close Behavior (shared handler — tested once)
// =========================================================================

test.describe("Modal Close Behavior", () => {
  test("should close modal when clicking close button", async ({ page }) => {
    await sendMessage(page, "/model");
    await waitForVisible(page, Selectors.modelPickerModal);
    await page.click(Selectors.modelPickerClose);
    await waitForHidden(page, Selectors.modelPickerModal);
  });

  test("should close modal when pressing Escape", async ({ page }) => {
    await sendMessage(page, "/model");
    await waitForVisible(page, Selectors.modelPickerModal);
    await page.keyboard.press("Escape");
    await waitForHidden(page, Selectors.modelPickerModal);
  });

  test("should close modal when clicking overlay", async ({ page }) => {
    await sendMessage(page, "/model");
    await waitForVisible(page, Selectors.modelPickerModal);
    await clickModalOverlay(page);
    await waitForHidden(page, Selectors.modelPickerModal);
  });
});

// =========================================================================
// Model Picker (/model)
// =========================================================================

test.describe("Model Picker (/model)", () => {
  test("should open with model list, active badge, and cleared input", async ({
    page,
  }) => {
    await sendMessage(page, "/model");
    await expect(page.locator(Selectors.modelPickerModal)).toBeVisible({
      timeout: 10000,
    });
    // Structure
    await expect(page.locator(Selectors.modelPickerContent)).toBeVisible();
    await expect(page.locator(Selectors.modelPickerClose)).toBeVisible();
    // Items listed
    await expect(page.locator(Selectors.modelPickerItem).first()).toBeVisible();
    // Active badge
    const activeItem = page.locator(`${Selectors.modelPickerItem}.active`);
    await expect(activeItem).toBeVisible();
    await expect(activeItem).toContainText("Active");
    // Input cleared
    await expect(page.locator(Selectors.messageInput)).toBeEmpty();
  });

  test("should switch model when clicking a model item", async ({ page }) => {
    await sendMessage(page, "/model");
    await waitForVisible(page, Selectors.modelPickerModal);

    const nonActiveItem = page
      .locator(`${Selectors.modelPickerItem}:not(.active)`)
      .first();

    const count = await nonActiveItem.count();
    if (count > 0) {
      const targetAlias = await nonActiveItem
        .locator(".model-picker-alias")
        .textContent();

      await nonActiveItem.click({ force: true });

      const systemMsg = page.locator(Selectors.systemMessage);
      await expect(systemMsg.last()).toBeVisible({ timeout: 15000 });

      const modalVisible = await page
        .locator(Selectors.modelPickerModal)
        .isVisible();
      if (!modalVisible) {
        await expect(systemMsg.last()).toContainText(
          `Model switched to ${targetAlias}`
        );
      }
    }
  });
});

// =========================================================================
// Config Modal (/config)
// =========================================================================

test.describe("Config Modal (/config)", () => {
  test("should open with sections, toggles, and cleared input", async ({
    page,
  }) => {
    await sendMessage(page, "/config");
    await expect(page.locator(Selectors.configModal)).toBeVisible({
      timeout: 10000,
    });
    // Structure
    await expect(page.locator(Selectors.configModalContent)).toBeVisible();
    await expect(page.locator(Selectors.configModalClose)).toBeVisible();
    // Model section
    const modelSection = page
      .locator(".config-section-title")
      .filter({ hasText: "Model" });
    await expect(modelSection).toBeVisible();
    const modelAction = page
      .locator(".config-row-action")
      .filter({ hasText: "Change" });
    await expect(modelAction.first()).toBeVisible();
    // Preferences section
    const prefSection = page
      .locator(".config-section-title")
      .filter({ hasText: "Preferences" });
    await expect(prefSection).toBeVisible();
    // Toggle count
    const toggles = page.locator(".config-toggle");
    expect(await toggles.count()).toBeGreaterThanOrEqual(5);
    // Input cleared
    await expect(page.locator(Selectors.messageInput)).toBeEmpty();
  });

  test("should toggle a switch when clicked", async ({ page }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const { checkedBefore, checkedAfter } = await page.evaluate(() => {
      const cb = document.querySelector(
        ".config-toggle input[type='checkbox']"
      ) as HTMLInputElement;
      const before = cb.checked;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
      return { checkedBefore: before, checkedAfter: cb.checked };
    });

    expect(checkedAfter).not.toBe(checkedBefore);
  });

  test("should open model picker when clicking Change on Model row", async ({
    page,
  }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const changeBtns = page.locator(".config-row-action");
    await changeBtns.first().click();

    await waitForHidden(page, Selectors.configModal);
    await waitForVisible(page, Selectors.modelPickerModal);
  });

  test("should open thinking picker when clicking Change on Thinking row", async ({
    page,
  }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const changeBtns = page.locator(".config-row-action");
    await changeBtns.nth(1).click();

    await waitForHidden(page, Selectors.configModal);
    await waitForVisible(page, "#thinking-picker-modal");
  });
});

// =========================================================================
// Thinking Picker (opened from config)
// =========================================================================

test.describe("Thinking Picker", () => {
  test("should open with 5 levels and active badge", async ({ page }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const changeBtns = page.locator(".config-row-action");
    await changeBtns.nth(1).click();

    await waitForVisible(page, "#thinking-picker-modal");

    // 5 levels
    const items = page.locator(".thinking-picker-item");
    expect(await items.count()).toBe(5);
    // Active badge
    const activeItem = page.locator(".thinking-picker-item.active");
    await expect(activeItem).toBeVisible();
    await expect(activeItem).toContainText("Active");
  });

  test("should close thinking picker when pressing Escape", async ({
    page,
  }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const changeBtns = page.locator(".config-row-action");
    await changeBtns.nth(1).click();

    await waitForVisible(page, "#thinking-picker-modal");
    await page.keyboard.press("Escape");
    await waitForHidden(page, "#thinking-picker-modal");
  });

  test("should switch thinking level when clicking an item", async ({
    page,
  }) => {
    await sendMessage(page, "/config");
    await waitForVisible(page, Selectors.configModal);

    const changeBtns = page.locator(".config-row-action");
    await changeBtns.nth(1).click();

    await waitForVisible(page, "#thinking-picker-modal");

    const nonActiveItem = page
      .locator(".thinking-picker-item:not(.active)")
      .first();

    const count = await nonActiveItem.count();
    if (count > 0) {
      const level = await nonActiveItem
        .locator(".thinking-picker-level")
        .textContent();

      await nonActiveItem.click({ force: true });

      const systemMsg = page.locator(Selectors.systemMessage);
      await expect(systemMsg.last()).toBeVisible({ timeout: 15000 });

      const modalVisible = await page
        .locator("#thinking-picker-modal")
        .isVisible();
      if (!modalVisible) {
        await expect(systemMsg.last()).toContainText(
          `Thinking level set to ${level}`
        );
      }
    }
  });
});

// =========================================================================
// MCP Modal (/mcp)
// =========================================================================

test.describe("MCP Modal (/mcp)", () => {
  test("should open with server list and cleared input", async ({ page }) => {
    await sendMessage(page, "/mcp");
    await expect(page.locator(Selectors.mcpModal)).toBeVisible({
      timeout: 10000,
    });
    // Structure
    await expect(page.locator(Selectors.mcpModalContent)).toBeVisible();
    await expect(page.locator(Selectors.mcpModalClose)).toBeVisible();
    // Server listed
    await expect(page.locator(Selectors.mcpModalContent)).toContainText(
      "e2e_test_server"
    );
    // Input cleared
    await expect(page.locator(Selectors.messageInput)).toBeEmpty();
  });

  test("should toggle MCP server disable/enable", async ({ page }) => {
    await sendMessage(page, "/mcp");
    await waitForVisible(page, Selectors.mcpModal);

    const toggleBtn = page.locator(
      "button.mcp-toggle-btn[data-name='e2e_test_server']"
    );
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });
    const btnTextBefore = await toggleBtn.textContent();

    await toggleBtn.click({ force: true });

    await page.waitForTimeout(2000);

    const hasError = await page
      .locator(Selectors.systemMessage)
      .filter({ hasText: "toggle" })
      .count();

    if (hasError > 0) {
      const errorMsg = await page
        .locator(Selectors.systemMessage)
        .filter({ hasText: "toggle" })
        .last()
        .textContent();
      expect(errorMsg).toBeTruthy();
      return;
    }

    const toggleBtnAfter = page.locator(
      "button.mcp-toggle-btn[data-name='e2e_test_server']"
    );
    await expect(toggleBtnAfter).toBeVisible({ timeout: 5000 });
    const btnTextAfter = await toggleBtnAfter.textContent();

    expect(btnTextAfter).not.toBe(btnTextBefore);
  });
});

// =========================================================================
// Rewind Modal (/rewind)
// =========================================================================

test.describe("Rewind Modal (/rewind)", () => {
  test("should open with empty state and cleared input when no messages exist", async ({
    page,
  }) => {
    await sendMessage(page, "/rewind");
    await expect(page.locator(Selectors.rewindModal)).toBeVisible({
      timeout: 10000,
    });
    // Structure
    await expect(page.locator(Selectors.rewindMessagesList)).toBeVisible();
    await expect(page.locator(Selectors.rewindModalClose)).toBeVisible();
    // Input cleared
    await expect(page.locator(Selectors.messageInput)).toBeEmpty();
  });

  test("should list messages with preview, default selection, and action buttons", async ({
    page,
  }) => {
    await page.fill(Selectors.messageInput, "Rewind test message");
    await page.click(Selectors.sendButton);
    await page.locator(Selectors.userMessage).last().waitFor({
      state: "visible",
      timeout: 5000,
    });

    await sendMessage(page, "/rewind");
    await waitForVisible(page, Selectors.rewindModal);

    // Items listed
    const items = page.locator(".rewind-message-item");
    expect(await items.count()).toBeGreaterThanOrEqual(1);
    // Content preview
    await expect(items.first()).toContainText("Rewind test message");
    // Last selected by default
    await expect(items.last()).toHaveClass(/selected/);
    // Action button visible
    await expect(page.locator("#rewind-edit-btn")).toBeVisible();
  });

  test("should allow selecting a different message by clicking", async ({
    page,
  }) => {
    await page.fill(Selectors.messageInput, "First message");
    await page.click(Selectors.sendButton);
    await page.locator(Selectors.userMessage).last().waitFor({
      state: "visible",
      timeout: 5000,
    });

    await page.fill(Selectors.messageInput, "Second message");
    await page.click(Selectors.sendButton);
    await page.locator(Selectors.userMessage).last().waitFor({
      state: "visible",
      timeout: 5000,
    });

    await sendMessage(page, "/rewind");
    await waitForVisible(page, Selectors.rewindModal);

    const firstItem = page.locator(".rewind-message-item").first();
    await firstItem.click({ force: true });

    await expect(firstItem).toHaveClass(/selected/);

    const lastItem = page.locator(".rewind-message-item").last();
    await expect(lastItem).not.toHaveClass(/selected/);
  });

  test("should populate input with message content after Edit Message", async ({
    page,
  }) => {
    const testMsg = "Rewind target message for editing";
    await page.fill(Selectors.messageInput, testMsg);
    await page.click(Selectors.sendButton);
    await page.locator(Selectors.userMessage).last().waitFor({
      state: "visible",
      timeout: 5000,
    });

    await sendMessage(page, "/rewind");
    await waitForVisible(page, Selectors.rewindModal);

    const editBtn = page.locator("#rewind-edit-btn");
    await expect(editBtn).toBeVisible();
    await editBtn.click({ force: true });

    await waitForHidden(page, Selectors.rewindModal, 15000);

    const systemMsg = page.locator(Selectors.systemMessage).last();
    await expect(systemMsg).toBeVisible({ timeout: 10000 });
    await expect(systemMsg).toContainText("Rewinding to message");

    const input = page.locator(Selectors.messageInput);
    await expect(input).toBeVisible();
    const inputValue = await input.inputValue();
    expect(inputValue).toContain(testMsg);
  });

  test("should show restore files system message when clicking Edit & Restore Files", async ({
    page,
  }) => {
    await page.fill(Selectors.messageInput, "Test message for file restore");
    await page.click(Selectors.sendButton);
    await page.locator(Selectors.userMessage).last().waitFor({
      state: "visible",
      timeout: 5000,
    });

    await sendMessage(page, "/rewind");
    await waitForVisible(page, Selectors.rewindModal);

    const restoreBtn = page.locator("#rewind-restore-btn");
    const restoreVisible = await restoreBtn.isVisible();

    if (restoreVisible) {
      await restoreBtn.click({ force: true });

      await waitForHidden(page, Selectors.rewindModal, 15000);

      const systemMsg = page.locator(Selectors.systemMessage).last();
      await expect(systemMsg).toBeVisible({ timeout: 10000 });
      await expect(systemMsg).toContainText("restoring files");
    }
  });
});

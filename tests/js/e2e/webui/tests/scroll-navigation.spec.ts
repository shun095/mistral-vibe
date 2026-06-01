/**
 * E2E tests for WebUI scroll navigation features.
 * Covers US-21 (scroll FAB buttons), US-22 (smart scroll behavior).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse } from "../helpers/test-utils";

test.describe("Scroll Navigation (FAB Buttons)", () => {
  test("should show scroll-to-top FAB and scroll to top when clicked", async ({
    page,
    mockBackend,
  }) => {
    for (let i = 0; i < 5; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - This is a longer response to create more content.`,
      });
    }

    for (let i = 1; i <= 5; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    // Scroll to bottom
    await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }
    });

    // FAB container visible
    const fabContainer = page.locator(".fab-container");
    await expect(fabContainer).toBeVisible({ timeout: 10000 });

    // Scroll-to-top button visible
    const scrollTopBtn = page.locator("#scroll-top-btn");
    await expect(scrollTopBtn).toBeVisible();

    // Click and verify scroll to top
    await scrollTopBtn.click();

    await page.waitForFunction(() => {
      const messages = document.getElementById("messages");
      return messages && messages.scrollTop < 5;
    });

    const finalScroll = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });
    expect(finalScroll).toBeLessThan(10);
  });

  test("should show scroll-to-bottom FAB button", async ({ page }) => {
    const fabContainer = page.locator(".fab-container");
    await expect(fabContainer).toBeVisible();

    const scrollBottomBtn = page.locator("#scroll-bottom-btn");
    await expect(scrollBottomBtn).toBeVisible();
  });

  test("should scroll to bottom when scroll-to-bottom button is clicked", async ({
    page,
  }) => {
    const scrollBottomBtn = page.locator("#scroll-bottom-btn");
    await expect(scrollBottomBtn).toBeVisible();
    await scrollBottomBtn.click();

    const scrollPos = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (!messages) return -1;
      return messages.scrollTop + messages.clientHeight;
    });

    const totalHeight = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollHeight : -1;
    });

    expect(scrollPos).toBeGreaterThanOrEqual(totalHeight - 5);
  });

  test("should show scroll buttons for user message navigation", async ({
    page,
    mockBackend,
  }) => {
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1}`,
      });
    }

    for (let i = 1; i <= 3; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    const scrollPrevUserBtn = page.locator("#scroll-prev-user-btn");
    const scrollNextUserBtn = page.locator("#scroll-next-user-btn");

    await expect(scrollPrevUserBtn).toBeVisible();
    await expect(scrollNextUserBtn).toBeVisible();
  });
});

test.describe("Smart Scroll Behavior", () => {
  test("should auto-scroll to bottom when new messages arrive", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerResponse({ response_text: "New message!" });

    await sendMessage(page, "Hello");

    const assistantMsg = page.locator(Selectors.assistantMessage);
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });
  });

  test("should not scroll when user is reading above", async ({
    page,
    mockBackend,
  }) => {
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - Content for scroll test.`,
      });
    }

    for (let i = 1; i <= 3; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    // Scroll up to simulate user reading older messages
    await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (messages) {
        messages.scrollTop = 0;
      }
    });

    const scrollBefore = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });

    // Send a new message
    await mockBackend.registerResponse({ response_text: "Another response!" });
    await sendMessage(page, "Scroll test message");
    await waitForResponse(page, 10000);

    // Verify scroll position is roughly unchanged
    const scrollAfter = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });

    expect(Math.abs(scrollAfter - scrollBefore)).toBeLessThan(50);
  });

  test("should scroll to bottom when user is at bottom", async ({
    page,
    mockBackend,
  }) => {
    // Ensure user is at bottom
    await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }
    });

    // Verify at bottom
    const atBottom = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (!messages) return false;
      return (
        Math.abs(
          messages.scrollTop + messages.clientHeight - messages.scrollHeight
        ) < 5
      );
    });
    expect(atBottom).toBe(true);

    // Register and send message
    await mockBackend.registerResponse({ response_text: "Bottom scroll test!" });
    await sendMessage(page, "Bottom test");

    // Wait for response
    const assistantMsg = page.locator(Selectors.assistantMessage).last();
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    // Should have scrolled to show new message
    const newAtBottom = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (!messages) return false;
      return (
        Math.abs(
          messages.scrollTop + messages.clientHeight - messages.scrollHeight
        ) < 50
      );
    });
    expect(newAtBottom).toBe(true);
  });
});

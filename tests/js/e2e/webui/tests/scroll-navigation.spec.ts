/**
 * E2E tests for WebUI scroll navigation features.
 * Covers US-21 (scroll FAB buttons), US-22 (smart scroll behavior).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse } from "../helpers/test-utils";

test.describe("Scroll Navigation (FAB Buttons)", () => {
  test("should show scroll-to-top FAB button when scrolled down", async ({
    page,
    mockBackend,
  }) => {
    // Register multiple responses to create scrollable content
    for (let i = 0; i < 5; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - This is a longer response to create more content.`,
      });
    }

    // Send messages to create scrollable content
    for (let i = 1; i <= 5; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    // Scroll to the bottom to ensure there's content to scroll from
    await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }
    });

    // Wait a moment for scroll position to settle
    await page.waitForTimeout(500);

    // Scroll FAB container should be visible
    const fabContainer = page.locator(".fab-container");
    await expect(fabContainer).toBeVisible();

    // Scroll-to-top button should be visible
    const scrollTopBtn = page.locator("#scroll-top-btn");
    await expect(scrollTopBtn).toBeVisible();
  });

  test("should scroll to top when scroll-to-top button is clicked", async ({
    page,
    mockBackend,
  }) => {
    // Register multiple responses to create scrollable content
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - Scroll test content.`,
      });
    }

    // Send messages
    for (let i = 1; i <= 3; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    // Scroll to bottom via JS (more reliable than waiting for auto-scroll)
    await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }
    });
    await page.waitForTimeout(300);

    // Verify we're at bottom
    const atBottom = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (!messages) return false;
      return Math.abs(messages.scrollTop + messages.clientHeight - messages.scrollHeight) < 5;
    });
    expect(atBottom).toBe(true);

    // Click scroll-to-top button
    const scrollTopBtn = page.locator("#scroll-top-btn");
    await expect(scrollTopBtn).toBeVisible();
    await scrollTopBtn.click();

    // Wait for scroll animation to complete
    await page.waitForTimeout(300);

    // Scroll position should be at or near top
    const finalScroll = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });

    expect(finalScroll).toBeLessThan(10);
  });

  test("should show scroll-to-bottom FAB button", async ({ page }) => {
    // FAB container should be visible
    const fabContainer = page.locator(".fab-container");
    await expect(fabContainer).toBeVisible();

    // Scroll-to-bottom button should be visible
    const scrollBottomBtn = page.locator("#scroll-bottom-btn");
    await expect(scrollBottomBtn).toBeVisible();
  });

  test("should scroll to bottom when scroll-to-bottom button is clicked", async ({
    page,
  }) => {
    // Click scroll-to-bottom button
    const scrollBottomBtn = page.locator("#scroll-bottom-btn");
    await expect(scrollBottomBtn).toBeVisible();
    await scrollBottomBtn.click();

    // Page should scroll to bottom
    const scrollPos = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      if (!messages) return -1;
      return messages.scrollTop + messages.clientHeight;
    });

    // Verify we're at or near the bottom
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
    // Register multiple responses
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1}`,
      });
    }

    // Send multiple messages
    for (let i = 1; i <= 3; i++) {
      await sendMessage(page, `Message ${i}`);
      await waitForResponse(page, 10000);
    }

    // Scroll navigation buttons should be visible
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
    // Register a response
    await mockBackend.registerResponse({ response_text: "New message!" });

    // Send a message
    await sendMessage(page, "Hello");

    // Wait for the response to appear
    const assistantMsg = page.locator(Selectors.assistantMessage);
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    // The page should have scrolled to show the new message
    // This is a basic check - the message should be visible
    await expect(assistantMsg).toBeVisible();
  });

  test("should not scroll when user is reading above", async ({
    page,
    mockBackend,
  }) => {
    // Register multiple responses to create scrollable content
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - Content for scroll test.`,
      });
    }

    // Send multiple messages
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

    // Wait for scroll to settle
    await page.waitForTimeout(500);

    // Record scroll position
    const beforeScroll = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });

    // Register a new response
    await mockBackend.registerResponse({ response_text: "New message while reading" });

    // Send another message
    await sendMessage(page, "Message 4");

    // Wait for response
    await waitForResponse(page, 10000);

    // Scroll position should not have changed significantly
    // (if user was at top, they should stay at top)
    const afterScroll = await page.evaluate(() => {
      const messages = document.getElementById("messages");
      return messages ? messages.scrollTop : -1;
    });

    // Allow small tolerance for layout changes
    expect(Math.abs(afterScroll - beforeScroll)).toBeLessThan(50);
  });

  test("should scroll to bottom when user is at bottom", async ({
    page,
    mockBackend,
  }) => {
    // Register multiple responses
    for (let i = 0; i < 3; i++) {
      await mockBackend.registerResponse({
        response_text: `Response ${i + 1} - Scroll test.`,
      });
    }

    // Send multiple messages
    for (let i = 1; i <= 3; i++) {
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
    await page.waitForTimeout(500);

    // Register a new response
    await mockBackend.registerResponse({ response_text: "New message" });

    // Send another message
    await sendMessage(page, "Message 4");

    // Wait for response
    await waitForResponse(page, 10000);

    // Page should have scrolled to bottom
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
});

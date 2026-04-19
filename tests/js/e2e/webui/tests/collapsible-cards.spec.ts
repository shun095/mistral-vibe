/**
 * E2E tests for collapsible cards toggle feature.
 * Covers US-10 (toggle all cards button).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, callVibeClient } from "../helpers/test-utils";

test.describe("Collapsible Cards Toggle", () => {
  test("should show toggle all cards button in header", async ({ page }) => {
    const toggleBtn = page.locator(Selectors.toggleCardsBtn);
    await expect(toggleBtn).toBeVisible();
  });

  test("should expand all cards when toggleAllCards is called from collapsed state", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call that creates a collapsible card
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read test file");

    // Wait for tool call card to appear (cards start collapsed by default)
    const toolCard = page.locator(".message.tool-call").last();
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Verify card starts collapsed
    await expect(toolCard).toHaveClass(/collapsed/);

    // Call toggleAllCards to expand
    await callVibeClient(page, "toggleAllCards");

    // Verify the card is now expanded
    await expect(toolCard).not.toHaveClass(/collapsed/);
  });

  test("should collapse all cards when toggleAllCards is called from expanded state", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read test file");

    // Wait for tool call card
    const toolCard = page.locator(".message.tool-call").last();
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // First expand (from default collapsed state)
    await callVibeClient(page, "toggleAllCards");
    await expect(toolCard).not.toHaveClass(/collapsed/);

    // Then collapse
    await callVibeClient(page, "toggleAllCards");

    // Verify the card is now collapsed
    await expect(toolCard).toHaveClass(/collapsed/);
  });

  test("should update toggle button icon based on collapse state", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read test file");

    // Wait for tool call card
    const toolCard = page.locator(".message.tool-call").last();
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    const toggleBtn = page.locator(Selectors.toggleCardsBtn);
    const icon = toggleBtn.locator(".material-symbols-rounded");

    // Icon should initially be "add" (collapse all) since cards start collapsed
    let iconText = await icon.textContent();
    expect(iconText).toBe("add");

    // Expand all cards
    await callVibeClient(page, "toggleAllCards");
    iconText = await icon.textContent();
    expect(iconText).toBe("remove");

    // Collapse all cards
    await callVibeClient(page, "toggleAllCards");
    iconText = await icon.textContent();
    expect(iconText).toBe("add");
  });

  test("should apply collapse preference to new cards created after toggle", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call for the first card
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test1.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read first file");

    // Wait for first tool call card
    const firstCard = page.locator(".message.tool-call").last();
    await expect(firstCard).toBeVisible({ timeout: 15000 });

    // First expand, then collapse to set _preferCollapsed = true
    await callVibeClient(page, "toggleAllCards"); // expand
    await callVibeClient(page, "toggleAllCards"); // collapse

    // Register a second tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test2.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read second file");

    // Wait for second tool call card
    const secondCard = page.locator(".message.tool-call").last();
    await expect(secondCard).toBeVisible({ timeout: 15000 });

    // Verify the second card is collapsed (respecting _preferCollapsed)
    await expect(secondCard).toHaveClass(/collapsed/);
  });

  test("should handle multiple cards with toggleAllCards", async ({
    page,
    mockBackend,
  }) => {
    // Register first tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({ path: "test1.txt", offset: 0, limit: 100 })
    );
    await sendMessage(page, "Read first file");
    const firstCard = page.locator(".message.tool-call").last();
    await expect(firstCard).toBeVisible({ timeout: 15000 });

    // Register second tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({ path: "test2.txt", offset: 0, limit: 100 })
    );
    await sendMessage(page, "Read second file");
    const secondCard = page.locator(".message.tool-call").last();
    await expect(secondCard).toBeVisible({ timeout: 15000 });

    // Wait for third tool call
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({ path: "test3.txt", offset: 0, limit: 100 })
    );
    await sendMessage(page, "Read third file");
    await expect(page.locator(".message.tool-call").last()).toBeVisible({ timeout: 15000 });

    // All cards should start collapsed
    const allCards = page.locator(".message.tool-call");
    await expect(allCards).toHaveCount(3);
    for (let i = 0; i < 3; i++) {
      await expect(allCards.nth(i)).toHaveClass(/collapsed/);
    }

    // Expand all cards
    await callVibeClient(page, "toggleAllCards");

    // All cards should be expanded
    for (let i = 0; i < 3; i++) {
      await expect(allCards.nth(i)).not.toHaveClass(/collapsed/);
    }

    // Collapse all cards
    await callVibeClient(page, "toggleAllCards");

    // All cards should be collapsed again
    for (let i = 0; i < 3; i++) {
      await expect(allCards.nth(i)).toHaveClass(/collapsed/);
    }
  });
});

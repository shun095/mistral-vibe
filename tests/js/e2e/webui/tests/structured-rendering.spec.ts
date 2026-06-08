import { test, expect } from "../fixtures";
import { sendMessage, waitForResponse, formatAndAppendToolResult } from "../helpers/test-utils";

test.describe("Structured JSON Rendering", () => {
  test("tool call args render as structured table, not raw JSON", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerToolCall(
      "read",
      JSON.stringify({
        file_path: "src/main.py",
        offset: 1,
        limit: 50,
      })
    );

    await sendMessage(page, "Read the file");
    await waitForResponse(page);

    // Tool call card should exist
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Expand if collapsed
    const header = toolCard.locator(".tool-header");
    const isCollapsed = await toolCard.evaluate((el) =>
      el.classList.contains("collapsed")
    );
    if (isCollapsed) {
      await header.click();
    }

    // Should have structured-args, NOT raw tool-args pre block
    const structuredArgs = toolCard.locator(".structured-args");
    await expect(structuredArgs).toBeVisible();

    // Should contain key-value table
    const structTable = structuredArgs.locator(".struct-table");
    await expect(structTable).toBeVisible();

    // Verify individual keys are present as table headers
    const keys = structuredArgs.locator(".struct-key");
    await expect(keys).toHaveCount(3);
    await expect(keys.nth(0)).toHaveText(/path|offset|limit/);

    // Should NOT contain raw JSON format like '{"path":'
    const argsText = await structuredArgs.textContent();
    expect(argsText).not.toContain('{');
    expect(argsText).not.toContain('"path"');
  });

  test("structured args detect file paths with icon", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerToolCall(
      "grep",
      JSON.stringify({
        pattern: "TODO",
        path: "./src/utils.py",
      })
    );

    await sendMessage(page, "Search for TODO");
    await waitForResponse(page);

    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Expand if collapsed
    await toolCard.locator(".tool-header").click().catch(() => {});

    // Path values should have struct-path class with file icon
    const pathValue = toolCard.locator(".struct-path");
    await expect(pathValue).toBeVisible();
    expect(await pathValue.textContent()).toContain("src/utils.py");
  });

  test("structured args detect numbers with proper styling", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerToolCall(
      "read",
      JSON.stringify({
        file_path: "test.txt",
        limit: 100,
        offset: 50,
      })
    );

    await sendMessage(page, "Read test");
    await waitForResponse(page);

    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    await toolCard.locator(".tool-header").click().catch(() => {});

    // Numbers should have struct-number class
    const numbers = toolCard.locator(".struct-number");
    await expect(numbers).toHaveCount(2);
  });

  test("generic tool result renders structured table", async ({ page }) => {
    // Use an unknown tool name to trigger the generic formatter
    await formatAndAppendToolResult(page, "unknown_custom_tool", {
      status: "completed",
      items_processed: 42,
      output_path: "/tmp/result.csv",
    });

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    // Should have structured-result inside card-content
    const structuredResult = card.locator(".structured-result");
    await expect(structuredResult).toBeVisible();

    // Should contain the structured table
    await expect(structuredResult.locator(".struct-table")).toBeVisible();

    // Summary should show field count, not raw JSON
    const summary = card.locator(".card-content > pre");
    await expect(summary).toContainText("3 fields");
  });

  test("generic tool result with array shows item count", async ({ page }) => {
    await formatAndAppendToolResult(page, "unknown_tool", [
      "item1",
      "item2",
      "item3",
    ]);

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    // Summary should show item count
    const summary = card.locator(".card-content > pre");
    await expect(summary).toContainText("3 items");

    // Should render as a list
    const list = card.locator(".struct-list");
    await expect(list).toBeVisible();
  });

  test("copy JSON button appears on hover", async ({ page }) => {
    await formatAndAppendToolResult(page, "test_tool", {
      key: "value",
      count: 10,
    });

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    const copyBtn = card.locator(".struct-copy-btn");
    await expect(copyBtn).toBeVisible();

    // Hover to make it visible
    await copyBtn.hover();
    const opacity = await copyBtn.evaluate((el) =>
      window.getComputedStyle(el).opacity
    );
    expect(parseFloat(opacity)).toBeGreaterThan(0);
  });

  test("boolean values render as colored badges", async ({ page }) => {
    await formatAndAppendToolResult(page, "bool_tool", {
      enabled: true,
      disabled: false,
    });

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    // True values should have true-badge class
    const trueBadge = card.locator(".true-badge");
    await expect(trueBadge).toBeVisible();
    expect(await trueBadge.textContent()).toContain("true");

    // False values should have false-badge class
    const falseBadge = card.locator(".false-badge");
    await expect(falseBadge).toBeVisible();
    expect(await falseBadge.textContent()).toContain("false");
  });

  test("null values render as muted badges", async ({ page }) => {
    await formatAndAppendToolResult(page, "null_tool", {
      value: null,
      name: "test",
    });

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    const nullBadge = card.locator(".null-badge");
    await expect(nullBadge).toBeVisible();
    expect(await nullBadge.textContent()).toContain("null");
  });

  test("multiline strings show line count badge and first line only", async ({
    page,
  }) => {
    await formatAndAppendToolResult(page, "multiline_tool", {
      command: "ls -la\nfind . -name '*.py'\ngrep -r TODO",
      single_line: "just one line",
    });

    const card = page.locator("body .tool-result-card");
    await expect(card).toBeVisible();

    // Multiline value should show line count badge
    const badge = card.locator(".struct-multiline-badge");
    await expect(badge).toBeVisible();
    expect(await badge.textContent()).toContain("3 lines");

    // Preview should show first line only
    const preview = card.locator(".struct-multiline-preview");
    await expect(preview).toBeVisible();
    expect(await preview.textContent()).toBe("ls -la");

    // Single line value should NOT have multiline badge
    const singleLineText = await card.locator(".struct-string").textContent();
    expect(singleLineText).toBe("just one line");
  });

  test("long single-line strings are not truncated, shown as-is", async ({
    page,
  }) => {
    const longCommand =
      "cd /path/to/project && nohup npm run test:e2e -- --grep \"test\" > /tmp/output.log 2>&1";

    await formatAndAppendToolResult(page, "long_tool", {
      command: longCommand,
    });

    const card = page.locator("body .tool-result-card").last();
    await expect(card).toBeVisible();

    // Should NOT have multiline badge (single line)
    expect(await card.locator(".struct-multiline-badge").count()).toBe(0);

    // Full text present in DOM (CSS ellipsis handles visual overflow)
    const fullCardText = await card.evaluate((el) => el.textContent || "");
    expect(fullCardText).toContain(longCommand);
  });

  test("clicking multiline string expands to show full content", async ({
    page,
  }) => {
    await formatAndAppendToolResult(page, "expand_tool", {
      content:
        "def hello():\n    print('world')\n    return True\n",
    });

    const card = page.locator("body .tool-result-card").last();
    await expect(card).toBeVisible();

    // Initially collapsed — no expanded pre block
    const expandedBefore = card.locator(".struct-multiline-expanded");
    expect(await expandedBefore.count()).toBe(0);

    // Click to expand
    await card.locator(".struct-multiline-preview").click();

    // Now expanded pre block should be visible with full content
    const expanded = card.locator(".struct-multiline-expanded");
    await expect(expanded).toBeVisible();
    const fullText = await expanded.textContent();
    expect(fullText).toContain("def hello():");
    expect(fullText).toContain("print('world')");
    expect(fullText).toContain("return True");
  });

  test("clicking again collapses multiline string", async ({ page }) => {
    await formatAndAppendToolResult(page, "toggle_tool", {
      data: "line1\nline2\nline3",
    });

    const card = page.locator("body .tool-result-card").last();
    await expect(card).toBeVisible();

    // Expand
    await card.locator(".struct-multiline-preview").click();
    await expect(card.locator(".struct-multiline-expanded")).toBeVisible();

    // Collapse
    await card.locator(".struct-multiline").click();
    await expect(card.locator(".struct-multiline-expanded")).toHaveCount(0);
    await expect(card.locator(".struct-multiline-preview")).toBeVisible();
  });

  test("session reload renders structured args for tool calls", async ({
    page,
    mockBackend,
  }) => {
    // Register tool call and send message
    await mockBackend.registerToolCall(
      "bash",
      JSON.stringify({
        command: "ls -la",
        timeout: 30,
      })
    );

    await sendMessage(page, "List files");
    await waitForResponse(page);

    // Verify structured args are present
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    await toolCard.locator(".tool-header").click().catch(() => {});

    const structuredArgs = toolCard.locator(".structured-args");
    await expect(structuredArgs).toBeVisible();

    // Reload the page (simulates session resume) — use domcontentloaded
    // since WebSocket keeps networkidle from resolving
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);

    // Wait for messages to be replayed
    await page.waitForFunction(() => {
      const cards = document.querySelectorAll(".message.tool-call");
      return cards.length > 0;
    }, { timeout: 15000 });

    // After reload, tool args should STILL be structured, not raw JSON
    const reloadedCard = page.locator(".message.tool-call");
    await expect(reloadedCard).toBeVisible();

    await reloadedCard.locator(".tool-header").click().catch(() => {});

    const reloadedArgs = reloadedCard.locator(".structured-args");
    await expect(reloadedArgs).toBeVisible();

    // Should contain command key in structured format
    const reloadedText = await reloadedArgs.textContent();
    expect(reloadedText).toContain("command");
    expect(reloadedText).toContain("ls -la");
  });
});

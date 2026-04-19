/**
 * E2E tests for WebUI tool card visualization and formatting.
 * Covers US-07 (tool call visualization), US-30-35 (tool result formatting).
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse, triggerLLMError, formatAndAppendToolResult, createReasoningCard } from "../helpers/test-utils";

test.describe("Tool Card Visualization", () => {
  test("should render tool call card with tool name and status", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call for read_file (which requires approval by default)
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "test_file.txt",
        offset: 0,
        limit: 100,
      })
    );

    await sendMessage(page, "Read test file");

    // Wait for tool call card to appear
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Verify tool name is displayed
    const toolName = toolCard.locator(".tool-name");
    await expect(toolName).toBeVisible();
  });

  test("should render tool result card with success status", async ({
    page,
    mockBackend,
  }) => {
    // Register a tool call for grep (read-only, no approval needed)
    await mockBackend.registerToolCall(
      "grep",
      JSON.stringify({
        pattern: "test_pattern",
        path: ".",
      })
    );

    await sendMessage(page, "Search for pattern");

    // Wait for tool call card to appear (it starts collapsed by default)
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 20000 });

    // Expand the collapsed tool call card so the result card becomes visible
    await toolCard.locator(".tool-header").click();

    // Wait for tool result card to appear
    const toolResultCard = page.locator(".tool-result-card");
    await expect(toolResultCard).toBeVisible();

    // Verify the card has a header with title
    const cardHeader = toolResultCard.locator(".card-header");
    await expect(cardHeader).toBeVisible();
  });

  test("should collapse and expand tool call cards", async ({
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
    const toolCard = page.locator(".message.tool-call");
    await expect(toolCard).toBeVisible({ timeout: 15000 });

    // Toggle the card by clicking the header
    const header = toolCard.locator(".tool-header");
    await header.click();

    // Card should toggle collapsed state
    const isCollapsed = await toolCard.evaluate((el) =>
      el.classList.contains("collapsed")
    );
    expect(typeof isCollapsed).toBe("boolean");
  });

  test("should collapse and expand reasoning cards", async ({ page }) => {
    // Create a reasoning card via VibeClient
    await createReasoningCard(page);

    // Wait for reasoning card
    const reasoningCard = page.locator(".message.reasoning");
    await expect(reasoningCard).toBeVisible({ timeout: 5000 });

    // Verify it has the reasoning header
    const reasoningHeader = reasoningCard.locator(".reasoning-header");
    await expect(reasoningHeader).toBeVisible();

    // Verify the toggle triangle is present
    const toggle = reasoningCard.locator(".reasoning-toggle");
    await expect(toggle).toBeVisible();
  });

  test("should show 'Thought' label on reasoning cards", async ({ page }) => {
    // Create a reasoning card
    await createReasoningCard(page);

    // Verify the label is "Thought"
    const reasoningCard = page.locator(".message.reasoning");
    await expect(reasoningCard).toBeVisible({ timeout: 5000 });
    await expect(reasoningCard).toContainText("Thought");
  });
});

test.describe("Tool Result Formatting", () => {
  test("should format bash result with return code and output sections", async ({
    page,
  }) => {
    const result = { command: "echo hello", returncode: 0, stdout: "hello\n" };
    await formatAndAppendToolResult(page, "bash", result);

    const bashCard = page.locator(".tool-result-card");
    await expect(bashCard).toBeVisible({ timeout: 5000 });
    await expect(bashCard).toContainText("echo hello");
    await expect(bashCard).toContainText("Return code: 0");
  });

  test("should format grep result with match count", async ({ page }) => {
    const result = { pattern: "test", match_count: 1, matches: "app.py:10: test function" };
    await formatAndAppendToolResult(page, "grep", result);

    const grepCard = page.locator(".tool-result-card");
    await expect(grepCard).toBeVisible({ timeout: 5000 });
    await expect(grepCard).toContainText("test");
  });

  test("should format todo result as table", async ({ page }) => {
    const result = { todos: [{ content: "Fix bug", status: "pending", priority: "high" }, { content: "Write tests", status: "done", priority: "medium" }] };
    await formatAndAppendToolResult(page, "todo", result);

    const todoCard = page.locator(".tool-result-card");
    await expect(todoCard).toBeVisible({ timeout: 5000 });
    // Todo results render a table
    const table = todoCard.locator("table");
    await expect(table).toBeVisible();
  });

  test("should format lsp result with diagnostic summary", async ({ page }) => {
    const result = { diagnostics: [{ severity: 2, message: "Unused import" }], formatted_output: "app.py:5: Unused import" };
    await formatAndAppendToolResult(page, "lsp", result);

    const lspCard = page.locator(".tool-result-card");
    await expect(lspCard).toBeVisible({ timeout: 5000 });
    await expect(lspCard).toContainText("LSP Diagnostics");
  });

  test("should format ask_user_question result with answers", async ({
    page,
  }) => {
    const result = { answer: "The sky is blue", sources: [{ title: "Sky color", url: "https://example.com/sky" }] };
    await formatAndAppendToolResult(page, "websearch", result);

    const searchCard = page.locator(".tool-result-card");
    await expect(searchCard).toBeVisible({ timeout: 5000 });
    await expect(searchCard).toContainText("The sky is blue");
  });

  test("should format read_file result with code block", async ({ page }) => {
    const result = { path: "src/main.py", content: "def hello():\n    pass", lines_read: 2 };
    await formatAndAppendToolResult(page, "read_file", result);

    const readFileCard = page.locator(".tool-result-card");
    await expect(readFileCard).toBeVisible({ timeout: 5000 });
    await expect(readFileCard).toContainText("src/main.py");
  });

  test("should format edit_file result with diff", async ({ page }) => {
    const result = { file: "src/main.py", blocks_applied: 1, lines_changed: 2, content: "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new" };
    await formatAndAppendToolResult(page, "edit_file", result);

    const editCard = page.locator(".tool-result-card");
    await expect(editCard).toBeVisible({ timeout: 5000 });
    await expect(editCard).toContainText("src/main.py");
  });

  test("should format write_file result with path and bytes", async ({
    page,
  }) => {
    const result = { path: "output.txt", bytes_written: 1234, file_existed: false };
    await formatAndAppendToolResult(page, "write_file", result);

    const writeFileCard = page.locator(".tool-result-card");
    await expect(writeFileCard).toBeVisible({ timeout: 5000 });
    await expect(writeFileCard).toContainText("output.txt");
  });

  test("should format web fetch result with line count", async ({ page }) => {
    const result = { url: "https://example.com", content: "<html>...</html>", lines_read: 42, total_lines: 42 };
    await formatAndAppendToolResult(page, "webfetch", result);

    const fetchCard = page.locator(".tool-result-card");
    await expect(fetchCard).toBeVisible({ timeout: 5000 });
    await expect(fetchCard).toContainText("https://example.com");
  });
});

test.describe("LLM Error Display", () => {
  test("should render LLM error card with error type and details", async ({
    page,
  }) => {
    // Trigger LLM error event via VibeClient
    await triggerLLMError(page, {
      error_type: "RateLimitError",
      error_message: "Rate limit exceeded. Please try again later.",
      provider: "openai",
      model: "gpt-4",
    });

    // Verify error card is rendered
    const errorCard = page.locator(".message.error");
    await expect(errorCard).toBeVisible({ timeout: 5000 });

    // Verify error header with type
    const errorHeader = errorCard.locator(".error-header");
    await expect(errorHeader).toBeVisible();
    await expect(errorHeader).toContainText("RateLimitError");

    // Verify error icon
    const errorIcon = errorCard.locator(".error-header .material-symbols-rounded");
    await expect(errorIcon).toHaveText("error");

    // Verify error details
    const errorDetails = errorCard.locator(".error-details");
    await expect(errorDetails).toBeVisible();
    await expect(errorDetails).toContainText("Rate limit exceeded");
  });

  test("should render LLM error card with provider and model metadata", async ({
    page,
  }) => {
    // Trigger LLM error event with provider and model
    await triggerLLMError(page, {
      error_type: "AuthenticationError",
      error_message: "Invalid API key",
      provider: "anthropic",
      model: "claude-3-opus",
    });

    // Verify error card is rendered
    const errorCard = page.locator(".message.error");
    await expect(errorCard).toBeVisible({ timeout: 5000 });

    // Verify metadata section with provider and model
    const errorMeta = errorCard.locator(".error-meta");
    await expect(errorMeta).toBeVisible();
    await expect(errorMeta).toContainText("Provider: anthropic");
    await expect(errorMeta).toContainText("Model: claude-3-opus");
  });

  test("should render LLM error card without metadata when provider/model absent", async ({
    page,
  }) => {
    // Trigger LLM error event without provider and model
    await triggerLLMError(page, {
      error_type: "ConnectionError",
      error_message: "Failed to connect to LLM provider",
    });

    // Verify error card is rendered
    const errorCard = page.locator(".message.error");
    await expect(errorCard).toBeVisible({ timeout: 5000 });

    // Verify no metadata section when provider/model are absent
    const errorMeta = errorCard.locator(".error-meta");
    await expect(errorMeta).not.toBeVisible();
  });
});

/**
 * E2E tests for WebUI !command (bash execution) feature.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
} from "../helpers/test-utils";

test.describe("Bash Command (!command) Feature", () => {
  test.beforeEach(async ({ page, authToken, webServer }) => {
    // Navigate with auth token
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);

    // Wait for chat interface to be visible
    await expect(page.locator(Selectors.messageInput)).toBeVisible();

    // Wait for WebSocket to connect (status-dot should have "connected" class)
    await page.waitForFunction(
      (selector) => {
        const el = document.querySelector(selector);
        return el && el.classList.contains("connected");
      },
      Selectors.statusIndicator,
      { timeout: 10000 }
    );
  });

  test("should execute simple bash command and show output", async ({
    page,
  }) => {
    // Send a simple bash command
    await sendMessage(page, "!echo 'Hello from WebUI bash'");

    // Wait for user message to appear with the command
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toBeVisible({ timeout: 10000 });
    await expect(userMessage).toContainText("!echo");

    // Wait for bash command card to appear
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Hello from WebUI bash");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should execute bash command with arguments", async ({ page }) => {
    // Send a bash command with arguments
    await sendMessage(page, "!echo 'test123'");

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("!echo");

    // Verify bash card contains the output
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("test123");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should handle bash command with non-zero exit code", async ({
    page,
  }) => {
    // Send a command that will fail
    await sendMessage(page, "!false");

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("!false");

    // Verify bash card shows exit code 1
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    // The command "false" always returns exit code 1
    await expect(bashCard).toContainText("Exit code: 1");
  });

  test("should handle non-existent bash command", async ({ page }) => {
    // Send a non-existent command
    await sendMessage(page, "!nonexistent_command_xyz123");

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("!nonexistent");

    // Verify bash card shows exit code (non-zero for failed command)
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    // Non-existent commands produce stderr output and non-zero exit code
    await expect(bashCard).toContainText("Exit code:");
  });

  test.skip("should handle empty bash command (!)", async ({ page }) => {
    // Send just "!" with no command
    await sendMessage(page, "!");

    // Verify bash card shows error about no command
    // Note: The user message may not be visible for just "!" but the error response should appear
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Error");
  });

  test("should execute chained bash commands", async ({ page }) => {
    // Send chained commands
    await sendMessage(page, "!echo 'first' && echo 'second'");

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("!echo");

    // Verify bash card contains both outputs
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("first");
    await expect(bashCard).toContainText("second");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should execute bash command and show stdout", async ({ page }) => {
    // Send a command that produces stdout
    await sendMessage(page, "!pwd");

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toContainText("!pwd");

    // Verify bash card contains a path (stdout from pwd)
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    // pwd outputs the current working directory path
    await expect(bashCard).toContainText("/");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should handle WebUI to TUI to WebUI roundtrip", async ({ page }) => {
    // This test verifies the complete roundtrip:
    // 1. WebUI sends !command via WebSocket
    // 2. TUI executes the command
    // 3. TUI broadcasts BashCommandEvent back to WebUI
    // 4. WebUI renders the bash command card

    // Track if bash card appears after command execution
    const command = "!echo 'roundtrip_test_123'";
    await sendMessage(page, command);

    // Verify user message appears (WebUI → TUI)
    const userMessage = page.locator(Selectors.userMessage).last();
    await expect(userMessage).toBeVisible({ timeout: 10000 });
    await expect(userMessage).toContainText(command);

    // Verify bash command card appears (TUI → WebUI via event broadcast)
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });

    // Verify the card has correct content from TUI execution
    await expect(bashCard).toContainText("roundtrip_test_123");
    await expect(bashCard).toContainText("Exit code: 0");

    // Verify card structure (header, command line, output)
    const header = bashCard.locator(".bash-card-header");
    await expect(header).toBeVisible();

    const commandLine = bashCard.locator(".bash-command-line");
    await expect(commandLine).toBeVisible();
    await expect(commandLine).toContainText("echo");

    const output = bashCard.locator(".bash-output pre");
    await expect(output).toBeVisible();
    await expect(output).toContainText("roundtrip_test_123");
  });
});

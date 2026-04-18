/**
 * E2E tests for WebUI !command (bash execution) feature.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  sendMessage,
} from "../helpers/test-utils";

test.describe("Bash Command (!command) Feature", () => {
  test("should execute simple bash command and show output", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // Send a simple bash command
    const command = "!echo 'simple_bash_test_789'";
    await sendMessage(page, command);

    // Wait for user message to appear with the specific command text
    const userMessage = page.locator(Selectors.userMessage).filter({ hasText: "simple_bash_test_789" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    // Wait for bash command card to appear
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "simple_bash_test_789" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should execute bash command with arguments", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send a bash command with arguments
    const command = "!echo 'bash_args_test_unique_456'";
    await sendMessage(page, command);

    // Verify user message
    const userMessage = page.locator(Selectors.userMessage).filter({ hasText: "bash_args_test_unique_456" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    // Verify bash card contains the output
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "bash_args_test_unique_456" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should handle bash command with non-zero exit code", async ({
    page,
  }) => {
    // Page is already loaded with auth by fixture
    // Send a command that will fail
    await sendMessage(page, "!exit 1");

    // Wait for the bash card with exit code 1 to appear
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "Exit code: 1" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
  });

  test("should handle non-existent bash command", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send a non-existent command
    await sendMessage(page, "!nonexistent_command_xyz789_unique");

    // Wait for a bash card to appear (non-existent commands produce stderr output and non-zero exit code)
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "Exit code:" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
  });

  test.skip("should handle empty bash command (!)", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send just "!" with no command
    await sendMessage(page, "!");

    // Verify bash card shows error about no command
    // Note: The user message may not be visible for just "!" but the error response should appear
    const bashCard = page.locator(Selectors.bashCommand).last();
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Error");
  });

  test("should execute chained bash commands", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Send chained commands
    await sendMessage(page, "!echo 'chain_first_abc' && echo 'chain_second_def'");

    // Verify bash card contains both outputs
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "chain_first_abc" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("chain_second_def");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should execute bash command and show stdout", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // Get initial count of bash cards
    const initialCount = await page.locator(Selectors.bashCommand).count();

    // Send a command that produces stdout
    await sendMessage(page, "!pwd");

    // Wait for a new bash card to appear
    await page.waitForFunction(
      (data: { selector: string; count: number }) => {
        return document.querySelectorAll(data.selector).length > data.count;
      },
      { selector: Selectors.bashCommand, count: initialCount }
    );

    // Get the new bash card (the one after the initial count)
    const bashCards = page.locator(Selectors.bashCommand);
    const newBashCard = bashCards.nth(initialCount);

    await expect(newBashCard).toBeVisible({ timeout: 10000 });
    await expect(newBashCard).toContainText("Exit code: 0");
    // pwd outputs the current working directory path
    await expect(newBashCard).toContainText("/");
  });

  test("should handle WebUI to TUI to WebUI roundtrip", async ({ page }) => {
    // Page is already loaded with auth by fixture
    // This test verifies the complete roundtrip:
    // 1. WebUI sends !command via WebSocket
    // 2. TUI executes the command
    // 3. TUI broadcasts BashCommandEvent back to WebUI
    // 4. WebUI renders the bash command card

    const command = "!echo 'roundtrip_test_unique_final'";
    await sendMessage(page, command);

    // Verify user message appears (WebUI → TUI)
    const userMessage = page.locator(Selectors.userMessage).filter({ hasText: "roundtrip_test_unique_final" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    // Verify bash command card appears (TUI → WebUI via event broadcast)
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "roundtrip_test_unique_final" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });

    // Verify the card has correct content from TUI execution
    await expect(bashCard).toContainText("Exit code: 0");

    // Verify card structure (header, command line, output)
    const header = bashCard.locator(".bash-card-header");
    await expect(header).toBeVisible();

    const commandLine = bashCard.locator(".bash-command-line");
    await expect(commandLine).toBeVisible();
    await expect(commandLine).toContainText("echo");

    const output = bashCard.locator(".bash-output pre");
    await expect(output).toBeVisible();
    await expect(output).toContainText("roundtrip_test_unique_final");
  });

  test("should execute double-bang bash command (!!)", async ({ page }) => {
    // Double-bang (!!command) is an alias for single-bang (!command)
    await sendMessage(page, "!!echo 'double_bang_test_xyz'");

    // Verify user message appears
    const userMessage = page.locator(Selectors.userMessage).filter({ hasText: "double_bang_test_xyz" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    // Verify bash command card appears
    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "double_bang_test_xyz" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Exit code: 0");
  });
});

/**
 * E2E tests for WebUI !command (bash execution) feature.
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage } from "../helpers/test-utils";

test.describe("Bash Command (!command) Feature", () => {
  test("should execute simple bash command and show output", async ({
    page,
  }) => {
    const command = "!echo 'simple_bash_test_789'";
    await sendMessage(page, command);

    const userMessage = page
      .locator(Selectors.userMessage)
      .filter({ hasText: "simple_bash_test_789" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "simple_bash_test_789" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should handle bash command with non-zero exit code", async ({
    page,
  }) => {
    await sendMessage(page, "!exit 1");

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "Exit code: 1" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
  });

  test("should handle non-existent bash command", async ({ page }) => {
    await sendMessage(page, "!nonexistent_command_xyz789_unique");

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "Exit code:" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
  });

  test("should execute chained bash commands", async ({ page }) => {
    await sendMessage(
      page,
      "!echo 'chain_first_abc' && echo 'chain_second_def'"
    );

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "chain_first_abc" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("chain_second_def");
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should execute double-bang bash command (!!)", async ({ page }) => {
    await sendMessage(page, "!!echo 'double_bang_test_xyz'");

    const userMessage = page
      .locator(Selectors.userMessage)
      .filter({ hasText: "double_bang_test_xyz" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "double_bang_test_xyz" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });
    await expect(bashCard).toContainText("Exit code: 0");
  });

  test("should handle WebUI to TUI to WebUI roundtrip", async ({ page }) => {
    const command = "!echo 'roundtrip_test_unique_final'";
    await sendMessage(page, command);

    const userMessage = page
      .locator(Selectors.userMessage)
      .filter({ hasText: "roundtrip_test_unique_final" });
    await expect(userMessage).toBeVisible({ timeout: 10000 });

    const bashCard = page
      .locator(Selectors.bashCommand)
      .filter({ hasText: "roundtrip_test_unique_final" });
    await expect(bashCard).toBeVisible({ timeout: 10000 });

    await expect(bashCard).toContainText("Exit code: 0");

    const header = bashCard.locator(".bash-card-header");
    await expect(header).toBeVisible();

    const commandLine = bashCard.locator(".bash-command-line");
    await expect(commandLine).toBeVisible();
    await expect(commandLine).toContainText("echo");

    const output = bashCard.locator(".bash-output pre");
    await expect(output).toBeVisible();
    await expect(output).toContainText("roundtrip_test_unique_final");
  });
});

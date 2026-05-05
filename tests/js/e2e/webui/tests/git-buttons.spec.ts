/**
 * E2E tests for WebUI git status and git diff buttons.
 */

import { test, expect } from "../fixtures";
import {
  Selectors,
  waitForVisible,
} from "../helpers/test-utils";

test.describe("Git Buttons Feature", () => {
  test("should execute git status when clicking git status button", async ({
    page,
  }) => {
    const gitStatusBtn = page.locator("#git-status-btn");
    await expect(gitStatusBtn).toBeVisible();

    await gitStatusBtn.click();

    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "git status" });
    await expect(bashCard).toBeVisible({ timeout: 15000 });
    await waitForVisible(page, ".bash-card-title");
    const title = bashCard.locator(".bash-card-title");
    await expect(title).toContainText("Git Status");
  });

  test("should execute git diff when clicking git diff button", async ({
    page,
  }) => {
    const gitDiffBtn = page.locator("#git-diff-btn");
    await expect(gitDiffBtn).toBeVisible();

    await gitDiffBtn.click();

    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "git diff" });
    await expect(bashCard).toBeVisible({ timeout: 15000 });
    await waitForVisible(page, ".bash-card-title");
    const title = bashCard.locator(".bash-card-title");
    await expect(title).toContainText("Git Diff");
  });

  test("git diff button shows command line and output section", async ({
    page,
  }) => {
    const gitDiffBtn = page.locator("#git-diff-btn");
    await gitDiffBtn.click();

    const bashCard = page.locator(Selectors.bashCommand).filter({ hasText: "git diff" });
    await expect(bashCard).toBeVisible({ timeout: 15000 });

    const commandLine = bashCard.locator(".bash-command-line");
    await expect(commandLine).toBeVisible();
    await expect(commandLine).toContainText("git diff");

    const output = bashCard.locator(".bash-output");
    await expect(output).toBeVisible();
  });
});

/**
 * E2E tests for WebUI download feature UI rendering.
 */

import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Download Feature UI", () => {
  test("should render download card with filename, MIME type, and button", async ({
    page,
  }) => {
    // Simulate ToolResultEvent for register_download
    await page.evaluate(() => {
      const result = {
        filename: "test_file.txt",
        file_path: "/tmp/test_file.txt",
        mime_type: "text/plain",
        description: "Test file for download",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient.formatToolResult) {
        const card = vibeClient.formatToolResult("register_download", result);
        document.body.appendChild(card);
      }
    });

    // Wait for download card to appear
    const downloadCard = page.locator(".download-card");
    await expect(downloadCard).toBeVisible({ timeout: 10000 });
    await expect(downloadCard).toContainText("test_file.txt");
    await expect(downloadCard).toContainText("text/plain");
    await expect(downloadCard).toContainText("Test file for download");

    // Verify download button is present
    const downloadButton = downloadCard.locator(
      '.download-card-button:has-text("Download")'
    );
    await expect(downloadButton).toBeVisible();
  });

  test("should handle download card without description", async ({
    page,
  }) => {
    await page.evaluate(() => {
      const result = {
        filename: "no_desc.txt",
        file_path: "/tmp/no_desc.txt",
        mime_type: "text/plain",
        description: null,
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient.formatToolResult) {
        const card = vibeClient.formatToolResult("register_download", result);
        document.body.appendChild(card);
      }
    });

    const downloadCard = page.locator(".download-card").filter({
      hasText: "no_desc.txt",
    });
    await expect(downloadCard).toBeVisible({ timeout: 10000 });

    // Should NOT have description element
    const descriptionEl = downloadCard.locator(".download-card-description");
    await expect(descriptionEl).not.toBeVisible();
  });

  test.describe("MIME type icons", () => {
    const cases = [
      ["image.png", "image/png", "image"],
      ["document.pdf", "application/pdf", "picture_as_pdf"],
      ["archive.zip", "application/zip", "archive"],
    ] as const;

    for (const [filename, mimeType, expectedIcon] of cases) {
      test(`should show ${expectedIcon} icon for ${filename}`, async ({ page }) => {
        await page.evaluate(
          ({ filename, mimeType }) => {
            const result = {
              filename,
              file_path: `/tmp/${filename}`,
              mime_type: mimeType,
            };

            const vibeClient = (window as any).vibeClient;
            if (vibeClient && vibeClient.formatToolResult) {
              const card = vibeClient.formatToolResult("register_download", result);
              document.body.appendChild(card);
            }
          },
          { filename, mimeType }
        );

        const card = page.locator(".download-card").filter({ hasText: filename });
        await expect(card).toBeVisible({ timeout: 10000 });

        const icon = card.locator(
          `.material-symbols-rounded:text("${expectedIcon}")`
        );
        await expect(icon).toBeVisible();
      });
    }
  });

  test("should persist download card after browser reload", async ({
    page,
    webServer,
    mockBackend,
  }) => {
    // Create a test file in the E2E test directory
    const testDir = webServer.e2eTestDir;
    expect(testDir).not.toBeNull();
    const fs = require("fs");
    const path = require("path");
    const testFilePath = path.join(testDir!, "reload_test.txt");
    fs.writeFileSync(testFilePath, "persist me across reload", "utf-8");

    // Register a mock tool call for register_download
    await mockBackend.registerToolCall(
      "register_download",
      JSON.stringify({ file_path: testFilePath })
    );

    // Send a message to trigger the tool call
    const { sendMessage, waitForConnected } = require("../helpers/test-utils");
    await sendMessage(page, "Register this file for download");

    // Wait for the download card to appear
    const downloadCard = page.locator(".download-card");
    await downloadCard.waitFor({ state: "attached", timeout: 20000 });
    await expect(downloadCard).toContainText("reload_test.txt");
    await expect(downloadCard).toContainText("text/plain");

    // Reload the page (use "load" instead of "networkidle" for WebSocket apps)
    await page.reload({ waitUntil: "load" });

    // Wait for WebSocket to reconnect
    await waitForConnected(page, 10000);

    // Verify the download card is still visible after reload
    const downloadCardAfterReload = page.locator(".download-card");
    await downloadCardAfterReload.waitFor({ state: "attached", timeout: 10000 });
    await expect(downloadCardAfterReload).toContainText("reload_test.txt");
    await expect(downloadCardAfterReload).toContainText("text/plain");

    // Verify the download button is still present
    const downloadButton = downloadCardAfterReload.locator(
      '.download-card-button:has-text("Download")'
    );
    await expect(downloadButton).toBeVisible();
  });

  test("should trigger download API when button is clicked", async ({
    page,
    webServer,
    mockBackend,
  }) => {
    // Create a test file in the E2E test directory
    const testDir = webServer.e2eTestDir;
    expect(testDir).not.toBeNull();
    const fs = require("fs");
    const path = require("path");
    const testFilePath = path.join(testDir!, "download_link_test.txt");
    fs.writeFileSync(testFilePath, "downloadable content", "utf-8");

    // Register a mock tool call for register_download
    await mockBackend.registerToolCall(
      "register_download",
      JSON.stringify({ file_path: testFilePath })
    );

    // Set up network interception to capture the download request
    const downloadResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/download") && response.status() === 200,
      { timeout: 10000 }
    );

    // Send a message to trigger the tool call
    const { sendMessage } = require("../helpers/test-utils");
    await sendMessage(page, "Register this file for download");

    // Wait for the download card to appear
    const downloadCard = page.locator(".download-card");
    await downloadCard.waitFor({ state: "attached", timeout: 20000 });

    // Click the download button
    const downloadButton = downloadCard.locator(
      '.download-card-button:has-text("Download")'
    );
    await downloadButton.click();

    // Wait for the download API response
    const response = await downloadResponse;
    expect(response.status()).toBe(200);

    // Verify the response contains the file content
    const body = await response.text();
    expect(body).toContain("downloadable content");
  });
});

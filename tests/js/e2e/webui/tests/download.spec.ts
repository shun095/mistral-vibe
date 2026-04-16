/**
 * E2E tests for WebUI download feature UI rendering.
 */

import { test, expect } from "../fixtures";
import { Selectors } from "../helpers/test-utils";

test.describe("Download Feature UI", () => {
  test("should render download card with filename and MIME type", async ({
    page,
  }) => {
    // Simulate receiving a DownloadableContentEvent
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "test_file.txt",
        file_path: "/tmp/test_file.txt",
        mime_type: "text/plain",
        description: "Test file for download",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    // Wait for download card to appear
    const downloadCard = page.locator(".download-card");
    await expect(downloadCard).toBeVisible({ timeout: 10000 });
    await expect(downloadCard).toContainText("test_file.txt");
    await expect(downloadCard).toContainText("text/plain");
    await expect(downloadCard).toContainText("Test file for download");
  });

  test("should show image icon for image MIME types", async ({ page }) => {
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "image.png",
        file_path: "/tmp/image.png",
        mime_type: "image/png",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    const downloadCard = page.locator(".download-card").filter({
      hasText: "image.png",
    });
    await expect(downloadCard).toBeVisible({ timeout: 10000 });

    // Check for image icon
    const imageIcon = downloadCard.locator(
      '.material-symbols-rounded:text("image")'
    );
    await expect(imageIcon).toBeVisible();
  });

  test("should show PDF icon for PDF files", async ({ page }) => {
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "document.pdf",
        file_path: "/tmp/document.pdf",
        mime_type: "application/pdf",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    const pdfCard = page.locator(".download-card").filter({
      hasText: "document.pdf",
    });
    await expect(pdfCard).toBeVisible({ timeout: 10000 });

    const pdfIcon = pdfCard.locator(
      '.material-symbols-rounded:text("picture_as_pdf")'
    );
    await expect(pdfIcon).toBeVisible();
  });

  test("should show archive icon for zip files", async ({ page }) => {
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "archive.zip",
        file_path: "/tmp/archive.zip",
        mime_type: "application/zip",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    const zipCard = page.locator(".download-card").filter({
      hasText: "archive.zip",
    });
    await expect(zipCard).toBeVisible({ timeout: 10000 });

    const archiveIcon = zipCard.locator(
      '.material-symbols-rounded:text("archive")'
    );
    await expect(archiveIcon).toBeVisible();
  });

  test("should show download button", async ({ page }) => {
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "test.txt",
        file_path: "/tmp/test.txt",
        mime_type: "text/plain",
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    const downloadCard = page.locator(".download-card");
    await expect(downloadCard).toBeVisible({ timeout: 10000 });

    const downloadButton = downloadCard.locator(
      '.download-card-button:has-text("Download")'
    );
    await expect(downloadButton).toBeVisible();
  });

  test("should handle download card without description", async ({
    page,
  }) => {
    await page.evaluate(() => {
      const event = {
        __type: "DownloadableContentEvent",
        filename: "no_desc.txt",
        file_path: "/tmp/no_desc.txt",
        mime_type: "text/plain",
        description: null,
      };

      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient._renderDownloadableContent) {
        vibeClient._renderDownloadableContent(event);
      }
    });

    const downloadCard = page.locator(".download-card").filter({
      hasText: "no_desc.txt",
    });
    await expect(downloadCard).toBeVisible({ timeout: 10000 });

    // Should not have description div
    const descriptionDiv = downloadCard.locator(
      ".download-card-description"
    );
    await expect(descriptionDiv).not.toBeVisible();
  });
});

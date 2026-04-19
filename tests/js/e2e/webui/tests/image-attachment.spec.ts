/**
 * E2E tests for WebUI image attachment feature.
 * Covers US-04: Attach images to messages via paste or file upload.
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, simulateImageAttachment } from "../helpers/test-utils";

test.describe("Image Attachment", () => {
  test("should show attach image button in input area", async ({ page }) => {
    // Verify attach image button is visible
    const attachBtn = page.locator(Selectors.attachImageBtn);
    await expect(attachBtn).toBeVisible();
  });

  test("should show image preview when file is selected", async ({ page }) => {
    // Simulate image attachment via evaluate (bypass file picker)
    const mockDataUrl = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
    await simulateImageAttachment(page, mockDataUrl);

    // Verify the preview container becomes visible
    const previewContainer = page.locator(Selectors.imagePreviewContainer);
    await expect(previewContainer).toBeVisible({ timeout: 5000 });

    // Verify the image preview is shown
    const previewImg = page.locator("#image-preview-img");
    await expect(previewImg).toBeVisible();
  });

  test("should remove image when remove button is clicked", async ({ page }) => {
    // Simulate image attachment via evaluate (bypass file picker)
    await simulateImageAttachment(page, "data:image/png;base64,mockImageData");

    // Verify preview is visible
    const previewContainer = page.locator(Selectors.imagePreviewContainer);
    await expect(previewContainer).toBeVisible({ timeout: 5000 });

    // Click remove button
    const removeBtn = page.locator("#image-preview-remove");
    await removeBtn.click();

    // Verify preview is hidden
    await expect(previewContainer).not.toBeVisible({ timeout: 5000 });
  });

  test("should enable send button when image is attached but no text", async ({
    page,
  }) => {
    // Simulate image attachment
    await simulateImageAttachment(page, "data:image/png;base64,mockImageData");

    // Send button should be enabled (image provides content)
    const sendBtn = page.locator(Selectors.sendButton);
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });

    // Clear the image
    await page.locator("#image-preview-remove").click();

    // Send button should be disabled again
    await expect(sendBtn).toBeDisabled();
  });

  test("should clear image after sending message", async ({
    page,
    mockBackend,
  }) => {
    // Register mock response
    await mockBackend.registerResponse({
      response_text: "Image received!",
    });

    // Simulate image attachment
    await simulateImageAttachment(page, "data:image/png;base64,mockImageData");

    // Verify preview is visible
    const previewContainer = page.locator(Selectors.imagePreviewContainer);
    await expect(previewContainer).toBeVisible({ timeout: 5000 });

    // Send a message (with attached image)
    await page.fill(Selectors.messageInput, "Look at this");
    await page.click(Selectors.sendButton);

    // Wait for message to be sent
    await page.waitForTimeout(500);

    // Verify image preview is cleared
    await expect(previewContainer).not.toBeVisible({ timeout: 5000 });
  });
});

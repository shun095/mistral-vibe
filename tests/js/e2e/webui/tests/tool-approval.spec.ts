import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse } from "../helpers/test-utils";

test.describe("Tool Approval Flow", () => {
  test.beforeEach(async ({ page, webServer, authToken }) => {
    await page.goto(`${webServer.getUrl()}/?token=${authToken}`);
  });

  test("should show approval popup for write_file tool", async ({
    page,
    mockBackend,
  }) => {
    // write_file requires ToolPermission.ASK by default
    await mockBackend.registerToolCall(
      "write_file",
      JSON.stringify({
        path: "test.txt",
        content: "test content",
        overwrite: false,
      })
    );

    await sendMessage(page, "Write test.txt");

    // Wait for approval popup
    const approvalPopup = page.locator(Selectors.approvalPopup);
    await approvalPopup.waitFor({ state: "visible", timeout: 10000 });
    await expect(approvalPopup).toBeVisible();

    // Verify popup shows tool details
    await expect(approvalPopup).toContainText("write_file command");
  });

  test("should approve tool execution with Yes button", async ({
    page,
    mockBackend,
  }) => {
    // Register TWO mock responses:
    // 1. Tool call (agent requests to write file)
    // 2. Post-approval response (agent confirms file was written)
    await mockBackend.registerToolCall(
      "write_file",
      JSON.stringify({
        path: "test.txt",
        content: "test content",
        overwrite: false,
      })
    );
    await mockBackend.registerResponse({
      response_text: "File written successfully",
    });

    await sendMessage(page, "Write test.txt");

    // Wait for and approve via Yes button (use .popup-btn class as used in WebUI)
    const yesButton = page.locator('.popup-btn.yes:has-text("Yes")').first();
    await yesButton.waitFor({ state: "visible", timeout: 10000 });
    await yesButton.click();

    // Wait for response after approval
    const response = await waitForResponse(page);
    await expect(response).toContainText("File written");
  });

  test("should reject tool execution with No button", async ({
    page,
    mockBackend,
  }) => {
    // Register TWO mock responses:
    // 1. Tool call (agent requests to write file)
    // 2. Post-rejection response (agent acknowledges rejection)
    await mockBackend.registerToolCall(
      "write_file",
      JSON.stringify({
        path: "dangerous.txt",
        content: "malicious",
        overwrite: false,
      })
    );
    await mockBackend.registerResponse({
      response_text: "I understand, I will not write that file.",
    });

    await sendMessage(page, "Write dangerous.txt");

    // Wait for and reject via No button (use .popup-btn class as used in WebUI)
    const noButton = page.locator('.popup-btn.no:has-text("No")');
    await noButton.waitFor({ state: "visible", timeout: 10000 });
    await noButton.click();

    // Popup should disappear
    await expect(page.locator(Selectors.approvalPopup)).not.toBeVisible({
      timeout: 5000,
    });

    // Wait for response after rejection
    const response = await waitForResponse(page);
    await expect(response).toContainText("I understand");
  });

  test("should show multiple approval options in popup", async ({
    page,
    mockBackend,
  }) => {
    await mockBackend.registerToolCall(
      "write_file",
      JSON.stringify({
        path: "test.txt",
        content: "test",
        overwrite: false,
      })
    );

    await sendMessage(page, "Write test.txt");

    // Wait for approval popup
    const approvalPopup = page.locator(Selectors.approvalPopup);
    await approvalPopup.waitFor({ state: "visible", timeout: 10000 });

    // Verify all approval options are visible (use .popup-btn class as used in WebUI)
    await expect(page.getByText("Yes", { exact: true })).toBeVisible();
    await expect(page.getByText("Yes (This Session)")).toBeVisible();
    await expect(page.getByText("Enable Auto-Approve")).toBeVisible();
    await expect(page.getByText("No", { exact: true })).toBeVisible();
  });
});

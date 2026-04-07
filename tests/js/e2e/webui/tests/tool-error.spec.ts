/**
 * E2E tests for tool error persistence after page reload.
 */

import { test, expect } from "../fixtures";
import { sendMessage, waitForConnected } from "../helpers/test-utils";

test.describe("Tool Error Persistence", () => {
  test("should persist tool error after page reload", async ({
    page,
    mockBackend,
  }) => {
    // Register a mock tool call that will fail (read_file with non-existent file)
    await mockBackend.registerToolCall(
      "read_file",
      JSON.stringify({
        path: "nonexistent_file_abc123_unique.txt",
        offset: 0,
        limit: 100,
      })
    );

    // Send a message to trigger the tool call
    await sendMessage(page, "Read nonexistent_file_abc123_unique.txt");

    // Wait for the tool call card to appear
    const toolCard = page.locator(".message.tool-call").last();
    await toolCard.waitFor({ state: "attached", timeout: 20000 });

    // Wait for the error div to be attached (it's always in the DOM, even if collapsed)
    const errorDiv = toolCard.locator(".tool-error");
    await errorDiv.waitFor({ state: "attached", timeout: 10000 });

    // Verify the error message contains "File not found"
    await expect(errorDiv).toContainText("File not found");

    // Reload the page (use "load" instead of "networkidle" for WebSocket apps)
    await page.reload({ waitUntil: "load" });

    // Wait for WebSocket to reconnect
    await waitForConnected(page, 10000);

    // Verify the tool call card is still visible after reload
    const toolCardAfterReload = page.locator(".message.tool-call").last();
    await toolCardAfterReload.waitFor({ state: "attached", timeout: 10000 });

    // Get the error div after reload (it should still be in the DOM)
    const errorDivAfterReload = toolCardAfterReload.locator(".tool-error");
    await errorDivAfterReload.waitFor({ state: "attached", timeout: 10000 });

    // Verify the error message is still visible after reload
    await expect(errorDivAfterReload).toContainText("File not found");
  });
});

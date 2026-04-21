/**
 * E2E tests for WebUI browser notifications.
 * Covers US-28: WebNotificationEvent triggers showBrowserNotification().
 */

import { test, expect } from "../fixtures";
import { Selectors, sendMessage, waitForResponse } from "../helpers/test-utils";

test.describe("Browser Notifications", () => {
  test("should trigger browser notification on WebNotificationEvent", async ({
    page,
    mockBackend,
  }) => {
    // Grant notification permission and mock the Notification API
    await page.evaluate(() => {
      // Mock the Notification API to capture notifications
      (window as any).__notificationCalls = [];

      const MockNotification = class extends EventTarget {
        title: string;
        options: NotificationOptions;

        constructor(title: string, options?: NotificationOptions) {
          super();
          this.title = title;
          this.options = options || {};
          (window as any).__notificationCalls.push({ title, options });
        }

        get closed() {
          return false;
        }

        close() {
          // No-op for testing
        }
      };

      // Override window.Notification
      (window as any).Notification = MockNotification as any;

      // Grant permission
      (window as any).Notification.permission = "granted";
    });

    // Register a response that triggers a WebNotificationEvent
    await mockBackend.registerResponse({ response_text: "Task completed!" });

    // Send a message
    await sendMessage(page, "Start task");

    // Wait for response to arrive
    const assistantMsg = page.locator(Selectors.assistantMessage);
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    // Broadcast a WebNotificationEvent via WebSocket
    await mockBackend.registerEvent({
      __type: "WebNotificationEvent",
      title: "Test Notification",
      message: "This is a test notification",
    });

    // Verify the notification was triggered
    const notificationCalls = await page.evaluate(() => {
      return (window as any).__notificationCalls || [];
    });

    expect(notificationCalls.length).toBeGreaterThan(0);
    expect(notificationCalls[0].title).toBe("Test Notification");
  });

  test("should show notification with message body", async ({
    page,
    mockBackend,
  }) => {
    // Set up notification mock
    await page.evaluate(() => {
      (window as any).__notificationCalls = [];
      const MockNotification = class extends EventTarget {
        title: string;
        options: NotificationOptions;

        constructor(title: string, options?: NotificationOptions) {
          super();
          this.title = title;
          this.options = options || {};
          (window as any).__notificationCalls.push({ title, options });
        }
        close() {}
      };
      (window as any).Notification = MockNotification as any;
      (window as any).Notification.permission = "granted";
    });

    // Broadcast notification via WebSocket
    await mockBackend.registerEvent({
      __type: "WebNotificationEvent",
      title: "Agent Complete",
      message: "The task has finished successfully.",
    });

    const calls = await page.evaluate(() => (window as any).__notificationCalls);
    expect(calls.length).toBe(1);
    expect(calls[0].title).toBe("Agent Complete");
    expect(calls[0].options?.body).toBe("The task has finished successfully.");
  });

  test("should not show notification when Notification API is not supported", async ({
    page,
    mockBackend,
  }) => {
    // Remove Notification API support
    await page.evaluate(() => {
      delete (window as any).Notification;
    });

    // Broadcast notification - should not throw
    await mockBackend.registerEvent({
      __type: "WebNotificationEvent",
      title: "Test",
      message: "Should be ignored",
    });

    // Should not throw - the handler should gracefully handle missing Notification API
    // Just verify the page is still functional
    const input = page.locator(Selectors.messageInput);
    await expect(input).toBeVisible();
  });

  test("should handle notification with empty message", async ({
    page,
    mockBackend,
  }) => {
    // Set up notification mock
    await page.evaluate(() => {
      (window as any).__notificationCalls = [];
      const MockNotification = class extends EventTarget {
        title: string;
        options: NotificationOptions;

        constructor(title: string, options?: NotificationOptions) {
          super();
          this.title = title;
          this.options = options || {};
          (window as any).__notificationCalls.push({ title, options });
        }
        close() {}
      };
      (window as any).Notification = MockNotification as any;
      (window as any).Notification.permission = "granted";
    });

    // Broadcast notification with empty message
    await mockBackend.registerEvent({
      __type: "WebNotificationEvent",
      title: "Simple Alert",
      message: "",
    });

    const calls = await page.evaluate(() => (window as any).__notificationCalls);
    expect(calls.length).toBe(1);
    expect(calls[0].title).toBe("Simple Alert");
  });
});

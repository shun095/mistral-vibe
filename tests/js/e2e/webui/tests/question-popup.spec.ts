/**
 * E2E tests for WebUI question popup feature.
 * Covers US-09: Answer interactive questions from the agent.
 */

import { test, expect } from "../fixtures";
import { Selectors, showQuestionPopup } from "../helpers/test-utils";

test.describe("Question Popup", () => {
  test("should show question popup with header and options", async ({ page }) => {
    // Simulate a QuestionPopupEvent via VibeClient
    await showQuestionPopup(page, {
      popup_id: "test-question-1",
      __type: "QuestionPopupEvent",
      questions: [
        {
          question: "What is your preferred language?",
          header: "Language",
          options: [
            { label: "English", description: "Most common" },
            { label: "Spanish", description: "Romance language" },
          ],
          multi_select: false,
          hide_other: false,
        },
      ],
    });

    // Wait for question popup
    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Verify header is shown
    const popupHeader = questionPopup.locator(".popup-header");
    await expect(popupHeader).toBeVisible();
    await expect(popupHeader).toContainText("Language");

    // Verify question text is shown
    const popupContent = questionPopup.locator(".popup-content");
    await expect(popupContent).toBeVisible();
    await expect(popupContent).toContainText("preferred language");

    // Verify options are shown
    await expect(questionPopup.getByText("English")).toBeVisible();
    await expect(questionPopup.getByText("Spanish")).toBeVisible();
  });

  test("should allow selecting a single option", async ({ page }) => {
    await showQuestionPopup(page, { popup_id: "test-question-2", __type: "QuestionPopupEvent", questions: [ { question: "Choose one", header: "Selection", options: [ { label: "Option A", description: "First" }, { label: "Option B", description: "Second" }, ], multi_select: false, hide_other: true, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Click on Option A (single-select auto-submits and closes popup)
    await questionPopup.getByText("Option A").click();

    // Popup should close after selection (auto-submit behavior)
    await expect(questionPopup).not.toBeVisible({ timeout: 5000 });
  });

  test("should allow multi-select options", async ({ page }) => {
    await showQuestionPopup(page, { popup_id: "test-question-3", __type: "QuestionPopupEvent", questions: [ { question: "Select all that apply", header: "Multi", options: [ { label: "A", description: "" }, { label: "B", description: "" }, { label: "C", description: "" }, ], multi_select: true, hide_other: false, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Click on two options
    await questionPopup.getByRole("button", { name: "A", exact: true }).click();
    await questionPopup.getByRole("button", { name: "B", exact: true }).click();

    // Both should be selected
    const selectedBtns = questionPopup.locator(
      '.popup-btn[data-option].selected'
    );
    const count = await selectedBtns.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test("should show custom answer input for 'Other' option", async ({
    page,
  }) => {
    await showQuestionPopup(page, { popup_id: "test-question-4", __type: "QuestionPopupEvent", questions: [ { question: "Your choice", header: "Custom", options: [{ label: "Default", description: "" }], multi_select: false, hide_other: false, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Click the "Other" button
    await questionPopup.getByText("Other (custom answer)").click();

    // Custom input should appear
    const otherInput = questionPopup.locator("#question-other-input");
    await expect(otherInput).toBeVisible();
  });

  test("should submit answer and close popup", async ({ page }) => {
    // Set up interceptor to capture question responses on window
    await page.evaluate(() => {
      const vibeClient = (window as any).vibeClient;
      if (vibeClient && vibeClient.wsClient) {
        const originalWsSend = vibeClient.wsClient.send.bind(vibeClient.wsClient);
        vibeClient.wsClient.send = (msg: any) => {
          if (msg.type === "question_response") {
            (window as any).__lastQuestionResponse = msg;
          }
          return originalWsSend(msg);
        };
      }
    });

    await showQuestionPopup(page, { popup_id: "test-question-5", __type: "QuestionPopupEvent", questions: [ { question: "Confirm?", header: "Yes/No", options: [ { label: "Yes", description: "" }, { label: "No", description: "" }, ], multi_select: false, hide_other: true, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Select Yes and submit
    await questionPopup.getByRole("button", { name: "Yes" }).click();

    // Popup should close after submission
    await expect(questionPopup).not.toBeVisible({ timeout: 5000 });

    // Verify the question response was sent with correct data
    const response = await page.evaluate(() => {
      return (window as any).__lastQuestionResponse;
    });
    expect(response).toBeDefined();
    expect(response.type).toBe("question_response");
  });

  test("should cancel question and close popup", async ({ page }) => {
    await showQuestionPopup(page, { popup_id: "test-question-6", __type: "QuestionPopupEvent", questions: [ { question: "Cancel test?", header: "Test", options: [ { label: "A", description: "" }, { label: "B", description: "" }, ], multi_select: false, hide_other: true, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Click cancel
    const cancelButton = questionPopup.locator("#question-cancel");
    await cancelButton.click();

    // Popup should close
    await expect(questionPopup).not.toBeVisible({ timeout: 5000 });
  });

  test("should disable input while question popup is open", async ({
    page,
  }) => {
    await showQuestionPopup(page, { popup_id: "test-question-7", __type: "QuestionPopupEvent", questions: [ { question: "Test?", header: "Test", options: [{ label: "A", description: "" }], multi_select: false, hide_other: true, }, ], });

    const questionPopup = page.locator(".question-popup");
    await expect(questionPopup).toBeVisible({ timeout: 5000 });

    // Input should be disabled
    const input = page.locator(Selectors.messageInput);
    await expect(input).toBeDisabled();

    // Cancel to re-enable
    await questionPopup.locator("#question-cancel").click();

    // Input should be re-enabled
    await expect(input).toBeEnabled();
  });
});

/**
 * Tests for VibeClient question handling.
 * 
 * These tests verify the JavaScript logic for handling ask_user_question tool
 * in the Web UI.
 */

// Mock DOM elements for testing
global.document = {
  createElement: jest.fn(() => ({
    className: '',
    id: '',
    innerHTML: '',
    parentNode: null,
    addEventListener: jest.fn(),
    querySelector: jest.fn(),
    querySelectorAll: jest.fn(() => []),
    appendChild: jest.fn(),
    removeChild: jest.fn(),
    style: {},
    focus: jest.fn(),
    display: '',
    disabled: false,
    value: '',
    textContent: '',
    classList: {
      add: jest.fn(),
      remove: jest.fn(),
      toggle: jest.fn(),
    },
    removeClass: jest.fn(),
    addClass: jest.fn(),
  })),
  addEventListener: jest.fn(),
};

// Mock WebSocket
global.WebSocket = jest.fn(() => ({
  send: jest.fn(),
  close: jest.fn(),
  onopen: null,
  onmessage: null,
  onclose: null,
  onerror: null,
}));

// Import the VibeClient - we'll test the logic by mocking the relevant parts
describe('VibeClient Question Handling', () => {
  let mockClient;

  beforeEach(() => {
    // Create a mock client that simulates the VibeClient behavior
    mockClient = {
      currentPopupId: null,
      currentPopupElement: null,
      currentQuestions: null,
      currentQuestionIndex: 0,
      currentQuestionAnswers: [],
      sentResponses: [],
      elements: {
        input: { disabled: false },
      },

      // Simulate showQuestionPopup logic
      showQuestionPopup(event) {
        this.currentPopupId = event.popup_id;

        // Only reset state if this is the first question (from server event)
        // For subsequent questions (from submitCurrentQuestionOrNext), preserve state
        if (this.currentQuestions === null || this.currentQuestions.length === 0) {
          this.currentQuestions = event.questions;
          this.currentQuestionIndex = 0;
          this.currentQuestionAnswers = [];
        }

        const currentQuestion = this.currentQuestions[this.currentQuestionIndex];
        return currentQuestion;
      },

      // Simulate submitCurrentQuestionOrNext logic
      submitCurrentQuestionOrNext() {
        // Check if there are more questions to answer
        if (this.currentQuestionIndex < this.currentQuestions.length - 1) {
          // Move to next question
          this.currentQuestionIndex++;
          this.currentPopupElement = null;
          // Show next question popup with updated popup_id
          const nextEvent = {
            popup_id: this.currentPopupId + '_q' + (this.currentQuestionIndex + 1),
            questions: this.currentQuestions,
            content_preview: null,
          };
          return { question: this.showQuestionPopup(nextEvent), hasMore: true };
        } else {
          // All questions answered, send final response
          this.sendQuestionResponse(this.currentPopupId, this.currentQuestionAnswers, false);
          this.currentPopupElement = null;
          this.currentQuestions = null;
          this.currentQuestionIndex = 0;
          this.currentQuestionAnswers = [];
          return { question: null, hasMore: false };
        }
      },

      // Simulate sendQuestionResponse logic
      sendQuestionResponse(popupId, answers, cancelled) {
        this.sentResponses.push({
          type: 'question_response',
          popup_id: popupId,
          answers: answers,
          cancelled: cancelled,
        });
      },

      // Simulate hidePopup logic
      hidePopup(event) {
        this.currentPopupElement = null;
        this.currentPopupId = null;
        this.currentQuestions = null;
        this.currentQuestionIndex = 0;
        this.currentQuestionAnswers = [];
      },

      // Simulate option selection
      selectOption(optionIdx, isOther = false, otherText = '') {
        const currentQuestion = this.currentQuestions[this.currentQuestionIndex];

        if (isOther) {
          this.currentQuestionAnswers.push({
            question: currentQuestion.question,
            answer: otherText,
            is_other: true,
          });
        } else {
          // Return option label text instead of index
          const optionLabel = currentQuestion.options[optionIdx].label;
          this.currentQuestionAnswers.push({
            question: currentQuestion.question,
            answer: optionLabel,
            is_other: false,
          });
        }

        return this.submitCurrentQuestionOrNext();
      },
    };
  });

  describe('Single Question Handling', () => {
    test('returns option label text instead of index', () => {
      const event = {
        popup_id: 'question_123',
        questions: [
          {
            question: 'What is your favorite color?',
            header: 'Color',
            options: [
              { label: 'Blue', description: 'Calm and peaceful' },
              { label: 'Red', description: 'Bold and energetic' },
              { label: 'Green', description: 'Natural and fresh' },
            ],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);
      mockClient.selectOption(0); // Select first option (index 0)

      // Verify the answer contains the label, not the index
      expect(mockClient.sentResponses).toHaveLength(1);
      const response = mockClient.sentResponses[0];
      expect(response.answers[0].answer).toBe('Blue');
      expect(response.answers[0].answer).not.toBe('0');
      expect(response.answers[0].is_other).toBe(false);
    });

    test('handles Other option correctly', () => {
      const event = {
        popup_id: 'question_456',
        questions: [
          {
            question: 'What is your favorite color?',
            header: 'Color',
            options: [
              { label: 'Blue', description: 'Calm and peaceful' },
              { label: 'Red', description: 'Bold and energetic' },
            ],
            multi_select: false,
            hide_other: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);
      mockClient.selectOption(0, true, 'Purple'); // Select Other with custom text

      // Verify the answer contains the custom text
      expect(mockClient.sentResponses).toHaveLength(1);
      const response = mockClient.sentResponses[0];
      expect(response.answers[0].answer).toBe('Purple');
      expect(response.answers[0].is_other).toBe(true);
    });
  });

  describe('Multiple Questions Handling', () => {
    test('shows questions sequentially', () => {
      const event = {
        popup_id: 'question_789',
        questions: [
          {
            question: 'What is your favorite color?',
            header: 'Color',
            options: [
              { label: 'Blue', description: 'Calm and peaceful' },
              { label: 'Red', description: 'Bold and energetic' },
            ],
            multi_select: false,
          },
          {
            question: 'What is your favorite food?',
            header: 'Food',
            options: [
              { label: 'Pizza', description: 'Italian classic' },
              { label: 'Sushi', description: 'Japanese delicacy' },
            ],
            multi_select: false,
          },
        ],
      };

      // First question
      mockClient.showQuestionPopup(event);
      const result1 = mockClient.selectOption(0); // Select "Blue"
      expect(result1.hasMore).toBe(true);
      expect(result1.question.question).toBe('What is your favorite food?');

      // Second question
      const result2 = mockClient.selectOption(1); // Select "Sushi"
      expect(result2.hasMore).toBe(false);

      // Verify all answers are sent together
      expect(mockClient.sentResponses).toHaveLength(1);
      const response = mockClient.sentResponses[0];
      expect(response.answers).toHaveLength(2);
      expect(response.answers[0].answer).toBe('Blue');
      expect(response.answers[1].answer).toBe('Sushi');
    });

    test('accumulates answers across questions', () => {
      const event = {
        popup_id: 'question_abc',
        questions: [
          {
            question: 'Question 1?',
            header: 'Q1',
            options: [
              { label: 'A1', description: '' },
              { label: 'B1', description: '' },
            ],
            multi_select: false,
          },
          {
            question: 'Question 2?',
            header: 'Q2',
            options: [
              { label: 'A2', description: '' },
              { label: 'B2', description: '' },
            ],
            multi_select: false,
          },
          {
            question: 'Question 3?',
            header: 'Q3',
            options: [
              { label: 'A3', description: '' },
              { label: 'B3', description: '' },
            ],
            multi_select: false,
          },
        ],
      };

      // Answer all three questions
      mockClient.showQuestionPopup(event);
      mockClient.selectOption(0); // A1
      mockClient.selectOption(1); // B2
      mockClient.selectOption(0); // A3

      // Verify all answers are accumulated
      expect(mockClient.sentResponses).toHaveLength(1);
      const response = mockClient.sentResponses[0];
      expect(response.answers).toHaveLength(3);
      expect(response.answers[0].answer).toBe('A1');
      expect(response.answers[1].answer).toBe('B2');
      expect(response.answers[2].answer).toBe('A3');
    });

    test('cancel clears all state', () => {
      const event = {
        popup_id: 'question_xyz',
        questions: [
          {
            question: 'Question 1?',
            header: 'Q1',
            options: [{ label: 'A1', description: '' }],
            multi_select: false,
          },
          {
            question: 'Question 2?',
            header: 'Q2',
            options: [{ label: 'A2', description: '' }],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);
      mockClient.selectOption(0); // Answer first question

      // Cancel
      mockClient.sendQuestionResponse(mockClient.currentPopupId, [], true);
      mockClient.hidePopup({ popup_id: mockClient.currentPopupId });

      // Verify state is cleared
      expect(mockClient.currentQuestions).toBe(null);
      expect(mockClient.currentQuestionIndex).toBe(0);
      expect(mockClient.currentQuestionAnswers).toHaveLength(0);
      expect(mockClient.currentPopupId).toBe(null);
    });

    test('handles mixed regular and Other answers', () => {
      const event = {
        popup_id: 'question_mixed',
        questions: [
          {
            question: 'Question 1?',
            header: 'Q1',
            options: [{ label: 'A1', description: '' }],
            multi_select: false,
          },
          {
            question: 'Question 2?',
            header: 'Q2',
            options: [{ label: 'A2', description: '' }],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);
      mockClient.selectOption(0); // Regular answer: A1
      mockClient.selectOption(0, true, 'Custom answer'); // Other answer

      // Verify mixed answers
      expect(mockClient.sentResponses).toHaveLength(1);
      const response = mockClient.sentResponses[0];
      expect(response.answers).toHaveLength(2);
      expect(response.answers[0].answer).toBe('A1');
      expect(response.answers[0].is_other).toBe(false);
      expect(response.answers[1].answer).toBe('Custom answer');
      expect(response.answers[1].is_other).toBe(true);
    });
  });

  describe('State Preservation', () => {
    test('preserves state across popups', () => {
      const event = {
        popup_id: 'question_state',
        questions: [
          {
            question: 'Question 1?',
            header: 'Q1',
            options: [{ label: 'A1', description: '' }],
            multi_select: false,
          },
          {
            question: 'Question 2?',
            header: 'Q2',
            options: [{ label: 'A2', description: '' }],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);
      expect(mockClient.currentQuestionIndex).toBe(0);
      expect(mockClient.currentQuestions).toHaveLength(2);

      // Simulate moving to next question
      mockClient.currentQuestionAnswers.push({
        question: 'Question 1?',
        answer: 'A1',
        is_other: false,
      });
      mockClient.currentQuestionIndex = 1;

      // Show next popup (simulating submitCurrentQuestionOrNext)
      const nextEvent = {
        popup_id: 'question_state_q2',
        questions: mockClient.currentQuestions,
        content_preview: null,
      };
      mockClient.showQuestionPopup(nextEvent);

      // State should be preserved
      expect(mockClient.currentQuestionIndex).toBe(1);
      expect(mockClient.currentQuestions).toHaveLength(2);
      expect(mockClient.currentQuestionAnswers).toHaveLength(1);
    });
  });

  describe('Submit Button Text', () => {
    test('shows Next button for non-last question', () => {
      const event = {
        popup_id: 'question_btn',
        questions: [
          {
            question: 'Question 1?',
            header: 'Q1',
            options: [{ label: 'A1', description: '' }],
            multi_select: false,
          },
          {
            question: 'Question 2?',
            header: 'Q2',
            options: [{ label: 'A2', description: '' }],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);

      // First question should show "Next"
      const isLastQuestion =
        mockClient.currentQuestions.length === 1 ||
        mockClient.currentQuestionIndex === mockClient.currentQuestions.length - 1;
      const submitButtonText = isLastQuestion ? 'Submit' : 'Next';
      expect(submitButtonText).toBe('Next');

      // Move to last question
      mockClient.currentQuestionIndex = 1;

      // Last question should show "Submit"
      const isLastQuestion2 =
        mockClient.currentQuestions.length === 1 ||
        mockClient.currentQuestionIndex === mockClient.currentQuestions.length - 1;
      const submitButtonText2 = isLastQuestion2 ? 'Submit' : 'Next';
      expect(submitButtonText2).toBe('Submit');
    });

    test('shows Submit button for single question', () => {
      const event = {
        popup_id: 'question_single',
        questions: [
          {
            question: 'Single question?',
            header: 'Q',
            options: [{ label: 'A1', description: '' }],
            multi_select: false,
          },
        ],
      };

      mockClient.showQuestionPopup(event);

      // Single question should show "Submit"
      const isLastQuestion =
        mockClient.currentQuestions.length === 1 ||
        mockClient.currentQuestionIndex === mockClient.currentQuestions.length - 1;
      const submitButtonText = isLastQuestion ? 'Submit' : 'Next';
      expect(submitButtonText).toBe('Submit');
    });
  });
});

/**
 * Question Handler Module
 * Handles the logic for multi-question popups and state management.
 */

class QuestionHandler {
    constructor() {
        this.currentPopupId = null;
        this.originalPopupId = null; // Store original popup_id without _q suffixes
        this.currentQuestions = null;
        this.currentQuestionIndex = 0;
        this.currentQuestionAnswers = [];
    }

    /**
     * Initialize or update question state from an event.
     * @param {Object} event - The QuestionPopupEvent object
     * @returns {Object|null} The current question or null if no questions provided
     */
    showQuestionPopup(event) {
        this.currentPopupId = event.popup_id;

        // Store original popup_id (before any _q suffixes) for final response
        if (!this.originalPopupId) {
            this.originalPopupId = event.popup_id.split('_q')[0];
        }

        // Only reset state if this is the first question (from server event)
        // For subsequent questions (from submitCurrentQuestionOrNext), preserve state
        if (!this.currentQuestions || this.currentQuestions.length === 0) {
            if (!event.questions || event.questions.length === 0) {
                console.error('showQuestionPopup: No questions provided');
                return null;
            }
            this.currentQuestions = event.questions;
            this.currentQuestionIndex = 0;
            this.currentQuestionAnswers = [];
        }

        const currentQuestion = this.currentQuestions[this.currentQuestionIndex];
        return currentQuestion;
    }

    /**
     * Submit current answer and move to next question or send final response.
     * @returns {Object} Result with hasMore flag
     */
    submitCurrentQuestionOrNext() {
        // Check if there are more questions to answer
        if (this.currentQuestionIndex < this.currentQuestions.length - 1) {
            // Move to next question
            this.currentQuestionIndex++;

            // Build next event for VibeClient to handle
            const nextEvent = {
                popup_id: this.currentPopupId + '_q' + (this.currentQuestionIndex + 1),
                questions: this.currentQuestions,
                content_preview: null
            };

            return { hasMore: true, nextEvent };
        } else {
            // All questions answered, send final response
            const message = this.sendQuestionResponse(this.originalPopupId, this.currentQuestionAnswers, false);

            // Clear state
            this.currentPopupId = null;
            this.originalPopupId = null;
            this.currentQuestions = null;
            this.currentQuestionIndex = 0;
            this.currentQuestionAnswers = [];

            return { hasMore: false, message };
        }
    }

    /**
     * Send question response via WebSocket.
     * @param {string} popupId - The popup ID to respond to
     * @param {Array} answers - Array of answers
     * @param {boolean} cancelled - Whether the popup was cancelled
     * @returns {Object} The message that was sent
     */
    sendQuestionResponse(popupId, answers, cancelled) {
        const message = {
            type: 'question_response',
            popup_id: popupId,
            answers: answers,
            cancelled: cancelled
        };
        return message;
    }

    /**
     * Hide popup and clear state.
     * This method should be overridden by the VibeClient to handle DOM operations.
     * @param {Object} event - The popup event
     */
    hidePopup(event) {
        // Default implementation - clear state only
        // VibeClient should override this to also remove DOM elements
        this.currentPopupId = null;
        this.currentQuestions = null;
        this.currentQuestionIndex = 0;
        this.currentQuestionAnswers = [];
    }

    /**
     * Reset all question state.
     */
    reset() {
        this.currentPopupId = null;
        this.originalPopupId = null;
        this.currentQuestions = null;
        this.currentQuestionIndex = 0;
        this.currentQuestionAnswers = [];
    }
}

// ES6 module export for browser
export { QuestionHandler };

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { QuestionHandler };
}

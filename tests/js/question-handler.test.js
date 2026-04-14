/**
 * Tests for QuestionHandler module.
 *
 * These tests verify the JavaScript logic for handling ask_user_question tool
 * in the Web UI.
 */

// Import the actual QuestionHandler module
const { QuestionHandler } = require('../../vibe/cli/web_ui/static/js/question-handler.js');

describe('QuestionHandler', () => {
    let handler;

    beforeEach(() => {
        handler = new QuestionHandler();
    });

    describe('Single Question Handling', () => {
        test('shows single question and returns it', () => {
            const event = {
                popup_id: 'question_single',
                questions: [
                    {
                        question: 'What is your name?',
                        header: 'Name',
                        options: [
                            { label: 'Alice', description: 'A common name' },
                            { label: 'Bob', description: 'Another name' },
                        ],
                        multi_select: false,
                    }
                ],
            };

            const currentQuestion = handler.showQuestionPopup(event);

            expect(currentQuestion).toEqual(event.questions[0]);
            expect(handler.currentQuestionIndex).toBe(0);
            expect(handler.currentQuestions).toHaveLength(1);
        });

        test('submits single question and sends response with original popup_id', () => {
            const event = {
                popup_id: 'question_single',
                questions: [
                    {
                        question: 'What is your name?',
                        header: 'Name',
                        options: [
                            { label: 'Alice', description: 'A common name' },
                            { label: 'Bob', description: 'Another name' },
                        ],
                        multi_select: false,
                    }
                ],
            };

            handler.showQuestionPopup(event);
            handler.currentQuestionAnswers.push({
                question: 'What is your name?',
                answer: 'Alice',
                is_other: false,
            });

            const result = handler.submitCurrentQuestionOrNext();

            expect(result.hasMore).toBe(false);
            expect(result.message).toEqual({
                type: 'question_response',
                popup_id: 'question_single',
                answers: [
                    {
                        question: 'What is your name?',
                        answer: 'Alice',
                        is_other: false,
                    }
                ],
                cancelled: false,
            });

            // State should be cleared
            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
            expect(handler.currentQuestionAnswers).toHaveLength(0);
            expect(handler.originalPopupId).toBe(null);
        });
    });

    describe('Multiple Questions Handling', () => {
        test('shows questions sequentially', () => {
            const event = {
                popup_id: 'question_multi',
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
                ],
            };

            // First question
            let currentQuestion = handler.showQuestionPopup(event);
            expect(currentQuestion.question).toBe('Question 1?');
            expect(handler.currentQuestionIndex).toBe(0);

            // Answer first question
            handler.currentQuestionAnswers.push({
                question: 'Question 1?',
                answer: 'A1',
                is_other: false,
            });
            handler.submitCurrentQuestionOrNext();

            // Second question should be shown
            expect(handler.currentQuestionIndex).toBe(1);
            expect(handler.currentQuestions).toHaveLength(2);
        });

        test('accumulates answers across questions', () => {
            const event = {
                popup_id: 'question_answers',
                questions: [
                    {
                        question: 'Question 1?',
                        header: 'Q1',
                        options: [{ label: 'A1', description: '' }, { label: 'B1', description: '' }],
                        multi_select: false,
                    },
                    {
                        question: 'Question 2?',
                        header: 'Q2',
                        options: [{ label: 'A2', description: '' }, { label: 'B2', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);

            // Answer first question
            handler.currentQuestionAnswers.push({
                question: 'Question 1?',
                answer: 'A1',
                is_other: false,
            });
            handler.submitCurrentQuestionOrNext();

            expect(handler.currentQuestionAnswers).toHaveLength(1);

            // Answer second question
            handler.currentQuestionAnswers.push({
                question: 'Question 2?',
                answer: 'B2',
                is_other: false,
            });
            const result = handler.submitCurrentQuestionOrNext();

            expect(result.message.answers).toHaveLength(2);
            expect(result.message.answers[0].answer).toBe('A1');
            expect(result.message.answers[1].answer).toBe('B2');
        });

        test('sends response with original popup_id after multiple questions', () => {
            const event = {
                popup_id: 'question_original_id',
                questions: [
                    {
                        question: 'Question 1?',
                        header: 'Q1',
                        options: [{ label: 'A1', description: '' }, { label: 'B1', description: '' }],
                        multi_select: false,
                    },
                    {
                        question: 'Question 2?',
                        header: 'Q2',
                        options: [{ label: 'A2', description: '' }, { label: 'B2', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);

            // Answer first question
            handler.currentQuestionAnswers.push({
                question: 'Question 1?',
                answer: 'A1',
                is_other: false,
            });
            const nextResult = handler.submitCurrentQuestionOrNext();

            // Verify nextEvent has correct popup_id with _q suffix
            expect(nextResult.hasMore).toBe(true);
            expect(nextResult.nextEvent.popup_id).toBe('question_original_id_q2');

            // Show next question (simulating VibeClient behavior)
            handler.showQuestionPopup(nextResult.nextEvent);

            // Answer second question
            handler.currentQuestionAnswers.push({
                question: 'Question 2?',
                answer: 'B2',
                is_other: false,
            });
            const result = handler.submitCurrentQuestionOrNext();

            // Response should use original popup_id
            expect(result.message.popup_id).toBe('question_original_id');
        });

        test('handles 3 questions correctly', () => {
            const event = {
                popup_id: 'question_3',
                questions: [
                    {
                        question: 'Question 1?',
                        header: 'Q1',
                        options: [{ label: 'A1', description: '' }, { label: 'B1', description: '' }],
                        multi_select: false,
                    },
                    {
                        question: 'Question 2?',
                        header: 'Q2',
                        options: [{ label: 'A2', description: '' }, { label: 'B2', description: '' }],
                        multi_select: false,
                    },
                    {
                        question: 'Question 3?',
                        header: 'Q3',
                        options: [{ label: 'A3', description: '' }, { label: 'B3', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);

            // Answer first question
            handler.currentQuestionAnswers.push({ question: 'Question 1?', answer: 'A1', is_other: false });
            let nextResult = handler.submitCurrentQuestionOrNext();
            expect(nextResult.hasMore).toBe(true);
            handler.showQuestionPopup(nextResult.nextEvent);

            // Answer second question
            handler.currentQuestionAnswers.push({ question: 'Question 2?', answer: 'B2', is_other: false });
            nextResult = handler.submitCurrentQuestionOrNext();
            expect(nextResult.hasMore).toBe(true);
            handler.showQuestionPopup(nextResult.nextEvent);

            // Answer third question
            handler.currentQuestionAnswers.push({ question: 'Question 3?', answer: 'A3', is_other: false });
            const result = handler.submitCurrentQuestionOrNext();

            expect(result.message.answers).toHaveLength(3);
            expect(result.message.answers[0].answer).toBe('A1');
            expect(result.message.answers[1].answer).toBe('B2');
            expect(result.message.answers[2].answer).toBe('A3');
            expect(result.message.popup_id).toBe('question_3');
        });
    });

    describe('Null/Empty Questions Handling', () => {
        test('handles null questions gracefully', () => {
            const event = {
                popup_id: 'question_null',
                questions: null,
            };

            const result = handler.showQuestionPopup(event);

            expect(result).toBe(null);
            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
        });

        test('handles undefined questions gracefully', () => {
            const event = {
                popup_id: 'question_undefined',
                questions: undefined,
            };

            const result = handler.showQuestionPopup(event);

            expect(result).toBe(null);
            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
        });

        test('handles empty questions array gracefully', () => {
            const event = {
                popup_id: 'question_empty',
                questions: [],
            };

            const result = handler.showQuestionPopup(event);

            expect(result).toBe(null);
            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
        });
    });

    describe('State Management', () => {
        test('preserves state across question navigation', () => {
            const event = {
                popup_id: 'question_state',
                questions: [
                    {
                        question: 'Q1?',
                        header: 'H1',
                        options: [{ label: 'A1', description: '' }, { label: 'B1', description: '' }],
                        multi_select: false,
                    },
                    {
                        question: 'Q2?',
                        header: 'H2',
                        options: [{ label: 'A2', description: '' }, { label: 'B2', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);

            // Answer first question
            handler.currentQuestionAnswers.push({ question: 'Q1?', answer: 'A1', is_other: false });
            handler.submitCurrentQuestionOrNext();

            // Verify state after first answer
            expect(handler.currentQuestionIndex).toBe(1);
            expect(handler.currentQuestions).toHaveLength(2);
            expect(handler.currentQuestionAnswers).toHaveLength(1);
            expect(handler.originalPopupId).toBe('question_state');
        });

        test('clears state after completion', () => {
            const event = {
                popup_id: 'question_clear',
                questions: [
                    {
                        question: 'Q1?',
                        header: 'H1',
                        options: [{ label: 'A1', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);
            handler.currentQuestionAnswers.push({ question: 'Q1?', answer: 'A1', is_other: false });
            handler.submitCurrentQuestionOrNext();

            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
            expect(handler.currentQuestionAnswers).toHaveLength(0);
            expect(handler.originalPopupId).toBe(null);
        });

        test('reset method clears all state', () => {
            const event = {
                popup_id: 'question_reset',
                questions: [
                    {
                        question: 'Q1?',
                        header: 'H1',
                        options: [{ label: 'A1', description: '' }],
                        multi_select: false,
                    },
                ],
            };

            handler.showQuestionPopup(event);
            handler.currentQuestionAnswers.push({ question: 'Q1?', answer: 'A1', is_other: false });

            handler.reset();

            expect(handler.currentPopupId).toBe(null);
            expect(handler.originalPopupId).toBe(null);
            expect(handler.currentQuestions).toBe(null);
            expect(handler.currentQuestionIndex).toBe(0);
            expect(handler.currentQuestionAnswers).toHaveLength(0);
        });
    });
});

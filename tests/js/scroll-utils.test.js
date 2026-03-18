/**
 * Tests for scroll-utils module.
 * 
 * These tests verify the JavaScript scroll utilities for the chat message container.
 */

// Import the actual scroll-utils module
const scrollUtils = require('../../vibe/cli/web_ui/static/js/scroll-utils.js');

// Mock HTMLElement for testing
class MockElement {
    constructor(config = {}) {
        this.scrollTop = config.scrollTop || 0;
        this.scrollHeight = config.scrollHeight || 0;
        this.clientHeight = config.clientHeight || 0;
        this.children = config.children || [];
        this.offsetTop = config.offsetTop || 0;
        this.offsetHeight = config.offsetHeight || 0;
    }

    querySelectorAll(selector) {
        // Return elements that match the selector
        if (selector === '.message.user') {
            return this.children.filter(child => child.classList && child.classList.includes('user'));
        }
        return [];
    }
}

class MockMessageElement extends MockElement {
    constructor(config = {}) {
        super(config);
        this.classList = config.classList || [];
    }
}

describe('scroll-utils', () => {
    describe('isAtBottom', () => {
        test('returns true when at the bottom', () => {
            const messages = new MockElement({
                scrollTop: 900,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            expect(scrollUtils.isAtBottom(messages, 100)).toBe(true);
        });

        test('returns true when within threshold of bottom', () => {
            const messages = new MockElement({
                scrollTop: 850,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            expect(scrollUtils.isAtBottom(messages, 100)).toBe(true);
        });

        test('returns false when not at the bottom', () => {
            const messages = new MockElement({
                scrollTop: 500,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            expect(scrollUtils.isAtBottom(messages, 100)).toBe(false);
        });

        test('returns false when far from bottom', () => {
            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            expect(scrollUtils.isAtBottom(messages, 100)).toBe(false);
        });

        test('uses default threshold of 100', () => {
            const messages = new MockElement({
                scrollTop: 900,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            expect(scrollUtils.isAtBottom(messages)).toBe(true);
        });
    });

    describe('wasAtBottomBeforeUpdate', () => {
        test('returns true if user was at bottom before content expanded', () => {
            const messages = new MockElement({
                scrollTop: 900,
                scrollHeight: 1100, // Increased after content added
                clientHeight: 100,
            });
            const previousScrollHeight = 1000;

            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(true);
        });

        test('returns false if user was not at bottom before content expanded', () => {
            const messages = new MockElement({
                scrollTop: 500,
                scrollHeight: 1100, // Increased after content added
                clientHeight: 100,
            });
            const previousScrollHeight = 1000;

            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(false);
        });

        test('returns true if user was within threshold before content expanded', () => {
            const messages = new MockElement({
                scrollTop: 850,
                scrollHeight: 1100, // Increased after content added
                clientHeight: 100,
            });
            const previousScrollHeight = 1000;

            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(true);
        });
    });

    describe('scrollToBottom', () => {
        test('sets scrollTop to scrollHeight', () => {
            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            scrollUtils.scrollToBottom(messages);

            expect(messages.scrollTop).toBe(1000);
        });
    });

    describe('scrollToBottomIfNeeded', () => {
        test('scrolls to bottom when at bottom', () => {
            const messages = new MockElement({
                scrollTop: 900,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            scrollUtils.scrollToBottomIfNeeded(messages, 100);

            expect(messages.scrollTop).toBe(1000);
        });

        test('does not scroll when not at bottom', () => {
            const messages = new MockElement({
                scrollTop: 500,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            scrollUtils.scrollToBottomIfNeeded(messages, 100);

            expect(messages.scrollTop).toBe(500);
        });
    });

    describe('scrollToBottomIfWasAtBottom', () => {
        test('scrolls to bottom if user was at bottom before update', () => {
            const messages = new MockElement({
                scrollTop: 900,
                scrollHeight: 1100,
                clientHeight: 100,
            });
            const previousScrollHeight = 1000;

            scrollUtils.scrollToBottomIfWasAtBottom(messages, previousScrollHeight, 100);

            expect(messages.scrollTop).toBe(1100);
        });

        test('does not scroll if user was not at bottom before update', () => {
            const messages = new MockElement({
                scrollTop: 500,
                scrollHeight: 1100,
                clientHeight: 100,
            });
            const previousScrollHeight = 1000;

            scrollUtils.scrollToBottomIfWasAtBottom(messages, previousScrollHeight, 100);

            expect(messages.scrollTop).toBe(500);
        });
    });

    describe('scrollToTop', () => {
        test('sets scrollTop to 0', () => {
            const messages = new MockElement({
                scrollTop: 500,
                scrollHeight: 1000,
                clientHeight: 100,
            });

            scrollUtils.scrollToTop(messages);

            expect(messages.scrollTop).toBe(0);
        });
    });

    describe('getUserMessages', () => {
        test('returns array of user messages', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100 });
            const userMsg2 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 200 });
            const assistantMsg = new MockMessageElement({ classList: ['message', 'assistant'], offsetTop: 300 });

            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 100,
                children: [userMsg1, assistantMsg, userMsg2],
            });

            const userMessages = scrollUtils.getUserMessages(messages);

            expect(userMessages).toHaveLength(2);
            expect(userMessages[0]).toBe(userMsg1);
            expect(userMessages[1]).toBe(userMsg2);
        });

        test('returns empty array when no user messages', () => {
            const assistantMsg = new MockMessageElement({ classList: ['message', 'assistant'] });

            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 100,
                children: [assistantMsg],
            });

            const userMessages = scrollUtils.getUserMessages(messages);

            expect(userMessages).toHaveLength(0);
        });
    });

    describe('getCurrentUserMessageIndex', () => {
        test('returns index of visible user message', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 50, offsetHeight: 50 });
            const userMsg2 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 150, offsetHeight: 50 });
            const userMsg3 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 250, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 100,
                scrollHeight: 1000,
                clientHeight: 200,
                children: [userMsg1, userMsg2, userMsg3],
            });

            const index = scrollUtils.getCurrentUserMessageIndex(messages);

            expect(index).toBe(1); // userMsg2 is visible
        });

        test('returns -1 when no user messages', () => {
            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 100,
                children: [],
            });

            const index = scrollUtils.getCurrentUserMessageIndex(messages);

            expect(index).toBe(-1);
        });

        test('returns first user message below viewport when none visible', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100, offsetHeight: 50 });
            const userMsg2 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 200, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 0,
                scrollHeight: 1000,
                clientHeight: 50, // Very small viewport
                children: [userMsg1, userMsg2],
            });

            const index = scrollUtils.getCurrentUserMessageIndex(messages);

            expect(index).toBe(0); // Returns first user message below viewport
        });
    });

    describe('scrollToPreviousUserMessage', () => {
        test('scrolls to previous user message', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100, offsetHeight: 50 });
            const userMsg2 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 200, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 180, // userMsg2 is visible
                scrollHeight: 1000,
                clientHeight: 200,
                children: [userMsg1, userMsg2],
            });

            scrollUtils.scrollToPreviousUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(80); // userMsg1.offsetTop - 20
        });

        test('scrolls to top when at first message', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 80,
                scrollHeight: 1000,
                clientHeight: 200,
                children: [userMsg1],
            });

            scrollUtils.scrollToPreviousUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(0);
        });

        test('scrolls to top when no user messages', () => {
            const messages = new MockElement({
                scrollTop: 100,
                scrollHeight: 1000,
                clientHeight: 200,
                children: [],
            });

            scrollUtils.scrollToPreviousUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(0);
        });
    });

    describe('scrollToNextUserMessage', () => {
        test('scrolls to next user message', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100, offsetHeight: 50 });
            const userMsg2 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 200, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 50, // userMsg1 is visible
                scrollHeight: 1000,
                clientHeight: 200,
                children: [userMsg1, userMsg2],
            });

            scrollUtils.scrollToNextUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(180); // userMsg2.offsetTop - 20
        });

        test('scrolls to bottom when at last message', () => {
            const userMsg1 = new MockMessageElement({ classList: ['message', 'user'], offsetTop: 100, offsetHeight: 50 });

            const messages = new MockElement({
                scrollTop: 80,
                scrollHeight: 1000,
                clientHeight: 200,
                children: [userMsg1],
            });

            scrollUtils.scrollToNextUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(1000);
        });

        test('scrolls to bottom when no user messages', () => {
            const messages = new MockElement({
                scrollTop: 100,
                scrollHeight: 1000,
                clientHeight: 200,
                children: [],
            });

            scrollUtils.scrollToNextUserMessage(messages, 20);

            expect(messages.scrollTop).toBe(1000);
        });
    });
});

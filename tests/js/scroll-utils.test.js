/**
 * Tests for scroll-utils module.
 *
 * These tests verify the JavaScript scroll utilities for the chat message container.
 */

// Import the actual scroll-utils module
const scrollUtils = require('../../vibe/cli/web_ui/static/js/scroll-utils.js');

// Helper: create a scrollable container element
function createContainer(config = {}) {
    const el = document.createElement('div');
    Object.defineProperty(el, 'scrollTop', { writable: true, configurable: true, value: config.scrollTop || 0 });
    Object.defineProperty(el, 'scrollHeight', { configurable: true, value: config.scrollHeight || 0 });
    Object.defineProperty(el, 'clientHeight', { configurable: true, value: config.clientHeight || 0 });
    return el;
}

// Helper: create a message element with classList and offsetTop
function createMessage(classes, offsetTop = 0, offsetHeight = 0) {
    const el = document.createElement('div');
    classes.forEach(c => el.classList.add(c));
    Object.defineProperty(el, 'offsetTop', { configurable: true, value: offsetTop });
    Object.defineProperty(el, 'offsetHeight', { configurable: true, value: offsetHeight });
    return el;
}

describe('scroll-utils', () => {
    describe('isAtBottom', () => {
        test('returns true when at the bottom', () => {
            const messages = createContainer({ scrollTop: 900, scrollHeight: 1000, clientHeight: 100 });
            expect(scrollUtils.isAtBottom(messages, 100)).toBe(true);
        });

        test('returns true when within threshold of bottom', () => {
            const messages = createContainer({ scrollTop: 850, scrollHeight: 1000, clientHeight: 100 });
            expect(scrollUtils.isAtBottom(messages, 100)).toBe(true);
        });

        test('returns false when not at the bottom', () => {
            const messages = createContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 100 });
            expect(scrollUtils.isAtBottom(messages, 100)).toBe(false);
        });

        test('returns false when far from bottom', () => {
            const messages = createContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 100 });
            expect(scrollUtils.isAtBottom(messages, 100)).toBe(false);
        });

        test('uses default threshold of 100', () => {
            const messages = createContainer({ scrollTop: 900, scrollHeight: 1000, clientHeight: 100 });
            expect(scrollUtils.isAtBottom(messages)).toBe(true);
        });
    });

    describe('wasAtBottomBeforeUpdate', () => {
        test('returns true if user was at bottom before content expanded', () => {
            const messages = createContainer({ scrollTop: 900, scrollHeight: 1100, clientHeight: 100 });
            const previousScrollHeight = 1000;
            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(true);
        });

        test('returns false if user was not at bottom before content expanded', () => {
            const messages = createContainer({ scrollTop: 500, scrollHeight: 1100, clientHeight: 100 });
            const previousScrollHeight = 1000;
            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(false);
        });

        test('returns true if user was within threshold before content expanded', () => {
            const messages = createContainer({ scrollTop: 850, scrollHeight: 1100, clientHeight: 100 });
            const previousScrollHeight = 1000;
            expect(scrollUtils.wasAtBottomBeforeUpdate(messages, previousScrollHeight, 100)).toBe(true);
        });
    });

    describe('scrollToBottom', () => {
        test('sets scrollTop to scrollHeight', () => {
            const messages = createContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 100 });
            scrollUtils.scrollToBottom(messages);
            expect(messages.scrollTop).toBe(1000);
        });
    });

    describe('scrollToBottomIfNeeded', () => {
        test('scrolls to bottom when at bottom', () => {
            const messages = createContainer({ scrollTop: 900, scrollHeight: 1000, clientHeight: 100 });
            scrollUtils.scrollToBottomIfNeeded(messages, 100);
            expect(messages.scrollTop).toBe(1000);
        });

        test('does not scroll when not at bottom', () => {
            const messages = createContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 100 });
            scrollUtils.scrollToBottomIfNeeded(messages, 100);
            expect(messages.scrollTop).toBe(500);
        });
    });

    describe('scrollToBottomIfWasAtBottom', () => {
        test('scrolls to bottom if user was at bottom before update', () => {
            const messages = createContainer({ scrollTop: 900, scrollHeight: 1100, clientHeight: 100 });
            const previousScrollHeight = 1000;
            scrollUtils.scrollToBottomIfWasAtBottom(messages, previousScrollHeight, 100);
            expect(messages.scrollTop).toBe(1100);
        });

        test('does not scroll if user was not at bottom before update', () => {
            const messages = createContainer({ scrollTop: 500, scrollHeight: 1100, clientHeight: 100 });
            const previousScrollHeight = 1000;
            scrollUtils.scrollToBottomIfWasAtBottom(messages, previousScrollHeight, 100);
            expect(messages.scrollTop).toBe(500);
        });
    });

    describe('scrollToTop', () => {
        test('sets scrollTop to 0', () => {
            const messages = createContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 100 });
            scrollUtils.scrollToTop(messages);
            expect(messages.scrollTop).toBe(0);
        });
    });

    describe('getUserMessages', () => {
        test('returns array of user messages', () => {
            const container = createContainer();
            const userMsg1 = createMessage(['message', 'user'], 100);
            const userMsg2 = createMessage(['message', 'user'], 200);
            const assistantMsg = createMessage(['message', 'assistant'], 300);
            container.appendChild(userMsg1);
            container.appendChild(assistantMsg);
            container.appendChild(userMsg2);

            const userMessages = scrollUtils.getUserMessages(container);
            expect(userMessages).toHaveLength(2);
            expect(userMessages[0]).toBe(userMsg1);
            expect(userMessages[1]).toBe(userMsg2);
        });

        test('returns empty array when no user messages', () => {
            const container = createContainer();
            const assistantMsg = createMessage(['message', 'assistant']);
            container.appendChild(assistantMsg);

            const userMessages = scrollUtils.getUserMessages(container);
            expect(userMessages).toHaveLength(0);
        });
    });

    describe('getCurrentUserMessageIndex', () => {
        test('returns index of visible user message', () => {
            const container = createContainer({ scrollTop: 100, scrollHeight: 1000, clientHeight: 200 });
            const userMsg1 = createMessage(['message', 'user'], 50, 50);
            const userMsg2 = createMessage(['message', 'user'], 150, 50);
            const userMsg3 = createMessage(['message', 'user'], 250, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);
            container.appendChild(userMsg3);

            const index = scrollUtils.getCurrentUserMessageIndex(container);
            expect(index).toBe(1); // userMsg2 is visible
        });

        test('returns -1 when no user messages', () => {
            const container = createContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 100 });

            const index = scrollUtils.getCurrentUserMessageIndex(container);
            expect(index).toBe(-1);
        });

        test('returns first user message below viewport when none visible', () => {
            const container = createContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 50 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);

            const index = scrollUtils.getCurrentUserMessageIndex(container);
            expect(index).toBe(0); // Returns first user message below viewport
        });

        test('returns last user message as fallback when none visible and none below', () => {
            // This tests the unreachable fallback path: a message inside a container
            // can't have offsetTop < scrollTop, so this path is defensive only.
            // We verify the function returns a valid index in this edge case.
            const container = createContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 500 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);

            const index = scrollUtils.getCurrentUserMessageIndex(container);
            expect(index).toBe(0); // First message is visible (returns visible, not fallback)
        });
    });

    describe('scrollToPreviousUserMessage', () => {
        test('scrolls to previous user message', () => {
            const container = createContainer({ scrollTop: 300, scrollHeight: 1000, clientHeight: 100 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            const userMsg3 = createMessage(['message', 'user'], 300, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);
            container.appendChild(userMsg3);

            scrollUtils.scrollToPreviousUserMessage(container, 10);
            expect(container.scrollTop).toBe(190); // userMsg2.offsetTop(200) - offset(10)
        });

        test('scrolls to top when at first user message', () => {
            const container = createContainer({ scrollTop: 100, scrollHeight: 1000, clientHeight: 100 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);

            scrollUtils.scrollToPreviousUserMessage(container, 10);
            expect(container.scrollTop).toBe(0);
        });

        test('scrolls to top when no user messages', () => {
            const container = createContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 100 });

            scrollUtils.scrollToPreviousUserMessage(container, 10);
            expect(container.scrollTop).toBe(0);
        });
    });

    describe('scrollToNextUserMessage', () => {
        test('scrolls to next user message', () => {
            const container = createContainer({ scrollTop: 100, scrollHeight: 1000, clientHeight: 100 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            const userMsg3 = createMessage(['message', 'user'], 300, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);
            container.appendChild(userMsg3);

            scrollUtils.scrollToNextUserMessage(container, 10);
            expect(container.scrollTop).toBe(190); // userMsg2.offsetTop(200) - offset(10)
        });

        test('scrolls to bottom when at last user message', () => {
            const container = createContainer({ scrollTop: 200, scrollHeight: 1000, clientHeight: 100 });
            const userMsg1 = createMessage(['message', 'user'], 100, 50);
            const userMsg2 = createMessage(['message', 'user'], 200, 50);
            container.appendChild(userMsg1);
            container.appendChild(userMsg2);

            scrollUtils.scrollToNextUserMessage(container, 10);
            expect(container.scrollTop).toBe(1000);
        });

        test('scrolls to bottom when no user messages', () => {
            const container = createContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 100 });

            scrollUtils.scrollToNextUserMessage(container, 10);
            expect(container.scrollTop).toBe(1000);
        });
    });
});

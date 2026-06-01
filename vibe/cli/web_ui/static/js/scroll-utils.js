/**
 * Scroll utilities for chat message container.
 * Provides functions to check scroll position and scroll to bottom conditionally.
 */

/**
 * Check if the messages container is scrolled to the bottom.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} threshold - Pixels from bottom to consider "at bottom" (default: 100)
 * @returns {boolean} True if within threshold of bottom
 */
function isAtBottom(messages, threshold = 100) {
    return messages.scrollHeight - messages.scrollTop - messages.clientHeight < threshold;
}

/**
 * Check if user was at bottom before content was added.
 * This handles the case where content expands and pushes the bottom down.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} previousScrollHeight - The scroll height before content was added
 * @param {number} threshold - Pixels from bottom to consider "at bottom" (default: 100)
 * @returns {boolean} True if user was at bottom before the update
 */
function wasAtBottomBeforeUpdate(messages, previousScrollHeight, threshold = 100) {
    return previousScrollHeight - messages.scrollTop - messages.clientHeight < threshold;
}

/**
 * Scroll to bottom of the messages container.
 * @param {HTMLElement} messages - The messages container element
 */
function scrollToBottom(messages) {
    messages.scrollTop = messages.scrollHeight;
}

/**
 * Scroll to bottom only if already at the bottom.
 * This prevents disrupting the user's reading position.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} threshold - Pixels from bottom to consider "at bottom" (default: 100)
 */
function scrollToBottomIfNeeded(messages, threshold = 100) {
    if (isAtBottom(messages, threshold)) {
        scrollToBottom(messages);
    }
}

/**
 * Scroll to bottom if user was at bottom before the update.
 * This handles expanding content that pushes the bottom down.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} previousScrollHeight - The scroll height before content was added
 * @param {number} threshold - Pixels from bottom to consider "at bottom" (default: 100)
 */
function scrollToBottomIfWasAtBottom(messages, previousScrollHeight, threshold = 100) {
    if (wasAtBottomBeforeUpdate(messages, previousScrollHeight, threshold)) {
        scrollToBottom(messages);
    }
}

/**
 * Scroll to top of the messages container.
 * @param {HTMLElement} messages - The messages container element
 */
function scrollToTop(messages) {
    messages.scrollTop = 0;
}

/**
 * Get all user message elements from the messages container.
 * @param {HTMLElement} messages - The messages container element
 * @returns {HTMLElement[]} Array of user message elements
 */
function getUserMessages(messages) {
    return Array.from(messages.querySelectorAll('.message.user'));
}

/**
 * Get the index of the closest user message to the current scroll position.
 * @param {HTMLElement} messages - The messages container element
 * @returns {number} Index of the current user message, or -1 if none found
 */
function getCurrentUserMessageIndex(messages) {
    const userMessages = getUserMessages(messages);
    if (userMessages.length === 0) return -1;

    const scrollTop = messages.scrollTop;
    const containerTop = scrollTop;
    const containerBottom = scrollTop + messages.clientHeight;

    // Find user messages that are currently visible
    let visibleUserMessages = [];
    userMessages.forEach((msg, idx) => {
        const msgTop = msg.offsetTop;
        if (msgTop >= containerTop && msgTop < containerBottom) {
            visibleUserMessages.push(idx);
        }
    });

    if (visibleUserMessages.length > 0) {
        // Return the first visible user message
        return visibleUserMessages[0];
    }

    // If no user messages visible, find the closest one below
    for (let i = 0; i < userMessages.length; i++) {
        if (userMessages[i].offsetTop >= containerBottom) {
            return i;
        }
    }

    // Fallback: return the last user message
    return userMessages.length - 1;
}

/**
 * Scroll to previous user message.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} offset - Pixels above the message to scroll to (default: 20)
 */
function scrollToPreviousUserMessage(messages, offset = 20) {
    const currentIndex = getCurrentUserMessageIndex(messages);
    const userMessages = getUserMessages(messages);

    if (currentIndex <= 0 || userMessages.length === 0) {
        scrollToTop(messages);
        return;
    }

    const targetIndex = currentIndex - 1;
    const targetMessage = userMessages[targetIndex];
    messages.scrollTop = targetMessage.offsetTop - offset;
}

/**
 * Scroll to next user message.
 * @param {HTMLElement} messages - The messages container element
 * @param {number} offset - Pixels above the message to scroll to (default: 20)
 */
function scrollToNextUserMessage(messages, offset = 20) {
    const currentIndex = getCurrentUserMessageIndex(messages);
    const userMessages = getUserMessages(messages);

    if (currentIndex < 0 || userMessages.length === 0) {
        scrollToBottom(messages);
        return;
    }

    if (currentIndex >= userMessages.length - 1) {
        scrollToBottom(messages);
        return;
    }

    const targetIndex = currentIndex + 1;
    const targetMessage = userMessages[targetIndex];
    messages.scrollTop = targetMessage.offsetTop - offset;
}

// Export for CommonJS (Jest) and ES modules (browser)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        isAtBottom,
        wasAtBottomBeforeUpdate,
        scrollToBottom,
        scrollToBottomIfNeeded,
        scrollToBottomIfWasAtBottom,
        scrollToTop,
        getUserMessages,
        getCurrentUserMessageIndex,
        scrollToPreviousUserMessage,
        scrollToNextUserMessage,
    };
}

// ES module export for browser
export {
    isAtBottom,
    wasAtBottomBeforeUpdate,
    scrollToBottom,
    scrollToBottomIfNeeded,
    scrollToBottomIfWasAtBottom,
    scrollToTop,
    getUserMessages,
    getCurrentUserMessageIndex,
    scrollToPreviousUserMessage,
    scrollToNextUserMessage,
};

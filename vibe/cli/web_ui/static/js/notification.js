/**
 * Browser Notification Module
 *
 * Handles desktop notifications for the WebUI.
 * Extracted from app.js for testability.
 */

/**
 * Create and configure a notification
 * @param {string} title
 * @param {string|null} message
 * @returns {Notification|null} The notification or null if not created
 */
export function createNotification(title, message = null) {
    if (!('Notification' in window)) {
        console.log('[Notification] Desktop notifications not supported');
        return null;
    }

    if (Notification.permission === 'granted') {
        const notification = new Notification(title, {
            body: message || '',
            tag: `vibe-${Date.now()}`,
            requireInteraction: false,
        });

        return notification;
    }

    return null;
}

/**
 * Configure notification behavior (auto-dismiss and click handler)
 * @param {Notification} notification
 * @param {number} dismissDelayMs
 */
export function configureNotification(notification, dismissDelayMs = 5000) {
    // Auto-dismiss after delay
    setTimeout(() => {
        notification.close();
    }, dismissDelayMs);

    // Focus the page when notification is clicked
    notification.onclick = () => {
        window.focus();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    };
}

/**
 * Show browser notification
 * @param {string} title
 * @param {string|null} message
 */
export function showBrowserNotification(title, message = null) {
    if (!('Notification' in window)) {
        console.log('[Notification] Desktop notifications not supported');
        return false;
    }

    if (Notification.permission === 'granted') {
        const notification = createNotification(title, message);
        if (notification) {
            configureNotification(notification);
            return true;
        }
        return false;
    } else if (Notification.permission !== 'denied') {
        // Request permission on first notification
        return Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                return showBrowserNotification(title, message);
            }
            return false;
        });
    }

    return false;
}

/**
 * Handle web notification event
 * @param {Object} event
 * @param {string} event.context - Notification context
 * @param {string} event.title - Notification title
 * @param {string|null} event.message - Optional message
 * @returns {boolean|Promise<boolean>} Whether notification was shown
 */
export function handleWebNotification(event) {
    const { title, message } = event;
    return showBrowserNotification(title, message);
}

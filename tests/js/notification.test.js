/**
 * Tests for notification.js module.
 *
 * Uses global mock for Notification API (setup in setup-notifications.js)
 * to avoid jsdom memory leaks.
 */

const {
    createNotification,
    configureNotification,
    showBrowserNotification,
} = require('../../vibe/cli/web_ui/static/js/notification.js');

describe('notification', () => {
    let origNotification;

    beforeEach(() => {
        origNotification = globalThis.Notification;
        jest.useFakeTimers();
    });

    afterEach(() => {
        globalThis.Notification = origNotification;
        jest.useRealTimers();
    });

    describe('createNotification', () => {
        test('returns null when Notification is not supported', () => {
            delete globalThis.Notification;
            expect(createNotification('Title')).toBeNull();
        });

        test('returns null when permission is denied', () => {
            globalThis.Notification = { permission: 'denied' };
            expect(createNotification('Title')).toBeNull();
        });

        test('returns null when permission is default (not granted)', () => {
            globalThis.Notification = { permission: 'default' };
            expect(createNotification('Title')).toBeNull();
        });

        test('creates and returns notification when permission is granted', () => {
            const mockNotif = { title: 'T', options: { body: 'B' } };
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            MockNotification.permission = 'granted';
            globalThis.Notification = MockNotification;

            const result = createNotification('My Title', 'My Body');

            expect(result).toBeDefined();
            expect(result.title).toBe('My Title');
            expect(result.options.body).toBe('My Body');
        });

        test('creates notification with empty body when message is null', () => {
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            MockNotification.permission = 'granted';
            globalThis.Notification = MockNotification;

            const result = createNotification('Title', null);

            expect(result.options.body).toBe('');
        });

        test('creates notification with empty body when message is undefined', () => {
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            MockNotification.permission = 'granted';
            globalThis.Notification = MockNotification;

            const result = createNotification('Title');

            expect(result.options.body).toBe('');
        });
    });

    describe('configureNotification', () => {
        test('sets up auto-dismiss timeout', () => {
            const mockNotif = { close: jest.fn(), onclick: null };
            configureNotification(mockNotif, 3000);

            expect(mockNotif.close).not.toHaveBeenCalled();
            jest.advanceTimersByTime(3000);
            expect(mockNotif.close).toHaveBeenCalledTimes(1);
        });

        test('uses default 5000ms delay', () => {
            const mockNotif = { close: jest.fn(), onclick: null };
            configureNotification(mockNotif);

            jest.advanceTimersByTime(4999);
            expect(mockNotif.close).not.toHaveBeenCalled();

            jest.advanceTimersByTime(1);
            expect(mockNotif.close).toHaveBeenCalledTimes(1);
        });

        test('sets onclick handler on notification', () => {
            const mockNotif = { close: jest.fn(), onclick: null };
            configureNotification(mockNotif, 5000);

            expect(mockNotif.onclick).toBeDefined();
            expect(typeof mockNotif.onclick).toBe('function');
        });
    });

    describe('showBrowserNotification', () => {
        test('returns false when Notification is not supported', () => {
            delete globalThis.Notification;
            const result = showBrowserNotification('Title', 'Body');
            expect(result).toBe(false);
        });

        test('returns true when permission is granted', () => {
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            MockNotification.permission = 'granted';
            globalThis.Notification = MockNotification;

            const result = showBrowserNotification('Title', 'Body');

            expect(result).toBe(true);
        });

        test('returns false when permission is denied', () => {
            globalThis.Notification = { permission: 'denied' };

            const result = showBrowserNotification('Title', 'Body');

            expect(result).toBe(false);
        });

        test('requests permission when permission is default', async () => {
            let perm = 'default';
            const mockReqPerms = jest.fn().mockImplementation(() => {
                perm = 'granted';
                return Promise.resolve('granted');
            });
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            Object.defineProperty(MockNotification, 'permission', {
                get: () => perm,
            });
            MockNotification.requestPermission = mockReqPerms;
            globalThis.Notification = MockNotification;

            const result = await showBrowserNotification('Title', 'Body');

            expect(mockReqPerms).toHaveBeenCalled();
            expect(result).toBe(true);
        });

        test('returns false when permission request is denied', async () => {
            let perm = 'default';
            const mockReqPerms = jest.fn().mockImplementation(() => {
                perm = 'denied';
                return Promise.resolve('denied');
            });
            const MockNotification = function (t, o) {
                return { title: t, options: o };
            };
            Object.defineProperty(MockNotification, 'permission', {
                get: () => perm,
            });
            MockNotification.requestPermission = mockReqPerms;
            globalThis.Notification = MockNotification;

            const result = await showBrowserNotification('Title', 'Body');

            expect(mockReqPerms).toHaveBeenCalled();
            expect(result).toBe(false);
        });
    });
});

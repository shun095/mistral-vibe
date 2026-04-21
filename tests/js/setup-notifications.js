/**
 * Jest setup file - mocks the Notification API globally.
 *
 * This avoids jsdom's native Notification constructor which causes
 * memory leaks (jsdom defers via process.nextTick).
 * See: https://stackoverflow.com/questions/13893163
 */

globalThis.Notification = {
    permission: 'default',
    requestPermission: jest.fn().mockResolvedValue('granted'),
};

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

// Mock marked (loaded from CDN in browser, not available in Jest)
class FakeRenderer {
    table(token) {
        return `<table><thead>${token?.header ?? ''}</thead><tbody>${token?.rows ?? ''}</tbody></table>`;
    }
}
globalThis.marked = {
    Renderer: FakeRenderer,
    parse: (text) => `<p>${text}</p>`,
    use: jest.fn(),
};

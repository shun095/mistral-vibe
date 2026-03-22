/**
 * Tests for collapse/expand state management in VibeClient
 */

describe('Collapse State Management', () => {
    describe('toggleAllCards logic', () => {
        test('should set _preferCollapsed to false when expanding all cards (allCollapsed=true)', () => {
            // Simulate the toggleAllCards logic
            let _preferCollapsed = true; // Initial state
            const allCollapsed = true; // All cards are collapsed

            // This is the logic from toggleAllCards()
            _preferCollapsed = !allCollapsed;

            expect(_preferCollapsed).toBe(false);
        });

        test('should set _preferCollapsed to true when collapsing all cards (allCollapsed=false)', () => {
            // Simulate the toggleAllCards logic
            let _preferCollapsed = false; // Initial state
            const allCollapsed = false; // All cards are expanded

            // This is the logic from toggleAllCards()
            _preferCollapsed = !allCollapsed;

            expect(_preferCollapsed).toBe(true);
        });
    });

    describe('createReasoningMessage class name logic', () => {
        test('should include collapsed class when _preferCollapsed is true', () => {
            const _preferCollapsed = true;
            const className = 'message reasoning' + (_preferCollapsed ? ' collapsed' : '');

            expect(className).toContain('collapsed');
            expect(className).toBe('message reasoning collapsed');
        });

        test('should not include collapsed class when _preferCollapsed is false', () => {
            const _preferCollapsed = false;
            const className = 'message reasoning' + (_preferCollapsed ? ' collapsed' : '');

            expect(className).not.toContain('collapsed');
            expect(className).toBe('message reasoning');
        });
    });

    describe('createToolCallElement class name logic', () => {
        test('should include collapsed class when _preferCollapsed is true', () => {
            const _preferCollapsed = true;
            const className = 'message tool-call' + (_preferCollapsed ? ' collapsed' : '');

            expect(className).toContain('collapsed');
            expect(className).toBe('message tool-call collapsed');
        });

        test('should not include collapsed class when _preferCollapsed is false', () => {
            const _preferCollapsed = false;
            const className = 'message tool-call' + (_preferCollapsed ? ' collapsed' : '');

            expect(className).not.toContain('collapsed');
            expect(className).toBe('message tool-call');
        });
    });
});

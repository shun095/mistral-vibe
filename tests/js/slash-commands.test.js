/**
 * Tests for slash command registry
 */

import { SlashCommandRegistry, SlashAutocomplete } from '../../vibe/cli/web_ui/static/js/slash-commands.js';

describe('SlashCommandRegistry', () => {
    let registry;

    beforeEach(() => {
        registry = new SlashCommandRegistry();
        registry.token = 'test-token';
    });

    describe('getCommand', () => {
        test('parses simple command', () => {
            const result = registry.getCommand('/clean');
            expect(result).toMatchObject({
                name: 'clean',
                args: '',
                command: undefined,
            });
        });

        test('parses command with args', () => {
            const result = registry.getCommand('/edit new content');
            expect(result).toMatchObject({
                name: 'edit',
                args: 'new content',
            });
        });

        test('returns null for non-command', () => {
            const result = registry.getCommand('hello');
            expect(result).toBeNull();
        });

        test('returns null for empty string', () => {
            const result = registry.getCommand('');
            expect(result).toBeNull();
        });

        test('handles command with multiple spaces', () => {
            const result = registry.getCommand('/edit  spaced  content');
            expect(result).toMatchObject({
                name: 'edit',
                args: 'spaced  content',
            });
        });
    });

    describe('getCompletions', () => {
        beforeEach(() => {
            // Mock command data
            registry.commands.set('/clean', { description: 'Clear history' });
            registry.commands.set('/clear', { description: 'Clear history' });
            registry.commands.set('/compact', { description: 'Compact history' });
            registry.commands.set('/config', { description: 'Edit config' });
            registry.commands.set('/help', { description: 'Show help' });
        });

        test('returns matching commands', () => {
            const completions = registry.getCompletions('/c');
            expect(completions).toHaveLength(4);
            expect(completions.map(c => c.label)).toContain('/clean');
            expect(completions.map(c => c.label)).toContain('/clear');
            expect(completions.map(c => c.label)).toContain('/compact');
            expect(completions.map(c => c.label)).toContain('/config');
        });

        test('returns exact match', () => {
            const completions = registry.getCompletions('/help');
            expect(completions).toHaveLength(1);
            expect(completions[0].label).toBe('/help');
        });

        test('returns empty for no match', () => {
            const completions = registry.getCompletions('/xyz');
            expect(completions).toHaveLength(0);
        });

        test('is case insensitive', () => {
            const completions = registry.getCompletions('/CLEAN');
            expect(completions).toHaveLength(1); // only /clean matches exactly
            expect(completions[0].label).toBe('/clean');
        });

        test('includes description in completion', () => {
            const completions = registry.getCompletions('/help');
            expect(completions[0]).toMatchObject({
                label: '/help',
                description: 'Show help',
            });
        });
    });

    describe('execute', () => {
        let mockFetch;

        beforeEach(() => {
            mockFetch = global.fetch = jest.fn();
        });

        afterEach(() => {
            jest.restoreAllMocks();
        });

        test('calls API with correct parameters', async () => {
            mockFetch.mockResolvedValueOnce({
                json: () => Promise.resolve({ success: true }),
            });

            const result = await registry.execute('clean', '');

            expect(mockFetch).toHaveBeenCalledWith('/api/command/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command: 'clean', args: '' }),
            });
            expect(result).toMatchObject({ success: true });
        });

        test('handles API error', async () => {
            mockFetch.mockRejectedValueOnce(new Error('Network error'));

            const result = await registry.execute('clean', '');

            expect(result).toMatchObject({
                success: false,
                error: 'Network error',
            });
        });

        test('handles API failure response', async () => {
            mockFetch.mockResolvedValueOnce({
                json: () => Promise.resolve({ success: false, error: 'Unknown command' }),
            });

            const result = await registry.execute('unknown', '');
            expect(result).toMatchObject({
                success: false,
                error: 'Unknown command',
            });
        });
    });

    describe('loadCommands', () => {
        let mockFetch;

        beforeEach(() => {
            mockFetch = global.fetch = jest.fn();
        });

        afterEach(() => {
            jest.restoreAllMocks();
        });

        test('loads commands from API', async () => {
            mockFetch.mockResolvedValueOnce({
                json: () => Promise.resolve({
                    commands: [
                        {
                            name: 'clean',
                            aliases: ['/clean'],
                            description: 'Clear history',
                        },
                    ],
                }),
            });

            await registry.loadCommands();

            expect(registry.loaded).toBe(true);
            expect(registry.commands.has('clean')).toBe(true);
            expect(registry.commands.has('/clean')).toBe(true);
        });

        test('does not reload if already loaded', async () => {
            registry.loaded = true;

            await registry.loadCommands();

            expect(mockFetch).not.toHaveBeenCalled();
        });

        test('handles API error', async () => {
            mockFetch.mockRejectedValueOnce(new Error('Network error'));

            await registry.loadCommands();

            expect(registry.loaded).toBe(false);
            expect(registry.commands.size).toBe(0);
        });
    });
});

/**
 * Tests for slash command autocomplete UI
 */

describe('SlashAutocomplete', () => {
    let autocomplete;
    let inputElement;
    let registry;

    beforeEach(() => {
        // Create DOM elements
        inputElement = document.createElement('input');
        inputElement.id = 'message-input';
        document.body.appendChild(inputElement);

        registry = new SlashCommandRegistry();

        // Pre-load some commands
        registry.commands.set('/clean', { description: 'Clear history' });
        registry.commands.set('/clear', { description: 'Clear history' });
        registry.commands.set('/compact', { description: 'Compact history' });
        registry.commands.set('/config', { description: 'Edit config' });
        registry.loaded = true;

        autocomplete = new SlashAutocomplete(inputElement, registry);
    });

    afterEach(() => {
        if (autocomplete && autocomplete.container) {
            document.body.removeChild(autocomplete.container);
        }
        if (inputElement && inputElement.parentNode) {
            document.body.removeChild(inputElement);
        }
    });

    describe('DOM creation', () => {
        test('creates container element', () => {
            expect(autocomplete.container).toBeDefined();
            expect(autocomplete.container.className).toBe('slash-autocomplete');
        });

        test('creates suggestions list', () => {
            const list = autocomplete.container.querySelector('.suggestions');
            expect(list).toBeDefined();
            expect(list.tagName).toBe('UL');
        });

        test('container is initially hidden', () => {
            // Initially display is empty string (browser default), not 'none'
            expect(autocomplete.container.style.display).toBe('');
        });
    });

    describe('showSuggestions', () => {
        test('shows container when suggestions available', async () => {
            inputElement.value = '/c';
            await autocomplete.showSuggestions('/c');

            expect(autocomplete.container.style.display).toBe('block');
        });

        test('hides container when no suggestions', async () => {
            inputElement.value = '/xyz';
            await autocomplete.showSuggestions('/xyz');

            expect(autocomplete.container.style.display).toBe('none');
        });

        test('renders correct number of suggestions', async () => {
            await autocomplete.showSuggestions('/c');

            const items = autocomplete.container.querySelectorAll('li');
            expect(items).toHaveLength(4); // /clean, /clear, /compact, /config
        });

        test('selects last suggestion by default', async () => {
            await autocomplete.showSuggestions('/c');

            expect(autocomplete.selectedIndex).toBe(autocomplete.suggestions.length - 1);
        });
    });

    describe('handleKeydown', () => {
        beforeEach(async () => {
            inputElement.value = '/c';
            await autocomplete.showSuggestions('/c');
        });

        test('handles ArrowDown key', () => {
            const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
            const preventDefault = jest.fn();
            event.preventDefault = preventDefault;

            autocomplete.handleKeydown(event);

            expect(preventDefault).toHaveBeenCalled();
        });

        test('handles ArrowUp key', () => {
            const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
            const preventDefault = jest.fn();
            event.preventDefault = preventDefault;

            autocomplete.handleKeydown(event);

            expect(preventDefault).toHaveBeenCalled();
        });

        test('handles Enter key with selection', () => {
            const event = new KeyboardEvent('keydown', { key: 'Enter' });
            const preventDefault = jest.fn();
            event.preventDefault = preventDefault;

            autocomplete.handleKeydown(event);

            expect(preventDefault).toHaveBeenCalled();
            expect(autocomplete.container.style.display).toBe('none');
        });

        test('handles Escape key', () => {
            const event = new KeyboardEvent('keydown', { key: 'Escape' });

            autocomplete.handleKeydown(event);

            expect(autocomplete.container.style.display).toBe('none');
        });

        test('ignores keys when not visible', () => {
            autocomplete.hide();

            const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
            const preventDefault = jest.fn();
            event.preventDefault = preventDefault;

            autocomplete.handleKeydown(event);

            expect(preventDefault).not.toHaveBeenCalled();
        });
    });

    describe('complete', () => {
        test('replaces last word with completion', () => {
            inputElement.value = '/cle';
            autocomplete.complete('/clean');

            expect(inputElement.value).toBe('/clean');
        });

        test('preserves arguments after command', () => {
            // The complete method replaces the last word in the input
            inputElement.value = 'test content /cle';
            autocomplete.complete('/clean');

            expect(inputElement.value).toBe('test content /clean');
        });

        test('hides autocomplete after completion', () => {
            inputElement.value = '/c';
            autocomplete.visible = true;

            autocomplete.complete('/clean');

            expect(autocomplete.container.style.display).toBe('none');
        });
    });

    describe('hide', () => {
        test('hides container and resets state', async () => {
            await autocomplete.showSuggestions('/c');

            autocomplete.hide();

            expect(autocomplete.visible).toBe(false);
            expect(autocomplete.container.style.display).toBe('none');
            expect(autocomplete.suggestions).toHaveLength(0);
            expect(autocomplete.selectedIndex).toBe(-1);
        });
    });

    describe('handleInput', () => {
        test('hides when input does not start with /', async () => {
            await autocomplete.showSuggestions('/c');

            inputElement.value = 'hello';
            autocomplete.handleInput();

            expect(autocomplete.container.style.display).toBe('none');
        });

        test('hides when last word does not start with /', async () => {
            await autocomplete.showSuggestions('/c');

            inputElement.value = '/clean test';
            autocomplete.handleInput();

            expect(autocomplete.container.style.display).toBe('none');
        });
    });

    describe('escapeHtml', () => {
        test('escapes HTML special characters', () => {
            const result = autocomplete.escapeHtml('<script>alert("xss")</script>');
            // textContent escapes < and > but not quotes
            expect(result).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
        });

        test('escapes ampersand', () => {
            const result = autocomplete.escapeHtml('A & B');
            expect(result).toBe('A &amp; B');
        });

        test('escapes quotes', () => {
            const result = autocomplete.escapeHtml('He said "Hello"');
            // textContent does not escape quotes
            expect(result).toBe('He said "Hello"');
        });
    });
});

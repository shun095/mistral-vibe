/**
 * Tests for tool-formatters.js module.
 */

const {
    getIconForMimeType,
    triggerDownload,
    createCardHeader,
    createCodeBlock,
    createOutputSection,
    detectLanguageFromPath,
    formatToolResult,
    truncatePathFromStart,
    getFormatterHelpers,
} = require('../../vibe/cli/web_ui/static/js/tool-formatters.js');

describe('tool-formatters', () => {
    describe('getIconForMimeType', () => {
        test('returns image icon for image types', () => {
            expect(getIconForMimeType('image/png')).toBe('image');
            expect(getIconForMimeType('image/jpeg')).toBe('image');
        });

        test('returns description icon for text types', () => {
            expect(getIconForMimeType('text/plain')).toBe('description');
            expect(getIconForMimeType('text/html')).toBe('description');
        });

        test('returns pdf icon for pdf types', () => {
            expect(getIconForMimeType('application/pdf')).toBe('picture_as_pdf');
        });

        test('returns archive icon for compressed types', () => {
            expect(getIconForMimeType('application/zip')).toBe('archive');
            expect(getIconForMimeType('application/x-compressed')).toBe('archive');
        });

        test('returns code icon for code types', () => {
            expect(getIconForMimeType('application/vnd+xml')).toBe('code');
        });

        test('returns description as default', () => {
            expect(getIconForMimeType('application/octet-stream')).toBe('description');
        });
    });

    describe('detectLanguageFromPath', () => {
        test('detects common languages', () => {
            expect(detectLanguageFromPath('file.js')).toBe('javascript');
            expect(detectLanguageFromPath('file.ts')).toBe('typescript');
            expect(detectLanguageFromPath('file.py')).toBe('python');
            expect(detectLanguageFromPath('file.go')).toBe('go');
            expect(detectLanguageFromPath('file.rs')).toBe('rust');
        });

        test('detects shell scripts', () => {
            expect(detectLanguageFromPath('script.sh')).toBe('bash');
            expect(detectLanguageFromPath('script.bash')).toBe('bash');
        });

        test('detects markup languages', () => {
            expect(detectLanguageFromPath('file.html')).toBe('xml');
            expect(detectLanguageFromPath('file.xml')).toBe('xml');
        });

        test('detects config files', () => {
            expect(detectLanguageFromPath('file.yaml')).toBe('yaml');
            expect(detectLanguageFromPath('file.toml')).toBe('toml');
            expect(detectLanguageFromPath('file.ini')).toBe('ini');
        });

        test('detects markdown', () => {
            expect(detectLanguageFromPath('README.md')).toBe('markdown');
        });

        test('returns plaintext for unknown extensions', () => {
            expect(detectLanguageFromPath('file.unknown')).toBe('plaintext');
        });

        test('handles case insensitivity', () => {
            expect(detectLanguageFromPath('file.JS')).toBe('javascript');
            expect(detectLanguageFromPath('file.PY')).toBe('python');
        });
    });

    describe('createOutputSection', () => {
        test('creates section with correct class and content', () => {
            const section = createOutputSection('stdout', 'hello world');
            expect(section.className).toBe('bash-output-section stdout');
            expect(section.querySelector('.output-label').textContent).toBe('STDOUT');
            expect(section.querySelector('pre').textContent).toBe('hello world');
        });

        test('escapes HTML in content to prevent XSS', () => {
            const malicious = '<script>alert("xss")</script>';
            const section = createOutputSection('stderr', malicious);
            // Content should be escaped, not rendered as HTML
            expect(section.querySelector('pre').innerHTML).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
            // No script element should exist in the DOM
            expect(section.querySelectorAll('script').length).toBe(0);
        });

        test('uses provided escapeHtml helper', () => {
            const customEscape = jest.fn((t) => `[ESCAPED:${t}]`);
            const section = createOutputSection('stdout', 'raw', { escapeHtml: customEscape });
            expect(customEscape).toHaveBeenCalledWith('raw');
            expect(section.querySelector('pre').innerHTML).toBe('[ESCAPED:raw]');
        });
    });

    describe('createCardHeader', () => {
        test('creates card with header and content', () => {
            const card = document.createElement('div');
            createCardHeader(card, 'Test Title', '<span>icon</span>', 'Summary');

            expect(card.querySelector('.card-header')).not.toBeNull();
            expect(card.querySelector('.card-header').textContent).toContain('Test Title');
            expect(card.querySelector('.card-content')).not.toBeNull();
            expect(card.querySelector('.card-content pre').textContent).toBe('Summary');
        });

        test('creates card without summary', () => {
            const card = document.createElement('div');
            createCardHeader(card, 'Test Title', '<span>icon</span>', null);

            expect(card.querySelector('.card-header')).not.toBeNull();
            expect(card.querySelector('.card-content')).not.toBeNull();
            expect(card.querySelector('.card-content pre')).toBeNull();
        });
    });

    describe('createCodeBlock', () => {
        test('creates code block with correct structure', () => {
            const container = document.createElement('div');
            const block = createCodeBlock('test.py', 'print("hello")', container, 'python');

            expect(block.tagName).toBe('PRE');
            expect(block.querySelector('code').className).toBe('language-python');
            expect(block.querySelector('code').textContent).toBe('print("hello")');
        });

        test('defaults to plaintext language', () => {
            const container = document.createElement('div');
            const block = createCodeBlock('test', 'content', container);

            expect(block.querySelector('code').className).toBe('language-plaintext');
        });
    });

    describe('formatToolResult', () => {
        const helpers = {
            escapeHtml: (text) => {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            },
        };

        test('delegates to bash formatter', () => {
            const result = formatToolResult('bash', { returncode: 0, command: 'ls', stdout: 'file.txt' }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('Return code: 0');
        });

        test('delegates to websearch formatter', () => {
            const result = formatToolResult('websearch', { answer: 'Test answer', sources: [] }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('0 sources found');
        });

        test('delegates to webfetch formatter', () => {
            const result = formatToolResult('webfetch', { url: 'http://example.com', content: 'body', lines_read: 10, total_lines: 10 }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('Fetched 10/10 lines');
        });

        test('delegates to grep formatter', () => {
            const result = formatToolResult('grep', { pattern: 'test', matches: 'match1', match_count: 1 }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 matches found');
        });

        test('delegates to read_file formatter', () => {
            const result = formatToolResult('read_file', { path: '/test.py', content: 'code', lines_read: 5 }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('Read 5 lines');
        });

        test('delegates to edit_file formatter', () => {
            const result = formatToolResult('edit_file', { file: 'test.py', blocks_applied: 1, lines_changed: 5 }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 block(s) applied');
        });

        test('delegates to write_file formatter', () => {
            const result = formatToolResult('write_file', { path: '/test.py', content: 'code', bytes_written: 100, file_existed: false }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('100 bytes written');
        });

        test('delegates to lsp formatter', () => {
            const result = formatToolResult('lsp', { diagnostics: [], formatted_output: 'no issues' }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('No issues found');
        });

        test('delegates to todo formatter', () => {
            const result = formatToolResult('todo', { total_count: 3, todos: [{ content: 'Task 1', status: 'pending', priority: 'high' }] }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('3 total');
        });

        test('delegates to ask_user_question formatter', () => {
            const result = formatToolResult('ask_user_question', { answers: [], cancelled: false }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('0 answer(s)');
        });

        test('delegates to register_download formatter', () => {
            const result = formatToolResult('register_download', { filename: 'file.txt', file_path: '/tmp/file.txt', mime_type: 'text/plain' }, helpers);
            expect(result.className).toBe('download-card');
            expect(result.querySelector('.download-card-header')).not.toBeNull();
            expect(result.querySelector('.download-card-title').textContent).toContain('file.txt');
        });

        test('delegates to generic formatter for unknown tool', () => {
            const result = formatToolResult('unknown_tool', { data: 'value' }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('"data"');
        });

        test('handles lsp with errors and warnings', () => {
            const diagnostics = [
                { severity: 1, message: 'Error 1' },
                { severity: 2, message: 'Warning 1' },
            ];
            const result = formatToolResult('lsp', { diagnostics }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 error(s), 1 warning(s)');
        });

        test('handles ask_user_question with answers', () => {
            const result = formatToolResult('ask_user_question', {
                answers: [{ question: 'Q?', answer: 'A', is_other: false }],
                cancelled: false,
            }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 answer(s)');
        });

        test('handles ask_user_question with cancelled', () => {
            const result = formatToolResult('ask_user_question', { answers: [], cancelled: true }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('cancelled');
        });

        test('handles edit_file with warnings', () => {
            const result = formatToolResult('edit_file', {
                file: 'test.py',
                blocks_applied: 1,
                lines_changed: 5,
                warnings: ['Warning 1', 'Warning 2'],
            }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 block(s) applied');
        });

        test('handles edit_file with string warnings', () => {
            const result = formatToolResult('edit_file', {
                file: 'test.py',
                blocks_applied: 1,
                lines_changed: 5,
                warnings: JSON.stringify(['Warning 1']),
            }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('1 block(s) applied');
        });

        test('handles read_file with lsp diagnostics', () => {
            const result = formatToolResult('read_file', {
                path: '/test.py',
                content: 'code',
                lines_read: 5,
                lsp_diagnostics: '1 error, 0 warnings',
            }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('Read 5 lines');
        });

        test('handles webfetch with truncated content', () => {
            const lines = Array(150).fill('line').join('\n');
            const result = formatToolResult('webfetch', {
                url: 'http://example.com',
                content: lines,
                lines_read: 150,
                total_lines: 150,
                was_truncated: true,
            }, helpers);
            expect(result.className).toBe('tool-result-card');
            expect(result.querySelector('.card-header')).not.toBeNull();
            expect(result.querySelector('.card-content > pre').textContent).toContain('150/150 lines (truncated)');
        });
    });

    describe('getFormatterHelpers', () => {
        test('returns object with expected methods', () => {
            const mockClient = {
                escapeHtml: (text) => text,
            };
            const helpers = getFormatterHelpers(mockClient);
            expect(helpers.escapeHtml).toBeDefined();
            expect(helpers.createCardHeader).toBeDefined();
            expect(helpers.createCodeBlock).toBeDefined();
            expect(helpers.createOutputSection).toBeDefined();
            expect(helpers.getIconForMimeType).toBeDefined();
            expect(helpers.triggerDownload).toBeDefined();
            expect(helpers.detectLanguageFromPath).toBeDefined();
        });

        test('createCodeBlock wrapper adds dblclick handler calling showCodeFullscreen', () => {
            const showFs = jest.fn();
            const mockClient = {
                escapeHtml: (text) => { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; },
                showCodeFullscreen: showFs,
            };
            const helpers = getFormatterHelpers(mockClient);

            const container = { appendChild: jest.fn() };
            const block = helpers.createCodeBlock('test.py', 'print("hello")', container, 'python');

            expect(block.tagName).toBe('PRE');

            // Simulate double-click via dispatchEvent
            block.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));

            expect(showFs).toHaveBeenCalledWith('test.py', 'print("hello")', 'python', 0);
        });

        test('createCodeBlock wrapper skips showCodeFullscreen when not available', () => {
            const mockClient = {
                escapeHtml: (text) => { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; },
            };
            const helpers = getFormatterHelpers(mockClient);

            const container = { appendChild: jest.fn() };
            const block = helpers.createCodeBlock('test.py', 'content', container, 'python');

            // Should not throw when showCodeFullscreen is missing
            expect(() => block.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))).not.toThrow();
        });
    });

    describe('truncatePathFromStart', () => {
        test('returns path when it fits', () => {
            const mockContainer = {
                offsetWidth: 500,
                getBoundingClientRect: () => ({}),
            };
            const style = window.getComputedStyle;
            window.getComputedStyle = jest.fn(() => ({ fontSize: 14 }));

            const result = truncatePathFromStart('short.txt', mockContainer);
            expect(result).toBe('short.txt');

            window.getComputedStyle = style;
        });

        test('truncates long path from start', () => {
            const mockContainer = {
                offsetWidth: 200,
                getBoundingClientRect: () => ({}),
            };
            const style = window.getComputedStyle;
            window.getComputedStyle = jest.fn(() => ({ fontSize: 14 }));

            const result = truncatePathFromStart('/very/long/path/to/file.txt', mockContainer);

            window.getComputedStyle = style;
            expect(result).toBeDefined();
        });
    });

    describe('triggerDownload', () => {
        test('triggers download via fetch', async () => {
            const mockBlob = { type: 'text/plain' };
            const mockUrl = 'mock-url';
            const origCreateObjectURL = window.URL.createObjectURL;
            const origRevokeObjectURL = window.URL.revokeObjectURL;
            window.URL.createObjectURL = jest.fn(() => mockUrl);
            window.URL.revokeObjectURL = jest.fn();

            const mockResponse = {
                ok: true,
                blob: jest.fn().mockResolvedValue(mockBlob),
            };
            global.fetch = jest.fn().mockResolvedValue(mockResponse);

            const clickSpy = jest.fn();
            const origAppendChild = document.body.appendChild;
            const origRemoveChild = document.body.removeChild;
            document.body.appendChild = jest.fn((el) => {
                el.click = clickSpy;
                return el;
            });
            document.body.removeChild = jest.fn();

            await triggerDownload('/path/to/file.txt');

            expect(global.fetch).toHaveBeenCalledWith('/api/download?file_path=%2Fpath%2Fto%2Ffile.txt');
            expect(window.URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
            expect(clickSpy).toHaveBeenCalled();
            expect(window.URL.revokeObjectURL).toHaveBeenCalledWith(mockUrl);

            window.URL.createObjectURL = origCreateObjectURL;
            window.URL.revokeObjectURL = origRevokeObjectURL;
            document.body.appendChild = origAppendChild;
            document.body.removeChild = origRemoveChild;
        });

        test('handles fetch error gracefully', async () => {
            global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

            await expect(triggerDownload('/path/to/file.txt')).resolves.toBeUndefined();
        });
    });

    describe('formatToolResult', () => {
        test('formats bash result with returncode badge', () => {
            const card = document.createElement('div');
            card.innerHTML = '<div class="card-content"></div>';
            const result = {
                name: 'bash',
                stdout: 'output',
                stderr: 'error',
                returncode: 0,
            };

            const formatted = formatToolResult('bash', result, { escapeHtml: (t) => t });
            expect(formatted.className).toBe('tool-result-card');
            expect(formatted.querySelector('.bash-returncode.success')).not.toBeNull();
            expect(formatted.querySelector('.bash-returncode.success').textContent).toBe('Return code: 0');
        });

        test('formats web search result with sources', () => {
            const card = document.createElement('div');
            card.innerHTML = '<div class="card-content"></div>';
            const result = {
                name: 'websearch',
                answer: 'search answer',
                sources: [
                    { title: 'Source 1', url: 'https://example.com' },
                ],
            };

            const formatted = formatToolResult('websearch', result, { escapeHtml: (t) => t });
            expect(formatted.className).toBe('tool-result-card');
            expect(formatted.querySelectorAll('.search-source-item')).toHaveLength(1);
            expect(formatted.querySelector('.search-source-item .source-title').textContent).toBe('Source 1');
        });

        test('formats edit file result with content', () => {
            const card = document.createElement('div');
            card.innerHTML = '<div class="card-content"></div>';
            const result = {
                name: 'edit_file',
                file: 'test.txt',
                blocks_applied: 1,
                lines_changed: 10,
                content: '+ line\n- line',
            };

            const formatted = formatToolResult('edit_file', result, { escapeHtml: (t) => t });
            expect(formatted.className).toBe('tool-result-card');
            const codeBlock = formatted.querySelector('.tool-formatter-code-block');
            expect(codeBlock).not.toBeNull();
            expect(codeBlock.querySelector('code').textContent).toBe('+ line\n- line');
            expect(codeBlock.querySelector('code').className).toBe('language-diff');
        });

        test('formats ask_user_question result with answers', () => {
            const card = document.createElement('div');
            card.innerHTML = '<div class="card-content"></div>';
            const result = {
                name: 'ask_user_question',
                answers: [{ question: 'Q1', answer: 'A1' }],
            };

            const formatted = formatToolResult('ask_user_question', result, { escapeHtml: (t) => t });
            expect(formatted.className).toBe('tool-result-card');
        });

        test('formats register_download result with description', () => {
            const card = document.createElement('div');
            card.innerHTML = '<div class="card-content"></div>';
            const result = {
                name: 'register_download',
                file_path: '/path/to/file.txt',
                mime_type: 'text/plain',
                description: 'File description',
            };

            const formatted = formatToolResult('register_download', result, { escapeHtml: (t) => t });
            expect(formatted.className).toBe('download-card');
            const button = formatted.querySelector('.download-card-button');
            expect(button).not.toBeNull();
            expect(button.textContent).toContain('Download');
        });
    });
});

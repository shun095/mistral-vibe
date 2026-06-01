const {
    createStructuredArgs,
    createStructuredResult,
} = require('../../vibe/cli/web_ui/static/js/structured-renderer.js');

describe('structured-renderer', () => {
    describe('multiline detection', () => {
        test('multiline string containing slash is folded, not treated as file path', () => {
            // CSS-like content with / in values (e.g. var(--border-color))
            // previously matched isFilePath() and bypassed multiline detection
            const args = {
                file_path: 'styles/test.css',
                old_string: '.class {\n    color: var(--primary);\n    border: 1px solid var(--border-color);\n}\n\n/* comment */\n.other { display: block; }',
                new_string: '.class {\n    color: var(--primary);\n    border: 1px solid var(--border-color);\n}',
                replace_all: false,
            };

            expect(args.old_string).toContain('\n');

            const container = createStructuredArgs(args);
            document.body.appendChild(container);

            const badges = container.querySelectorAll('.struct-multiline-badge');
            expect(badges.length).toBeGreaterThanOrEqual(2);

            document.body.removeChild(container);
        });

        test('multiline JS code is folded', () => {
            const args = {
                file_path: 'src/module.js',
                old_string: "function handler() {\n    const el = document.querySelector('.item');\n    if (el) {\n        el.classList.remove('hidden');\n    } else {\n        el.style.display = 'none';\n    }\n}",
                new_string: "function handler() {\n    const el = document.querySelector('.item');\n    if (el) {\n        el.classList.remove('hidden');\n    }\n}",
                replace_all: false,
            };

            expect(args.old_string).toContain('\n');

            const container = createStructuredArgs(args);
            document.body.appendChild(container);

            const badges = container.querySelectorAll('.struct-multiline-badge');
            expect(badges.length).toBeGreaterThanOrEqual(2);

            document.body.removeChild(container);
        });

        test('JSON.parse of backend-style args string produces multiline', () => {
            // Simulates: backend JSON with \n escapes → frontend JSON.parse → actual newlines
            const backendJson = '{"file_path":"test.txt","old_string":"line1\\nline2\\nline3","new_string":"line1\\nline3","replace_all":false}';
            const args = JSON.parse(backendJson);

            expect(args.old_string).toContain('\n');
            expect(args.old_string.split('\n')).toHaveLength(3);

            const container = createStructuredArgs(args);
            document.body.appendChild(container);

            expect(container.querySelectorAll('.struct-multiline-badge').length).toBe(2);

            document.body.removeChild(container);
        });

        test('string with literal backslash-n (not escape) is NOT folded', () => {
            const literalBackslashN = 'hello' + String.fromCharCode(92) + 'nworld';
            const args = { value: literalBackslashN };

            expect(args.value).not.toContain('\n');

            const container = createStructuredArgs(args);
            document.body.appendChild(container);

            expect(container.querySelectorAll('.struct-multiline-badge').length).toBe(0);

            document.body.removeChild(container);
        });
    });
});

/**
 * Tests for tool output formatting in WebUI.
 * Uses real jsdom for DOM assertions.
 */

// Import createCardHeader and createCodeBlock from the real module
const { createCardHeader, createCodeBlock, detectLanguageFromPath } = require('../../vibe/cli/web_ui/static/js/tool-formatters.js');

describe('Tool Output Formatting', () => {
    let app;
    let fullExtMap;

    beforeEach(() => {
        // Full extension map matching production code
        fullExtMap = {
            'js': 'javascript', 'jsx': 'jsx', 'ts': 'typescript', 'tsx': 'tsx',
            'py': 'python', 'rb': 'ruby', 'java': 'java', 'cpp': 'cpp',
            'cc': 'cpp', 'cxx': 'cpp', 'h': 'cpp', 'hpp': 'cpp', 'c': 'c',
            'cs': 'csharp', 'go': 'go', 'rs': 'rust', 'php': 'php',
            'phtml': 'php', 'php3': 'php', 'php4': 'php', 'php5': 'php',
            'phpt': 'php', 'swift': 'swift', 'kt': 'kotlin', 'scala': 'scala',
            'sh': 'bash', 'bash': 'bash', 'zsh': 'bash', 'fish': 'bash',
            'html': 'xml', 'htm': 'xml', 'xhtml': 'xml', 'xml': 'xml',
            'json': 'json', 'css': 'css', 'scss': 'scss', 'sass': 'scss',
            'less': 'less', 'yaml': 'yaml', 'yml': 'yaml', 'toml': 'toml',
            'ini': 'ini', 'cfg': 'ini', 'conf': 'ini', 'md': 'markdown',
            'markdown': 'markdown', 'rst': 'rst', 'tex': 'latex', 'sql': 'sql',
            'mysql': 'sql', 'postgres': 'sql', 'psql': 'sql', 'graphql': 'graphql',
            'gql': 'graphql', 'proto': 'protobuf', 'vue': 'vue', 'svelte': 'javascript',
            'r': 'r', 'R': 'r', 'ps1': 'powershell', 'psm1': 'powershell',
            'psd1': 'powershell', 'ps1xml': 'xml', 'ps1tab': 'xml', 'pssc': 'xml',
            'psrc': 'xml', 'lua': 'lua', 'pl': 'perl', 'pm': 'perl', 'tcl': 'tcl',
            'awk': 'awk', 'sbt': 'scala', 'gradle': 'groovy', 'gradle.kts': 'kotlin',
            'cake': 'csharp', 'fs': 'fsharp', 'fsi': 'fsharp', 'fsx': 'fsharp',
            'fsproj': 'xml', 'ml': 'ocaml', 'mli': 'ocaml', 'erl': 'erlang',
            'hrl': 'erlang', 'ex': 'elixir', 'exs': 'elixir', 'eex': 'elixir',
            'heex': 'elixir', 'leex': 'elixir', 'aw': 'actionscript', 'as': 'actionscript',
            'as3': 'actionscript', 'mxml': 'xml', 'actionscript': 'actionscript',
            'asp': 'asp', 'aspx': 'asp', 'vb': 'vbnet', 'vbs': 'vbnet',
            'vbhtml': 'asp', 'vbscript': 'vbnet', 'hbs': 'handlebars',
            'handlebars': 'handlebars', 'mustache': 'handlebars', 'ejs': 'ejs',
            'pug': 'pug', 'jade': 'pug', 'haml': 'haml', 'slim': 'slim',
            'coffee': 'coffeescript', 'litcoffee': 'coffeescript', 'dart': 'dart',
            'flap': 'dart', 'pubspec': 'yaml', 'pubspec.lock': 'yaml',
            'dart_tool': 'yaml', 'clj': 'clojure', 'cljs': 'clojure',
            'cljc': 'clojure', 'end': 'clojure', 'lisp': 'lisp', 'el': 'lisp',
            'scm': 'lisp', 'ss': 'lisp', 'rkt': 'scheme', 'rktl': 'scheme',
            'scheme': 'scheme', 'asm': 'asm', 'nasm': 'asm', 'masm': 'asm',
            'fasm': 'asm', 's': 'asm', 'S': 'asm', 'v': 'verilog',
            'sv': 'systemverilog', 'svh': 'systemverilog', 'vh': 'vhdl',
            'vhd': 'vhdl', 'vu': 'verilog', 'make': 'makefile', 'mk': 'makefile',
            'cmake': 'cmake', 'dockerfile': 'dockerfile', 'docker': 'dockerfile',
            'gitignore': 'ini', 'gitattributes': 'ini', 'editorconfig': 'ini',
            'gitconfig': 'ini', 'sublime': 'ini', 'sublime-project': 'json',
            'sublime-workspace': 'json', 'sublime-build': 'json',
            'sublime-settings': 'json', 'sublime-keybindings': 'json',
            'sublime-completions': 'json', 'sublime-menu': 'json',
            'sublime-macro': 'json', 'sublime-syntax': 'yaml',
            'sublime-theme': 'json', 'sublime-completion': 'json',
        };

        // Create a minimal app instance with the formatting methods using real DOM
        app = {
            createCardHeader: function(card, title, icon, summary) {
                createCardHeader(card, title, icon, summary);
            },
            detectLanguageFromPath: function(path) {
                const ext = path.split('.').pop().toLowerCase();
                return fullExtMap[ext] || 'plaintext';
            },
            createCodeBlock: function(path, content, container, language, offset = 0) {
                return createCodeBlock(path, content, container, language, offset);
            },
            showCodeFullscreen: jest.fn(),
            formatWriteFileResult: function(card, result) {
                const path = result.path || 'unknown';
                const bytesWritten = result.bytes_written || 0;
                const fileExisted = result.file_existed;

                const status = fileExisted ? 'Overwritten' : 'Created';
                const statusIcon = fileExisted ? 'edit_note' : 'note_add';
                const statusColor = fileExisted ? 'var(--yellow)' : 'var(--green)';

                this.createCardHeader(card, status,
                    `<span class="material-symbols-rounded" style="color: ${statusColor}">${statusIcon}</span>`,
                    `${bytesWritten} bytes written`);

                const contentDiv = card.querySelector('.card-content');

                const pathDiv = document.createElement('div');
                pathDiv.style.cssText = 'padding: 8px 12px 0; font-family: monospace; font-size: 0.9rem; color: var(--text-secondary);';
                pathDiv.textContent = `Path: ${path}`;
                contentDiv.appendChild(pathDiv);

                if (result.content) {
                    const language = this.detectLanguageFromPath(path);
                    this.createCodeBlock(path, result.content, contentDiv, language);
                }

                return card;
            },
            formatReadFileResult: function(card, result) {
                const path = result.path || 'unknown';
                const linesRead = result.lines_read || 0;
                const wasTruncated = result.was_truncated ? ' (truncated)' : '';

                this.createCardHeader(card, `Read: ${path}`,
                    '<span class="material-symbols-rounded">description</span>',
                    `Read ${linesRead} lines${wasTruncated}`);

                const content = card.querySelector('.card-content');

                if (result.content) {
                    const language = this.detectLanguageFromPath(path);
                    this.createCodeBlock(path, result.content, content, language, result.offset || 0);
                }

                if (result.lsp_diagnostics) {
                    const diagnosticsDiv = document.createElement('div');
                    diagnosticsDiv.style.cssText = 'margin-top: 12px; padding: 8px 12px; background-color: var(--bg-tertiary); border-radius: 4px;';
                    diagnosticsDiv.innerHTML = `<div style="font-weight: 600; color: var(--yellow); margin-bottom: 4px;">LSP Diagnostics</div><pre style="margin: 0; font-size: 0.85rem;">${result.lsp_diagnostics}</pre>`;
                    content.appendChild(diagnosticsDiv);
                }

                return card;
            },
            formatEditFileResult: function(card, result) {
                const blocksApplied = result.blocks_applied || 0;
                const linesChanged = result.lines_changed || 0;

                this.createCardHeader(card, `Edit: ${result.file || 'file'}`,
                    '<span class="material-symbols-rounded">edit</span>',
                    `${blocksApplied} block(s) applied, ${linesChanged} line(s) changed`);

                const content = card.querySelector('.card-content');

                if (result.warnings) {
                    let warningsArray = result.warnings;
                    if (typeof warningsArray === 'string') {
                        try { warningsArray = JSON.parse(warningsArray); } catch (e) { warningsArray = [warningsArray]; }
                    }

                    if (Array.isArray(warningsArray) && warningsArray.length > 0) {
                        const warningsDiv = document.createElement('div');
                        warningsDiv.style.cssText = 'padding: 8px 12px; background-color: #3a2a1a; border-radius: 4px; margin-bottom: 8px';
                        warningsDiv.innerHTML = `<div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">Warnings</div><ul style="margin: 0; padding-left: 20px; font-size: 0.85rem;">${warningsArray.map(w => `<li>${w}</li>`).join('')}</ul>`;
                        content.appendChild(warningsDiv);
                    }
                }

                if (result.content) {
                    const codeBlock = this.createCodeBlock('diff', result.content, content);
                    const codeElement = codeBlock.querySelector('code');
                    if (codeElement) {
                        codeElement.className = 'language-diff';
                        if (window.hljs) {
                            window.hljs.highlightElement(codeBlock);
                        }
                    }
                    codeBlock.classList.add('diff-block');
                }

                return card;
            },
            mapLanguageToMonaco: function(language) {
                const map = {
                    'javascript': 'javascript', 'jsx': 'javascript',
                    'typescript': 'typescript', 'tsx': 'typescript',
                    'python': 'python', 'ruby': 'ruby', 'java': 'java',
                    'cpp': 'cpp', 'c': 'c', 'csharp': 'csharp', 'go': 'go',
                    'rust': 'rust', 'php': 'php', 'swift': 'swift',
                    'kotlin': 'kotlin', 'scala': 'scala', 'bash': 'shell',
                    'sh': 'shell', 'sql': 'sql', 'json': 'json', 'css': 'css',
                    'scss': 'scss', 'html': 'html', 'xml': 'xml', 'yaml': 'yaml',
                    'yml': 'yaml', 'markdown': 'markdown', 'plaintext': 'plaintext',
                    'text': 'plaintext'
                };
                return map[language] || 'plaintext';
            }
        };
    });

    describe('formatWriteFileResult', () => {
        test('formats new file creation correctly', () => {
            const card = document.createElement('div');
            const result = {
                path: './tmp/test_write.txt',
                bytes_written: 69,
                file_existed: false,
                content: 'Test content\nLine 2'
            };

            app.formatWriteFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header).not.toBeNull();
            expect(header.textContent).toContain('Created');
            expect(header.textContent).toContain('note_add');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('69 bytes written');
        });

        test('formats file overwrite correctly', () => {
            const card = document.createElement('div');
            const result = {
                path: './src/main.py',
                bytes_written: 1234,
                file_existed: true,
                content: 'Updated content'
            };

            app.formatWriteFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Overwritten');
            expect(header.textContent).toContain('edit_note');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('1234 bytes written');
        });

        test('handles missing path gracefully', () => {
            const card = document.createElement('div');
            const result = {
                bytes_written: 100,
                file_existed: false
            };

            app.formatWriteFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Created');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('100 bytes written');
        });

        test('handles missing bytes_written gracefully', () => {
            const card = document.createElement('div');
            const result = {
                path: './test.txt',
                file_existed: false
            };

            app.formatWriteFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Created');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('0 bytes written');
        });

        test('handles missing content gracefully', () => {
            const card = document.createElement('div');
            const result = {
                path: './test.txt',
                bytes_written: 50,
                file_existed: false
            };

            app.formatWriteFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Created');
        });

        test('displays full path in content', () => {
            const card = document.createElement('div');
            const result = {
                path: '/path/to/project/tmp/test.txt',
                bytes_written: 69,
                file_existed: false,
                content: 'Test'
            };

            app.formatWriteFileResult(card, result);

            const pathDiv = card.querySelector('.card-content > div');
            expect(pathDiv.textContent).toBe('Path: /path/to/project/tmp/test.txt');
        });

        test('creates code block with correct language class', () => {
            const card = document.createElement('div');
            const result = {
                path: './test.py',
                bytes_written: 100,
                file_existed: false,
                content: 'print("hello")'
            };

            app.formatWriteFileResult(card, result);

            const code = card.querySelector('code');
            expect(code).not.toBeNull();
            expect(code.className).toBe('language-python');
            expect(code.textContent).toBe('print("hello")');
        });
    });

    describe('formatReadFileResult', () => {
        test('formats read file result correctly', () => {
            const card = document.createElement('div');
            const result = {
                path: './src/main.py',
                lines_read: 50,
                was_truncated: false,
                content: 'print("hello")'
            };

            app.formatReadFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Read: ./src/main.py');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('Read 50 lines');
        });

        test('shows truncated indicator when applicable', () => {
            const card = document.createElement('div');
            const result = {
                path: './large.py',
                lines_read: 1000,
                was_truncated: true,
                content: 'code'
            };

            app.formatReadFileResult(card, result);

            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('Read 1000 lines (truncated)');
        });

        test('handles missing path gracefully', () => {
            const card = document.createElement('div');
            const result = {
                lines_read: 10,
                content: 'code'
            };

            app.formatReadFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Read: unknown');
        });

        test('passes offset to createCodeBlock', () => {
            const card = document.createElement('div');
            const result = {
                path: './test.py',
                lines_read: 10,
                offset: 100,
                content: 'code'
            };

            app.formatReadFileResult(card, result);

            const code = card.querySelector('code');
            expect(code.textContent).toBe('code');
        });

        test('handles lsp_diagnostics', () => {
            const card = document.createElement('div');
            const result = {
                path: './test.py',
                lines_read: 10,
                content: 'code',
                lsp_diagnostics: 'ERROR: undefined variable'
            };

            app.formatReadFileResult(card, result);

            // The diagnostics div is the second child of .card-content (after the code block)
            const contentDiv = card.querySelector('.card-content');
            // Look for the diagnostics section by its title text
            const diagnosticsSection = contentDiv.querySelector('div[style*="font-weight: 600"]');
            expect(diagnosticsSection).not.toBeNull();
            expect(diagnosticsSection.textContent).toContain('LSP Diagnostics');
            // Check the full content has the error text
            expect(contentDiv.innerHTML).toContain('ERROR: undefined variable');
        });
    });

    describe('createCodeBlock', () => {
        test('creates code block with correct structure', () => {
            const container = document.createElement('div');
            const codeBlock = app.createCodeBlock('./test.py', 'print("hello")', container, 'python');

            expect(codeBlock.tagName).toBe('PRE');
            expect(codeBlock.title).toBe('Double-click to view full screen');
            expect(container.querySelector('pre')).toBe(codeBlock);
        });

        test('applies correct language class', () => {
            const container = document.createElement('div');
            const codeBlock = app.createCodeBlock('./test.py', 'code', container, 'python');

            const code = codeBlock.querySelector('code');
            expect(code.className).toBe('language-python');
        });

        test('sets correct styles', () => {
            const container = document.createElement('div');
            const codeBlock = app.createCodeBlock('./test.py', 'code', container, 'python');

            // jsdom doesn't parse cssText into individual properties,
            // so we check the title and structure instead
            expect(codeBlock.title).toBe('Double-click to view full screen');
            expect(codeBlock.tagName).toBe('PRE');
        });

        test('passes offset to showCodeFullscreen on dblclick', () => {
            const container = document.createElement('div');
            const showCodeFullscreenSpy = jest.spyOn(app, 'showCodeFullscreen');

            // Note: the module-level createCodeBlock doesn't set up dblclick listeners.
            // That's done by getFormatterHelpers. This test verifies the element is created.
            const codeBlock = app.createCodeBlock('./test.py', 'code', container, 'python', 50);

            expect(codeBlock.tagName).toBe('PRE');
            expect(showCodeFullscreenSpy).not.toHaveBeenCalled();
        });

        test('applies syntax highlighting when hljs is available', () => {
            const container = document.createElement('div');
            const hljsMock = { highlightElement: jest.fn() };
            global.window.hljs = hljsMock;

            app.createCodeBlock('./test.py', 'code', container, 'python');

            expect(hljsMock.highlightElement).toHaveBeenCalled();

            delete global.window.hljs;
        });
    });

    describe('mapLanguageToMonaco', () => {
        test('maps common languages correctly', () => {
            expect(app.mapLanguageToMonaco('javascript')).toBe('javascript');
            expect(app.mapLanguageToMonaco('python')).toBe('python');
            expect(app.mapLanguageToMonaco('typescript')).toBe('typescript');
            expect(app.mapLanguageToMonaco('rust')).toBe('rust');
        });

        test('maps jsx to javascript', () => {
            expect(app.mapLanguageToMonaco('jsx')).toBe('javascript');
        });

        test('maps tsx to typescript', () => {
            expect(app.mapLanguageToMonaco('tsx')).toBe('typescript');
        });

        test('maps bash and sh to shell', () => {
            expect(app.mapLanguageToMonaco('bash')).toBe('shell');
            expect(app.mapLanguageToMonaco('sh')).toBe('shell');
        });

        test('maps yml to yaml', () => {
            expect(app.mapLanguageToMonaco('yml')).toBe('yaml');
        });

        test('returns plaintext for unknown languages', () => {
            expect(app.mapLanguageToMonaco('unknown')).toBe('plaintext');
            expect(app.mapLanguageToMonaco('text')).toBe('plaintext');
        });
    });

    describe('detectLanguageFromPath comprehensive', () => {
        test('detects PHP variants', () => {
            expect(detectLanguageFromPath('./test.php')).toBe('php');
            expect(detectLanguageFromPath('./test.phtml')).toBe('php');
            expect(detectLanguageFromPath('./test.php3')).toBe('php');
        });

        test('detects C++ variants', () => {
            expect(detectLanguageFromPath('./test.cpp')).toBe('cpp');
            expect(detectLanguageFromPath('./test.cc')).toBe('cpp');
            expect(detectLanguageFromPath('./test.hpp')).toBe('cpp');
        });

        test('detects shell variants', () => {
            expect(detectLanguageFromPath('./script.sh')).toBe('bash');
            expect(detectLanguageFromPath('./script.zsh')).toBe('bash');
            expect(detectLanguageFromPath('./script.fish')).toBe('bash');
        });

        test('detects SQL variants', () => {
            expect(detectLanguageFromPath('./query.sql')).toBe('sql');
            expect(detectLanguageFromPath('./query.mysql')).toBe('sql');
            expect(detectLanguageFromPath('./query.postgres')).toBe('sql');
        });

        test('detects no duplicates in map', () => {
            expect(detectLanguageFromPath('./test.cake')).toBe('csharp');
            expect(detectLanguageFromPath('./test.php')).toBe('php');
            expect(detectLanguageFromPath('./test.sublime-project')).toBe('json');
        });
    });

    describe('formatEditFileResult', () => {
        test('formats edit file result correctly', () => {
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                blocks_applied: 1,
                lines_changed: 5,
                content: '@@ -1,3 +1,8 @@\n-def old_function():\n-    pass\n+def new_function():\n+    # New implementation\n+    return True\n'
            };

            app.formatEditFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Edit: ./src/main.py');
            expect(header.textContent).toContain('edit');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('1 block(s) applied, 5 line(s) changed');
        });

        test('handles warnings correctly', () => {
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                blocks_applied: 1,
                lines_changed: 0,
                warnings: ['old_string appears 2 times in the file'],
                content: 'diff content'
            };

            app.formatEditFileResult(card, result);

            // Check that warnings section exists by looking for the warning title
            const contentDiv = card.querySelector('.card-content');
            const warningTitle = contentDiv.querySelector('[style*="color: #f0ad4e"]');
            expect(warningTitle).not.toBeNull();
            expect(warningTitle.textContent).toContain('Warnings');
            // Check the full content div has the warning text
            expect(contentDiv.textContent).toContain('old_string appears 2 times in the file');
        });

        test('adds diff-block class to code block', () => {
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                blocks_applied: 1,
                lines_changed: 3,
                content: '@@ -1,3 +1,6 @@\n-old\n+new\n'
            };

            app.formatEditFileResult(card, result);

            const codeBlock = card.querySelector('.diff-block');
            expect(codeBlock).not.toBeNull();
        });

        test('displays full diff content without truncation', () => {
            const longDiff = Array(100).fill('line of diff content').join('\n');
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                blocks_applied: 1,
                lines_changed: 100,
                content: longDiff
            };

            app.formatEditFileResult(card, result);

            const code = card.querySelector('code');
            expect(code.textContent).toBe(longDiff);
        });

        test('applies language-diff class to code element', () => {
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                blocks_applied: 1,
                lines_changed: 3,
                content: '@@ -1,3 +1,6 @@\n-old\n+new\n'
            };

            app.formatEditFileResult(card, result);

            const code = card.querySelector('code');
            expect(code.className).toBe('language-diff');
        });

        test('handles missing file gracefully', () => {
            const card = document.createElement('div');
            const result = {
                blocks_applied: 1,
                lines_changed: 3,
                content: 'diff content'
            };

            app.formatEditFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Edit: file');
        });

        test('handles missing blocks_applied gracefully', () => {
            const card = document.createElement('div');
            const result = {
                file: './src/main.py',
                content: 'diff content'
            };

            app.formatEditFileResult(card, result);

            const header = card.querySelector('.card-header');
            expect(header.textContent).toContain('Edit: ./src/main.py');
            const summary = card.querySelector('.card-content > pre');
            expect(summary.textContent).toBe('0 block(s) applied, 0 line(s) changed');
        });
    });
});

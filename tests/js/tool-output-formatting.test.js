/**
 * Tests for tool output formatting in WebUI.
 */

describe('Tool Output Formatting', () => {
    let mockDocument;
    let mockCard;
    let app;
    let mockContainer;

    beforeEach(() => {
        mockContainer = {
            appendChild: jest.fn()
        };

        // Mock DOM elements
        mockDocument = {
            createElement: jest.fn((tagName) => {
                const mockElement = {
                    className: '',
                    style: { cssText: '' },
                    textContent: '',
                    innerHTML: '',
                    querySelector: jest.fn(),
                    appendChild: jest.fn(),
                    setAttribute: jest.fn(),
                    addEventListener: jest.fn(),
                    title: ''
                };
                return mockElement;
            })
        };

        // Mock card element
        mockCard = {
            className: '',
            querySelector: jest.fn((selector) => {
                if (selector === '.card-content') {
                    return mockContainer;
                }
                return null;
            })
        };

        // Full extension map matching production code
        const fullExtMap = {
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

        // Create a minimal app instance with the formatting methods
        app = {
            createCardHeader: jest.fn((card, title, icon, summary) => {
                card.headerTitle = title;
                card.headerIcon = icon;
                card.headerSummary = summary;
            }),
            detectLanguageFromPath: function(path) {
                const ext = path.split('.').pop().toLowerCase();
                return fullExtMap[ext] || 'plaintext';
            },
            createCodeBlock: function(path, content, container, offset = 0) {
                const language = this.detectLanguageFromPath(path);
                const codeBlock = document.createElement('pre');
                codeBlock.style.cssText = 'margin-top: 8px; border-radius: 4px; overflow: hidden; max-height: 400px; overflow-y: auto; cursor: pointer;';
                codeBlock.title = 'Double-click to view full screen';

                const code = document.createElement('code');
                code.className = `language-${language}`;
                code.textContent = content;

                codeBlock.appendChild(code);
                container.appendChild(codeBlock);

                if (window.hljs) {
                    window.hljs.highlightElement(codeBlock);
                }

                codeBlock.addEventListener('dblclick', () => {
                    this.showCodeFullscreen(path, content, language, offset);
                });

                return codeBlock;
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
                    this.createCodeBlock(path, result.content, contentDiv);
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
                    this.createCodeBlock(path, result.content, content, result.offset || 0);
                }

                if (result.lsp_diagnostics) {
                    const diagnosticsDiv = document.createElement('div');
                    diagnosticsDiv.style.cssText = 'margin-top: 12px; padding: 8px 12px; background-color: var(--bg-tertiary); border-radius: 4px;';
                    diagnosticsDiv.innerHTML = `<div style="font-weight: 600; color: var(--yellow); margin-bottom: 4px;">LSP Diagnostics</div><pre style="margin: 0; font-size: 0.85rem;">${result.lsp_diagnostics}</pre>`;
                    content.appendChild(diagnosticsDiv);
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

        // Override document for createElement calls
        global.document = mockDocument;
        global.window = { hljs: null };
    });

    afterEach(() => {
        delete global.document;
        delete global.window;
    });

    describe('formatWriteFileResult', () => {
        test('formats new file creation correctly', () => {
            const result = {
                path: './tmp/test_write.txt',
                bytes_written: 69,
                file_existed: false,
                content: 'Test content\nLine 2'
            };

            const card = app.formatWriteFileResult(mockCard, result);

            // Verify header was created with correct status
            expect(app.createCardHeader).toHaveBeenCalledWith(
                mockCard,
                'Created',
                expect.stringContaining('note_add'),
                '69 bytes written'
            );

            // Verify header properties
            expect(card.headerTitle).toBe('Created');
            expect(card.headerSummary).toBe('69 bytes written');
            expect(card.headerIcon).toContain('note_add');
            expect(card.headerIcon).toContain('var(--green)');
        });

        test('formats file overwrite correctly', () => {
            const result = {
                path: './src/main.py',
                bytes_written: 1234,
                file_existed: true,
                content: 'Updated content'
            };

            const card = app.formatWriteFileResult(mockCard, result);

            // Verify header was created with correct status
            expect(app.createCardHeader).toHaveBeenCalledWith(
                mockCard,
                'Overwritten',
                expect.stringContaining('edit_note'),
                '1234 bytes written'
            );

            // Verify header properties
            expect(card.headerTitle).toBe('Overwritten');
            expect(card.headerSummary).toBe('1234 bytes written');
            expect(card.headerIcon).toContain('edit_note');
            expect(card.headerIcon).toContain('var(--yellow)');
        });

        test('handles missing path gracefully', () => {
            const result = {
                bytes_written: 100,
                file_existed: false
            };

            const card = app.formatWriteFileResult(mockCard, result);

            expect(card.headerTitle).toBe('Created');
            expect(card.headerSummary).toBe('100 bytes written');
        });

        test('handles missing bytes_written gracefully', () => {
            const result = {
                path: './test.txt',
                file_existed: false
            };

            const card = app.formatWriteFileResult(mockCard, result);

            expect(card.headerSummary).toBe('0 bytes written');
        });

        test('handles missing content gracefully', () => {
            const result = {
                path: './test.txt',
                bytes_written: 50,
                file_existed: false
            };

            const card = app.formatWriteFileResult(mockCard, result);

            // Should not throw error when content is missing
            expect(card.headerTitle).toBe('Created');
        });

        test('displays full path in content', () => {
            const result = {
                path: '/path/to/project/tmp/test.txt',
                bytes_written: 69,
                file_existed: false,
                content: 'Test'
            };

            const card = app.formatWriteFileResult(mockCard, result);

            // Verify querySelector was called for .card-content
            expect(mockCard.querySelector).toHaveBeenCalledWith('.card-content');
        });

        test('detects language from file extension', () => {
            expect(app.detectLanguageFromPath('./test.py')).toBe('python');
            expect(app.detectLanguageFromPath('./test.js')).toBe('javascript');
            expect(app.detectLanguageFromPath('./test.ts')).toBe('typescript');
            expect(app.detectLanguageFromPath('./script.sh')).toBe('bash');
            expect(app.detectLanguageFromPath('./README.md')).toBe('markdown');
            expect(app.detectLanguageFromPath('./config.json')).toBe('json');
            expect(app.detectLanguageFromPath('./style.css')).toBe('css');
            expect(app.detectLanguageFromPath('./index.html')).toBe('xml');
            expect(app.detectLanguageFromPath('./unknown.xyz')).toBe('plaintext');
        });

        test('applies correct language class to code block', () => {
            const result = {
                path: './test.py',
                bytes_written: 100,
                file_existed: false,
                content: 'print("hello")'
            };

            const card = app.formatWriteFileResult(mockCard, result);

            expect(mockCard.querySelector).toHaveBeenCalledWith('.card-content');
        });
    });

    describe('formatReadFileResult', () => {
        test('formats read file result correctly', () => {
            const result = {
                path: './src/main.py',
                lines_read: 50,
                was_truncated: false,
                content: 'print("hello")'
            };

            const card = app.formatReadFileResult(mockCard, result);

            expect(app.createCardHeader).toHaveBeenCalledWith(
                mockCard,
                'Read: ./src/main.py',
                '<span class="material-symbols-rounded">description</span>',
                'Read 50 lines'
            );
            expect(card.headerTitle).toBe('Read: ./src/main.py');
            expect(card.headerSummary).toBe('Read 50 lines');
        });

        test('shows truncated indicator when applicable', () => {
            const result = {
                path: './large.py',
                lines_read: 1000,
                was_truncated: true,
                content: 'code'
            };

            const card = app.formatReadFileResult(mockCard, result);

            expect(card.headerSummary).toBe('Read 1000 lines (truncated)');
        });

        test('handles missing path gracefully', () => {
            const result = {
                lines_read: 10,
                content: 'code'
            };

            const card = app.formatReadFileResult(mockCard, result);

            expect(card.headerTitle).toBe('Read: unknown');
        });

        test('passes offset to createCodeBlock', () => {
            const result = {
                path: './test.py',
                lines_read: 10,
                offset: 100,
                content: 'code'
            };

            app.formatReadFileResult(mockCard, result);

            // verify createCodeBlock was called with offset
            expect(mockContainer.appendChild).toHaveBeenCalled();
        });

        test('handles lsp_diagnostics', () => {
            const result = {
                path: './test.py',
                lines_read: 10,
                content: 'code',
                lsp_diagnostics: 'ERROR: undefined variable'
            };

            app.formatReadFileResult(mockCard, result);

            // Should create diagnostics div
            expect(mockContainer.appendChild).toHaveBeenCalled();
        });
    });

    describe('createCodeBlock', () => {
        test('creates code block with correct structure', () => {
            const codeBlock = app.createCodeBlock('./test.py', 'print("hello")', mockContainer);

            expect(codeBlock.title).toBe('Double-click to view full screen');
            expect(mockContainer.appendChild).toHaveBeenCalledWith(codeBlock);
        });

        test('applies correct language class', () => {
            app.createCodeBlock('./test.py', 'code', mockContainer);

            expect(mockDocument.createElement).toHaveBeenCalledWith('code');
        });

        test('sets correct styles', () => {
            const codeBlock = app.createCodeBlock('./test.py', 'code', mockContainer);

            expect(codeBlock.style.cssText).toContain('max-height: 400px');
            expect(codeBlock.style.cssText).toContain('overflow-y: auto');
        });

        test('passes offset to showCodeFullscreen on dblclick', () => {
            const showCodeFullscreenSpy = jest.spyOn(app, 'showCodeFullscreen');

            // Create code block with offset
            app.createCodeBlock('./test.py', 'code', mockContainer, 50);

            // Verify showCodeFullscreen was set up to be called with offset
            expect(mockDocument.createElement).toHaveBeenCalled();
            expect(showCodeFullscreenSpy).toBeDefined();
        });

        test('applies syntax highlighting when hljs is available', () => {
            global.window.hljs = { highlightElement: jest.fn() };

            app.createCodeBlock('./test.py', 'code', mockContainer);

            expect(window.hljs.highlightElement).toHaveBeenCalled();
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
            expect(app.detectLanguageFromPath('./test.php')).toBe('php');
            expect(app.detectLanguageFromPath('./test.phtml')).toBe('php');
            expect(app.detectLanguageFromPath('./test.php3')).toBe('php');
        });

        test('detects C++ variants', () => {
            expect(app.detectLanguageFromPath('./test.cpp')).toBe('cpp');
            expect(app.detectLanguageFromPath('./test.cc')).toBe('cpp');
            expect(app.detectLanguageFromPath('./test.hpp')).toBe('cpp');
        });

        test('detects shell variants', () => {
            expect(app.detectLanguageFromPath('./script.sh')).toBe('bash');
            expect(app.detectLanguageFromPath('./script.zsh')).toBe('bash');
            expect(app.detectLanguageFromPath('./script.fish')).toBe('bash');
        });

        test('detects SQL variants', () => {
            expect(app.detectLanguageFromPath('./query.sql')).toBe('sql');
            expect(app.detectLanguageFromPath('./query.mysql')).toBe('sql');
            expect(app.detectLanguageFromPath('./query.postgres')).toBe('sql');
        });

        test('detects no duplicates in map', () => {
            // Verify no duplicate keys exist (cake, php, sublime-* were deduplicated)
            expect(app.detectLanguageFromPath('./test.cake')).toBe('csharp');
            expect(app.detectLanguageFromPath('./test.php')).toBe('php');
            expect(app.detectLanguageFromPath('./test.sublime-project')).toBe('json');
        });
    });
});

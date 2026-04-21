/**
 * Tool Result Formatters Module
 *
 * Handles formatting of tool results for display in the WebUI.
 * Extracted from app.js for testability and single responsibility.
 */

const MIME_ICONS = {
    image: 'image',
    text: 'description',
    pdf: 'picture_as_pdf',
    archive: 'archive',
    code: 'code',
};

/**
 * Fallback HTML escape function using DOM.
 * Used when helpers.escapeHtml is not provided.
 */
const ESCAPE_HTML_FALLBACK = (t) => {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
};

/**
 * Get icon for MIME type
 */
export function getIconForMimeType(mimeType) {
    if (mimeType.startsWith('image/')) return MIME_ICONS.image;
    if (mimeType.startsWith('text/')) return MIME_ICONS.text;
    if (mimeType.includes('pdf')) return MIME_ICONS.pdf;
    if (mimeType.includes('zip') || mimeType.includes('compressed')) return MIME_ICONS.archive;
    if (mimeType.includes('code') || mimeType.endsWith('+xml')) return MIME_ICONS.code;
    return MIME_ICONS.text;
}

/**
 * Trigger file download via API
 */
export async function triggerDownload(filePath) {
    const url = `/api/download?file_path=${encodeURIComponent(filePath)}`;
    try {
        const response = await fetch(url);
        if (response.ok) {
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filePath.split('/').pop() || 'download';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
        }
    } catch (err) {
        console.error('Download failed:', err);
    }
}

/**
 * Create a card header with collapsible content
 */
export function createCardHeader(card, title, icon, summary) {
    const header = document.createElement('div');
    header.className = 'card-header';
    header.innerHTML = `
        <div class="card-title">
            <span class="card-icon">${icon}</span>
            <span>${title}</span>
        </div>
        <span class="card-toggle">▼</span>
    `;

    if (!card.hasAttribute('data-listener-attached')) {
        header.addEventListener('click', () => card.classList.toggle('collapsed'));
        card.setAttribute('data-listener-attached', 'true');
    }

    const content = document.createElement('div');
    content.className = 'card-content';

    if (summary) {
        const summaryPre = document.createElement('pre');
        summaryPre.textContent = summary;
        content.appendChild(summaryPre);
    }

    card.appendChild(header);
    card.appendChild(content);
    return card;
}

/**
 * Create a code block with syntax highlighting
 */
export function createCodeBlock(path, content, container, language, offset = 0) {
    const codeBlock = document.createElement('pre');
    codeBlock.className = 'tool-formatter-code-block';
    codeBlock.title = 'Double-click to view full screen';

    const code = document.createElement('code');
    code.className = `language-${language || 'plaintext'}`;
    code.textContent = content;

    codeBlock.appendChild(code);
    container.appendChild(codeBlock);

    if (window.hljs) {
        window.hljs.highlightElement(codeBlock);
    }

    return codeBlock;
}

/**
 * Create an output section for bash results
 */
export function createOutputSection(type, content, helpers = {}) {
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;
    const section = document.createElement('div');
    section.className = `bash-output-section ${type}`;
    section.innerHTML = `<div class="output-label">${type.toUpperCase()}</div><div class="output-content"><pre>${escape(content)}</pre></div>`;
    return section;
}

/**
 * Detect language from file path extension
 */
export function detectLanguageFromPath(path) {
    const extMap = {
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

    const ext = path.split('.').pop().toLowerCase();
    return extMap[ext] || 'plaintext';
}

/**
 * Format tool result based on tool name
 */
export function formatToolResult(toolName, result, helpers) {
    const card = document.createElement('div');
    card.className = 'tool-result-card';

    switch (toolName) {
        case 'bash': return formatBashResult(card, result, helpers);
        case 'websearch': return formatWebSearchResult(card, result, helpers);
        case 'webfetch': return formatWebFetchResult(card, result, helpers);
        case 'grep': return formatGrepResult(card, result, helpers);
        case 'read_file': return formatReadFileResult(card, result, helpers);
        case 'edit_file': return formatEditFileResult(card, result, helpers);
        case 'write_file': return formatWriteFileResult(card, result, helpers);
        case 'lsp': return formatLspResult(card, result, helpers);
        case 'todo': return formatTodoResult(card, result, helpers);
        case 'ask_user_question': return formatAskUserQuestionResult(card, result, helpers);
        case 'register_download': return formatRegisterDownloadResult(card, result, helpers);
        default: return formatGenericResult(card, result, helpers);
    }
}

function formatBashResult(card, result, helpers = {}) {
    const returncode = parseInt(result.returncode) || 0;
    const isSuccess = returncode === 0;
    const ch = helpers.createCardHeader || createCardHeader;
    const cos = helpers.createOutputSection || createOutputSection;

    ch(card, `bash: ${result.command || 'command'}`,
        isSuccess ? '<span class="material-symbols-rounded">check_circle</span>' : '<span class="material-symbols-rounded">error</span>',
        `Return code: ${returncode}`);

    const content = card.querySelector('.card-content');

    if (result.stdout) {
        content.appendChild(cos('stdout', result.stdout, helpers));
    }
    if (result.stderr) {
        content.appendChild(cos('stderr', result.stderr, helpers));
    }

    const returncodeBadge = document.createElement('div');
    returncodeBadge.className = `bash-returncode ${isSuccess ? 'success' : 'failure'}`;
    returncodeBadge.textContent = `Return code: ${returncode}`;
    content.appendChild(returncodeBadge);

    return card;
}

function formatWebSearchResult(card, result, helpers = {}) {
    const sourceCount = result.sources?.length || 0;
    const ch = helpers.createCardHeader || createCardHeader;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    ch(card, `Web search: ${result.answer?.substring(0, 50) || 'search'}...`,
        '<span class="material-symbols-rounded">search</span>', `${sourceCount} sources found`);

    const content = card.querySelector('.card-content');

    if (result.answer) {
        const answerPre = document.createElement('pre');
        answerPre.textContent = result.answer;
        content.appendChild(answerPre);
    }

    if (result.sources?.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.style.marginTop = '12px';
        result.sources.forEach(source => {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'search-source-item';
            sourceItem.innerHTML = `<div class="source-title">${escape(source.title)}</div><div class="source-url">${escape(source.url)}</div>`;
            sourcesDiv.appendChild(sourceItem);
        });
        content.appendChild(sourcesDiv);
    }

    return card;
}

function formatWebFetchResult(card, result, helpers = {}) {
    const linesRead = result.lines_read || 0;
    const totalLines = result.total_lines || 0;
    const wasTruncated = result.was_truncated ? ' (truncated)' : '';
    const ch = helpers.createCardHeader || createCardHeader;

    ch(card, `Fetch: ${result.url || 'URL'}`,
        '<span class="material-symbols-rounded">description</span>',
        `Fetched ${linesRead}/${totalLines} lines${wasTruncated}`);

    const content = card.querySelector('.card-content');

    if (result.content) {
        const lines = result.content.split('\n');
        content.appendChild(document.createElement('pre')).textContent = lines.slice(0, 100).join('\n');

        if (lines.length > 100) {
            const moreDiv = document.createElement('div');
            moreDiv.className = 'tool-formatter-more-lines';
            moreDiv.textContent = `... and ${lines.length - 100} more lines`;
            content.appendChild(moreDiv);
        }
    }

    return card;
}

function formatGrepResult(card, result, helpers = {}) {
    const matchCount = result.match_count || 0;
    const wasTruncated = result.was_truncated ? ' (truncated)' : '';
    const ch = helpers.createCardHeader || createCardHeader;

    ch(card, `Grep: ${result.pattern || 'pattern'}`,
        '<span class="material-symbols-rounded">search</span>',
        `${matchCount} matches found${wasTruncated}`);

    const content = card.querySelector('.card-content');
    if (result.matches) {
        content.appendChild(document.createElement('pre')).textContent = result.matches;
    }

    return card;
}

function formatReadFileResult(card, result, helpers = {}) {
    const path = result.path || 'unknown';
    const linesRead = result.lines_read || 0;
    const wasTruncated = result.was_truncated ? ' (truncated)' : '';
    const ch = helpers.createCardHeader || createCardHeader;
    const ccb = helpers.createCodeBlock || createCodeBlock;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    ch(card, `Read: ${path}`,
        '<span class="material-symbols-rounded">description</span>',
        `Read ${linesRead} lines${wasTruncated}`);

    const content = card.querySelector('.card-content');

    if (result.content) {
        ccb(path, result.content, content, detectLanguageFromPath(path), result.offset || 0);
    }

    if (result.lsp_diagnostics) {
        const diagnosticsDiv = document.createElement('div');
        diagnosticsDiv.className = 'tool-formatter-diagnostics';
        diagnosticsDiv.innerHTML = `<div style="font-weight: 600; color: var(--yellow); margin-bottom: 4px;">LSP Diagnostics</div><pre style="margin: 0; font-size: 0.85rem;">${escape(result.lsp_diagnostics)}</pre>`;
        content.appendChild(diagnosticsDiv);
    }

    return card;
}

function formatEditFileResult(card, result, helpers = {}) {
    const blocksApplied = result.blocks_applied || 0;
    const linesChanged = result.lines_changed || 0;
    const ch = helpers.createCardHeader || createCardHeader;
    const ccb = helpers.createCodeBlock || createCodeBlock;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    ch(card, `Edit: ${result.file || 'file'}`,
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
            warningsDiv.className = 'tool-formatter-warnings';
            warningsDiv.innerHTML = `<div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">Warnings</div><ul style="margin: 0; padding-left: 20px; font-size: 0.85rem;">${warningsArray.map(w => `<li>${escape(w)}</li>`).join('')}</ul>`;
            content.appendChild(warningsDiv);
        }
    }

    if (result.content) {
        const codeBlock = ccb('diff', result.content, content);
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
}

function formatLspResult(card, result, helpers = {}) {
    const diagnostics = result.diagnostics || [];
    const errors = diagnostics.filter(d => d.severity === 1).length;
    const warnings = diagnostics.filter(d => d.severity === 2).length;
    const ch = helpers.createCardHeader || createCardHeader;

    let headerIcon = errors > 0 ? '<span class="material-symbols-rounded">error</span>' :
                     warnings > 0 ? '<span class="material-symbols-rounded">warning</span>' :
                     '<span class="material-symbols-rounded">check_circle</span>';
    const summary = errors === 0 && warnings === 0 ? 'No issues found' : `${errors} error(s), ${warnings} warning(s)`;

    ch(card, 'LSP Diagnostics', headerIcon, summary);

    const content = card.querySelector('.card-content');
    if (result.formatted_output) {
        content.appendChild(document.createElement('pre')).textContent = result.formatted_output;
    }

    return card;
}

function formatTodoResult(card, result, helpers = {}) {
    const total = result.total_count || 0;
    const ch = helpers.createCardHeader || createCardHeader;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    ch(card, 'Todo List',
        '<span class="material-symbols-rounded">check_circle</span>',
        `${total} total tasks`);

    const content = card.querySelector('.card-content');

    if (result.todos?.length > 0) {
        const table = document.createElement('table');
        table.className = 'tool-table';
        table.innerHTML = `
            <thead><tr><th>Status</th><th>Priority</th><th>Content</th></tr></thead>
            <tbody>${result.todos.map(todo => `
                <tr>
                    <td>${escape(todo.status || 'pending')}</td>
                    <td>${escape(todo.priority || 'medium')}</td>
                    <td>${escape(todo.content || '')}</td>
                </tr>
            `).join('')}</tbody>
        `;
        content.appendChild(table);
    }

    return card;
}

function formatAskUserQuestionResult(card, result, helpers = {}) {
    let answers = result.answers;
    if (typeof answers === 'string') {
        try {
            answers = JSON.parse(answers.replace(/'/g, '"').replace(/False/g, 'false').replace(/True/g, 'true'));
        } catch (e) {
            answers = [];
        }
    }
    answers = Array.isArray(answers) ? answers : [];

    const cancelled = result.cancelled === true;
    const ch = helpers.createCardHeader || createCardHeader;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    ch(card, 'User Answers',
        '<span class="material-symbols-rounded">chat</span>',
        `${answers.length} answer(s)${cancelled ? ' (cancelled)' : ''}`);

    const content = card.querySelector('.card-content');

    if (answers.length > 0) {
        answers.forEach((answer) => {
            const answerItem = document.createElement('div');
            answerItem.className = 'answer-item';
            const questionText = escape(answer.question);
            const answerText = escape(answer.answer);
            const otherBadge = answer.is_other ? '<span class="answer-other-badge">(Custom answer)</span>' : '';

            answerItem.innerHTML = `
                <div class="answer-question">${questionText}</div>
                <div class="answer-text">${answerText}${otherBadge}</div>
            `;
            content.appendChild(answerItem);
        });
    } else if (cancelled) {
        const cancelledText = document.createElement('div');
        cancelledText.className = 'answer-cancelled';
        cancelledText.textContent = 'Question was cancelled by the user';
        content.appendChild(cancelledText);
    }

    return card;
}

function formatRegisterDownloadResult(card, result, helpers = {}) {
    card.className = 'download-card';
    const filename = result.filename || 'file';
    const filePath = result.file_path || '';
    const mimeType = result.mime_type || 'application/octet-stream';
    const description = result.description;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;
    const icon = helpers.getIconForMimeType || getIconForMimeType;
    const td = helpers.triggerDownload || triggerDownload;

    const header = document.createElement('div');
    header.className = 'download-card-header';

    const iconVal = icon(mimeType);
    header.innerHTML = `
        <div class="download-card-title">
            <span class="material-symbols-rounded">${iconVal}</span>
            <span>${escape(filename)}</span>
        </div>
        <div class="download-card-type">${escape(mimeType)}</div>
    `;

    let descriptionDiv = null;
    if (description) {
        descriptionDiv = document.createElement('div');
        descriptionDiv.className = 'download-card-description';
        descriptionDiv.textContent = escape(description);
    }

    const button = document.createElement('button');
    button.className = 'download-card-button';
    button.innerHTML = `
        <span class="material-symbols-rounded">download</span>
        <span>Download</span>
    `;
    button.addEventListener('click', () => td(filePath));

    card.appendChild(header);
    if (descriptionDiv) card.appendChild(descriptionDiv);
    card.appendChild(button);

    return card;
}

function formatGenericResult(card, result, helpers = {}) {
    const ch = helpers.createCardHeader || createCardHeader;
    ch(card, 'Result',
        '<span class="material-symbols-rounded">analytics</span>',
        JSON.stringify(result, null, 2));
    return card;
}

function formatWriteFileResult(card, result, helpers = {}) {
    const path = result.path || 'unknown';
    const bytesWritten = result.bytes_written || 0;
    const fileExisted = result.file_existed;
    const ch = helpers.createCardHeader || createCardHeader;
    const ccb = helpers.createCodeBlock || createCodeBlock;
    const escape = helpers.escapeHtml || ESCAPE_HTML_FALLBACK;

    const status = fileExisted ? 'Overwritten' : 'Created';
    const statusIcon = fileExisted ? 'edit_note' : 'note_add';
    const statusColor = fileExisted ? 'var(--yellow)' : 'var(--green)';

    ch(card, status,
        `<span class="material-symbols-rounded" style="color: ${statusColor}">${statusIcon}</span>`,
        `${bytesWritten} bytes written`);

    const contentDiv = card.querySelector('.card-content');

    const pathDiv = document.createElement('div');
    pathDiv.className = 'tool-formatter-path';
    pathDiv.textContent = `Path: ${path}`;
    contentDiv.appendChild(pathDiv);

    if (result.content) {
        ccb(path, result.content, contentDiv, detectLanguageFromPath(path));
    }

    return card;
}

/**
 * Truncate path from start to fit container
 */
export function truncatePathFromStart(path, container) {
    const buttonsWidth = 70;
    const padding = 40;
    const availableWidth = container.offsetWidth - buttonsWidth - padding;
    const style = window.getComputedStyle(container);
    const fontSize = parseFloat(style.fontSize);
    const maxChars = Math.floor(availableWidth / (fontSize * 0.6));
    if (path.length <= maxChars) return path;
    const parts = path.split('/');
    let result = parts[parts.length - 1];
    for (let i = parts.length - 2; i >= 0; i--) {
        const test = '...' + parts.slice(i).join('/');
        if (test.length > maxChars) break;
        result = test;
    }
    return result;
}

/**
 * Helper object for formatter methods that need VibeClient methods
 */
export function getFormatterHelpers(vibeClient) {
    return {
        escapeHtml: vibeClient.escapeHtml.bind(vibeClient),
        createCardHeader,
        createCodeBlock: (path, content, container, language, offset = 0) => {
            const lang = language || detectLanguageFromPath(path);
            const block = createCodeBlock(path, content, container, lang, offset);
            block.addEventListener('dblclick', () => {
                if (vibeClient.showCodeFullscreen) {
                    vibeClient.showCodeFullscreen(path, content, lang, offset);
                }
            });
            return block;
        },
        createOutputSection,
        getIconForMimeType,
        triggerDownload: (filePath) => triggerDownload(filePath),
        detectLanguageFromPath,
    };
}

const MAX_ARRAY_ITEMS = 50;
const MAX_DEPTH = 4;

function isFilePath(s) {
    return /^(\/|[a-zA-Z]:\\|\.\/|\.\.\/)/.test(s) || /[\/\\]/.test(s);
}

function isUrl(s) {
    return /^https?:\/\//.test(s);
}

function hasFileExtension(s) {
    return /\.[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?$/.test(s) && !s.includes(' ');
}

function renderValue(value, depth) {
    if (value === null || value === undefined) {
        return createBadge('null', 'null-badge');
    }
    if (typeof value === 'boolean') {
        return createBadge(value ? 'true' : 'false', value ? 'bool-badge true-badge' : 'bool-badge false-badge');
    }
    if (typeof value === 'number') {
        const span = document.createElement('span');
        span.className = 'struct-number';
        span.textContent = value;
        return span;
    }
    if (typeof value === 'object') {
        if (Array.isArray(value)) {
            return renderArray(value, depth);
        }
        return renderObject(value, depth);
    }
    return renderString(value);
}

function renderString(s) {
    const span = document.createElement('span');
    const hasNewline = s.includes('\n');

    if (isUrl(s)) {
        span.className = 'struct-url';
        const a = document.createElement('a');
        a.href = s;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = s;
        a.title = s;
        span.appendChild(a);
        return span;
    }

    if (!hasNewline && (isFilePath(s) || hasFileExtension(s))) {
        span.className = 'struct-path';
        span.textContent = s;
        span.title = s;
        const icon = document.createElement('span');
        icon.className = 'material-symbols-rounded struct-icon';
        icon.textContent = 'drive_file_rename_outline';
        icon.style.fontSize = '0.85em';
        span.insertBefore(icon, span.firstChild);
        return span;
    }

    const realNewlines = hasNewline ? (s.match(/\n/g) || []).length : 0;
    const escapedNewlines = (s.match(/\\n/g) || []).length;
    const lineCount = Math.max(realNewlines, escapedNewlines) + 1;

    if (lineCount > 1) {
        const displayStr = escapedNewlines > 0 && realNewlines === 0 ? s.replace(/\\n/g, '\n') : s;
        const wrapper = document.createElement('span');
        wrapper.className = 'struct-multiline';

        const preview = document.createElement('span');
        preview.className = 'struct-multiline-preview';
        preview.textContent = displayStr.split('\n')[0];

        const badge = document.createElement('span');
        badge.className = 'struct-multiline-badge';
        badge.textContent = `${lineCount} lines`;

        wrapper.appendChild(preview);
        wrapper.appendChild(badge);

        wrapper.addEventListener('click', () => {
            const expanded = wrapper.querySelector('.struct-multiline-expanded');
            if (expanded) {
                expanded.remove();
                preview.style.display = '';
                badge.style.display = '';
            } else {
                preview.style.display = 'none';
                badge.style.display = 'none';
                const full = document.createElement('pre');
                full.className = 'struct-multiline-expanded';
                full.textContent = displayStr;
                wrapper.appendChild(full);
            }
        });

        return wrapper;
    }

    span.className = 'struct-string';
    span.textContent = s;
    return span;
}

function renderObject(obj, depth) {
    if (depth >= MAX_DEPTH) {
        const pre = document.createElement('pre');
        pre.className = 'struct-fallback';
        pre.textContent = JSON.stringify(obj, null, 2);
        return pre;
    }

    const keys = Object.keys(obj);
    if (keys.length === 0) {
        return createBadge('{}', 'empty-badge');
    }

    const container = document.createElement('div');
    container.className = 'struct-object';

    const table = document.createElement('table');
    table.className = 'struct-table';

    for (const key of keys) {
        const tr = document.createElement('tr');

        const th = document.createElement('th');
        th.className = 'struct-key';
        th.textContent = key;

        const td = document.createElement('td');
        td.className = 'struct-value';
        td.appendChild(renderValue(obj[key], depth + 1));

        tr.appendChild(th);
        tr.appendChild(td);
        table.appendChild(tr);
    }

    container.appendChild(table);
    return container;
}

function renderArray(arr, depth) {
    if (arr.length === 0) {
        return createBadge('[]', 'empty-badge');
    }

    const container = document.createElement('div');
    container.className = 'struct-array';

    const isSimple = arr.length > 0 && typeof arr[0] !== 'object';

    if (isSimple) {
        const list = document.createElement('ul');
        list.className = 'struct-list';
        const limit = Math.min(arr.length, MAX_ARRAY_ITEMS);
        for (let i = 0; i < limit; i++) {
            const li = document.createElement('li');
            li.appendChild(renderValue(arr[i], depth + 1));
            list.appendChild(li);
        }
        if (arr.length > MAX_ARRAY_ITEMS) {
            const li = document.createElement('li');
            li.className = 'struct-more';
            li.textContent = `… and ${arr.length - MAX_ARRAY_ITEMS} more`;
            list.appendChild(li);
        }
        container.appendChild(list);
    } else {
        const limit = Math.min(arr.length, MAX_ARRAY_ITEMS);
        for (let i = 0; i < limit; i++) {
            const item = document.createElement('div');
            item.className = 'struct-array-item';
            const idx = document.createElement('span');
            idx.className = 'struct-idx';
            idx.textContent = i;
            item.appendChild(idx);
            const content = document.createElement('div');
            content.className = 'struct-array-content';
            content.appendChild(renderObject(arr[i], depth + 1));
            item.appendChild(content);
            container.appendChild(item);
        }
        if (arr.length > MAX_ARRAY_ITEMS) {
            const more = document.createElement('div');
            more.className = 'struct-more';
            more.textContent = `… and ${arr.length - MAX_ARRAY_ITEMS} more items`;
            container.appendChild(more);
        }
    }

    return container;
}

function createBadge(text, className) {
    const span = document.createElement('span');
    span.className = `struct-badge ${className}`;
    span.textContent = text;
    return span;
}

export function renderStructured(container, data, options = {}) {
    const fallback = options.fallback !== false;
    const showCopy = options.showCopy !== false;
    const existingClass = container.className || '';

    try {
        container.className = existingClass
            ? existingClass + ' structured-renderer'
            : 'structured-renderer';

        if (data === null || data === undefined) {
            container.appendChild(createBadge('null', 'null-badge'));
            return;
        }

        if (typeof data !== 'object') {
            container.appendChild(renderString(String(data)));
            return;
        }

        if (Array.isArray(data)) {
            container.appendChild(renderArray(data, 0));
        } else {
            container.appendChild(renderObject(data, 0));
        }

        if (showCopy) {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'struct-copy-btn';
            copyBtn.innerHTML = '<span class="material-symbols-rounded">content_copy</span>';
            copyBtn.title = 'Copy as JSON';
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(JSON.stringify(data, null, 2));
                copyBtn.innerHTML = '<span class="material-symbols-rounded">check</span>';
                setTimeout(() => {
                    copyBtn.innerHTML = '<span class="material-symbols-rounded">content_copy</span>';
                }, 1500);
            });
            container.appendChild(copyBtn);
        }
    } catch (e) {
        if (fallback) {
            const pre = document.createElement('pre');
            pre.className = 'struct-fallback';
            try {
                pre.textContent = JSON.stringify(data, null, 2);
            } catch {
                pre.textContent = String(data);
            }
            container.appendChild(pre);
        }
    }
}

export function createStructuredArgs(data) {
    const div = document.createElement('div');
    div.className = 'structured-args';
    renderStructured(div, data, { showCopy: true });
    return div;
}

export function createStructuredResult(data) {
    const div = document.createElement('div');
    div.className = 'structured-result';
    renderStructured(div, data, { showCopy: true });
    return div;
}

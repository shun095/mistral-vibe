/**
 * Slash Command Registry and Handler
 */
export class SlashCommandRegistry {
    constructor() {
        this.commands = new Map();
        this.loaded = false;
        this.token = '';
    }

    async loadCommands() {
        if (this.loaded) {
            return;
        }
        
        try {
            const response = await fetch('/api/commands', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await response.json();
            
            data.commands.forEach(cmd => {
                this.commands.set(cmd.name, cmd);
                cmd.aliases.forEach(alias => {
                    this.commands.set(alias, cmd);
                });
            });
            
            this.loaded = true;
        } catch (error) {
            console.error('[SlashCommands] Failed to load commands:', error);
        }
    }

    getCommand(input) {
        // Parse input like "/clean" or "/help"
        const match = input.match(/^\/(\w+)(?:\s+(.*))?$/);
        if (!match) return null;
        
        const [, commandName, args] = match;
        const cmd = this.commands.get(`/${commandName}`) || 
                    this.commands.get(commandName);
        
        return {
            command: cmd,
            name: commandName,
            args: args || ''
        };
    }

    async execute(commandName, args = '') {
        try {
            const response = await fetch('/api/command/execute', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    command: commandName,
                    args: args
                })
            });
            
            return await response.json();
        } catch (error) {
            console.error(`Failed to execute command ${commandName}:`, error);
            return { success: false, error: error.message };
        }
    }

    getCompletions(prefix) {
        const lowerPrefix = prefix.toLowerCase();
        const completions = Array.from(this.commands.entries())
            .filter(([key]) => key.toLowerCase().startsWith(lowerPrefix))
            .map(([key, cmd]) => ({
                label: key,
                description: cmd.description
            }));
        return completions;
    }
}

/**
 * Slash Command Autocomplete
 */
export class SlashAutocomplete {
    constructor(inputElement, registry) {
        this.input = inputElement;
        this.registry = registry;
        this.visible = false;
        this.selectedIndex = -1;
        this.suggestions = [];
        
        this.container = this.createContainer();
        this.bindEvents();
    }

    createContainer() {
        const container = document.createElement('div');
        container.className = 'slash-autocomplete';
        container.innerHTML = '<ul class="suggestions"></ul>';
        document.body.appendChild(container);
        return container;
    }

    bindEvents() {
        this.input.addEventListener('input', () => this.handleInput());
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.slash-autocomplete') && 
                !e.target.closest('#message-input')) {
                this.hide();
            }
        });
    }

    handleInput() {
        const value = this.input.value;
        if (!value.startsWith('/')) {
            this.hide();
            return;
        }

        const words = value.split(/\s+/);
        const lastWord = words[words.length - 1];
        
        if (lastWord.startsWith('/')) {
            this.showSuggestions(lastWord);
        } else {
            this.hide();
        }
    }

    async showSuggestions(prefix) {
        if (!this.registry.loaded) {
            await this.registry.loadCommands();
        }

        this.suggestions = this.registry.getCompletions(prefix);
        
        if (this.suggestions.length === 0) {
            this.hide();
            return;
        }

        this.container.style.display = 'block';
        this.render();
        this.position();
        this.visible = true;
        this.selectedIndex = this.suggestions.length - 1;
    }

    render() {
        const list = this.container.querySelector('.suggestions');
        list.innerHTML = this.suggestions.map((sug, idx) => `
            <li class="${idx === this.selectedIndex ? 'selected' : ''}">
                <strong>${this.escapeHtml(sug.label)}</strong>
                <span>${this.escapeHtml(sug.description)}</span>
            </li>
        `).join('');
        
        // Add click handlers to suggestions
        const items = list.querySelectorAll('li');
        items.forEach((item, idx) => {
            item.addEventListener('click', () => {
                this.selectedIndex = idx;
                this.complete(this.suggestions[idx].label);
            });
        });
    }

    position() {
        const inputRect = this.input.getBoundingClientRect();
        const containerRect = this.container.getBoundingClientRect();
        
        this.container.style.top = `${inputRect.top - containerRect.height + window.scrollY}px`;
        this.container.style.left = `${inputRect.left + window.scrollX}px`;
        this.container.style.minWidth = `${inputRect.width}px`;
    }

    hide() {
        this.visible = false;
        this.container.style.display = 'none';
        this.suggestions = [];
        this.selectedIndex = -1;
    }

   show() {
        if (this.suggestions.length > 0) {
            this.container.style.display = 'block';
            this.render();
        }
    }

    selectCurrent() {
        if (this.selectedIndex < 0 || this.selectedIndex >= this.suggestions.length) {
            return null;
        }
        return this.suggestions[this.selectedIndex];
    }

    next() {
        if (this.suggestions.length === 0) return;
        this.selectedIndex = (this.selectedIndex + 1) % this.suggestions.length;
        this.render();
    }

    previous() {
        if (this.suggestions.length === 0) return;
        this.selectedIndex = (this.selectedIndex - 1 + this.suggestions.length) % this.suggestions.length;
        this.render();
    }

    handleKeydown(e) {
        if (!this.visible) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.previous(); // Down = toward input = lower index with column-reverse
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.next(); // Up = away from input = higher index with column-reverse
                break;
            case 'Tab':
            case 'Enter':
                const selected = this.selectCurrent();
                if (selected) {
                    e.preventDefault();
                    this.complete(selected.label);
                }
                break;
            case 'Escape':
                this.hide();
                break;
        }
    }

    complete(text) {
        const value = this.input.value;
        const words = value.split(/\s+/);
        const lastWord = words[words.length - 1];
        
        // Replace the last word with completion
        words[words.length - 1] = text;
        this.input.value = words.join(' ');
        this.hide();
        this.input.focus();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

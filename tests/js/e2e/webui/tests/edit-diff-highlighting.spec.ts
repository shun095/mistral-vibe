import { test, expect } from "../fixtures";

test.describe("Edit Diff Syntax Highlighting", () => {
  test("edit tool result - code highlighted as diff", async ({ page }) => {
    const result = {
      file: "/project/vibe/cli/web_ui/static/js/app.js",
      message: "The file has been updated successfully.",
      old_string: "    toggleTheme() {\n        const currentTheme = document.documentElement.getAttribute('data-theme');\n        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';\n        const icon = this.elements.themeToggle.querySelector('.material-symbols-rounded');\n\n        document.documentElement.setAttribute('data-theme', newTheme);\n        localStorage.setItem('theme', newTheme);\n        icon.textContent = newTheme === 'dark' ? 'light_mode' : 'dark_mode';\n    }",
      new_string: "    toggleTheme() {\n        const currentTheme = document.documentElement.getAttribute('data-theme');\n        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';\n        const icon = this.elements.themeToggle.querySelector('.material-symbols-rounded');\n\n        document.documentElement.setAttribute('data-theme', newTheme);\n        localStorage.setItem('theme', newTheme);\n        icon.textContent = newTheme === 'dark' ? 'light_mode' : 'dark_mode';\n        this.applyHljsTheme(newTheme);\n    }",
    };

    const domState = await page.evaluate(
      ({ toolName, result }) => {
        const vibeClient = (window as any).vibeClient;
        const formatted = vibeClient.formatToolResult(toolName, result);
        document.body.appendChild(formatted);

        const preBlock = document.querySelector('pre.tool-formatter-code-block');
        if (!preBlock) {
          return { error: 'no pre.tool-formatter-code-block' };
        }

        const innerHTML = preBlock.innerHTML.slice(0, 3000);

        return {
          hasHljsAddition: innerHTML.includes('hljs-addition'),
          hasHljsDeletion: innerHTML.includes('hljs-deletion'),
          hasHljsSelectorTag: innerHTML.includes('hljs-selector-tag'),
          hasHljsKeyword: innerHTML.includes('hljs-keyword'),
        };
      },
      { toolName: "edit", result }
    );

    expect(domState.error).toBeUndefined();
    expect(domState.hasHljsAddition).toBe(true);
    expect(domState.hasHljsDeletion).toBe(true);
    expect(domState.hasHljsSelectorTag).toBe(false);
    expect(domState.hasHljsKeyword).toBe(false);
  });

  test("edit_file tool result - code highlighted as diff", async ({ page }) => {
    const result = {
      file: "/project/vibe/cli/web_ui/static/js/app.js",
      blocks_applied: 1,
      lines_changed: 10,
      content: "    toggleTheme() {\n        const currentTheme = document.documentElement.getAttribute('data-theme');\n-        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';\n+        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';\n        const icon = this.elements.themeToggle.querySelector('.material-symbols-rounded');\n\n        document.documentElement.setAttribute('data-theme', newTheme);\n        localStorage.setItem('theme', newTheme);\n        icon.textContent = newTheme === 'dark' ? 'light_mode' : 'dark_mode';\n    }",
    };

    const domState = await page.evaluate(
      ({ toolName, result }) => {
        const vibeClient = (window as any).vibeClient;
        const formatted = vibeClient.formatToolResult(toolName, result);
        document.body.appendChild(formatted);

        const preBlock = document.querySelector('pre.tool-formatter-code-block');
        if (!preBlock) {
          return { error: 'no pre.tool-formatter-code-block' };
        }

        const innerHTML = preBlock.innerHTML.slice(0, 3000);

        return {
          hasHljsAddition: innerHTML.includes('hljs-addition'),
          hasHljsDeletion: innerHTML.includes('hljs-deletion'),
          hasHljsSelectorTag: innerHTML.includes('hljs-selector-tag'),
          hasHljsKeyword: innerHTML.includes('hljs-keyword'),
        };
      },
      { toolName: "edit_file", result }
    );

    expect(domState.error).toBeUndefined();
    expect(domState.hasHljsAddition).toBe(true);
    expect(domState.hasHljsDeletion).toBe(true);
    expect(domState.hasHljsSelectorTag).toBe(false);
    expect(domState.hasHljsKeyword).toBe(false);
  });
});

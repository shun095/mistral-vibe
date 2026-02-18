# edit_file Tool

## Purpose
Replaces text within a file. This tool is designed to replace exact literal strings within files, making it a precise alternative to search_replace.

## How It Works
- **Single replacement (default)**: Replaces only the first occurrence of `old_string`
- **Multiple replacement**: Set `replace_all=true` to replace all occurrences

## Usage Guidelines

### Required Parameters
1. **file_path**: Must be an absolute path starting with `/`
2. **old_string**: Must be the exact literal text to replace (including whitespace, indentation, and newlines)
3. **new_string**: Must be the exact literal text to replace `old_string` with

### Important Requirements
- **Exact Match Required**: The `old_string` must match exactly what's in the file, including all whitespace, indentation, and newlines
- **Absolute Path**: `file_path` must be an absolute path (starting with `/`)
- **Significant Context**: For single replacements, include at least 3 lines of context BEFORE and AFTER the target text to ensure precise targeting
- **Never Escape**: Do not escape `old_string` or `new_string` - they must be exact literal text

### Examples

#### Example 1: Simple single-line replacement
```python
edit_file(
    file_path="/home/user/project/main.py",
    old_string="def old_function():\n    return \"old\"",
    new_string="def new_function():\n    return \"new\""
)
```

#### Example 2: Multi-line replacement with context
```python
edit_file(
    file_path="/home/user/project/utils.py",
    old_string="    def old_method(self):\n        # Do something\n        return result\n    \n    def another_method(self):",
    new_string="    def new_method(self):\n        # Do something different\n        return new_result\n    \n    def another_method(self):"
)
```

#### Example 3: Replace all occurrences
```python
edit_file(
    file_path="/home/user/project/config.py",
    old_string="old_value = True",
    new_string="new_value = False",
    replace_all=True
)
```

## Error Cases
The tool will fail if:
- `file_path` is not an absolute path
- `old_string` is not found exactly in the file (including whitespace)
- `old_string` or `new_string` is empty
- File does not exist
- `file_path` is a directory, not a file

## Best Practices
1. Always use `read_file` to examine the file content before attempting to edit
2. Include sufficient context in `old_string` to uniquely identify the target location
3. Match exact whitespace and indentation
4. Use `replace_all=True` when you want to replace every occurrence, not just the first one
5. Consider the impact of your changes on the rest of the file

## Comparison with search_replace
- **edit_file**: Requires exact literal text matching with significant context; simpler, more predictable
- **search_replace**: Supports SEARCH/REPLACE blocks with fuzzy matching; more flexible but complex
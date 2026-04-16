Use `edit_file` to replace text within a file. By default, replaces a single occurrence. Set `replace_all` to true when you intend to modify every instance of `old_string`.

## Arguments

- `file_path`: The path to the file to modify (must be absolute, starting with `/`)
- `old_string`: The exact text to find and replace
- `new_string`: The text to replace it with
- `replace_all`: Set to `true` to replace all occurrences (default: `false`)

## IMPORTANT

- The `old_string` must match **exactly** what's in the file, including whitespace, indentation, and newlines
- For single replacements, include at least 3 lines of context BEFORE and AFTER the target text
- Do not escape `old_string` or `new_string` - they must be exact literal text
- Always use `read_file` to examine the file content before attempting to edit

## Examples

**Single replacement with context:**
```python
edit_file(
    file_path="/home/user/project/utils.py",
    old_string="    def old_method(self):\n        # Do something\n        return result\n    \n    def another_method(self):",
    new_string="    def new_method(self):\n        # Do something different\n        return new_result\n    \n    def another_method(self):"
)
```

**Replace all occurrences:**
```python
edit_file(
    file_path="/home/user/project/config.py",
    old_string="old_value = True",
    new_string="new_value = False",
    replace_all=True
)
```

## Best Practices

1. Always use `read_file` to examine the file content before attempting to edit
2. Include sufficient context in `old_string` to uniquely identify the target location
3. Match exact whitespace and indentation
4. Use `replace_all=True` when you want to replace every occurrence, not just the first one
5. Consider the impact of your changes on the rest of the file

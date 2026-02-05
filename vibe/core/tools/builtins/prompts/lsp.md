# LSP Tool

The LSP tool provides access to Language Server Protocol (LSP) servers for real-time code analysis and diagnostics.

## Usage

```python
lsp.check_file(file_path)  # Auto-detects server based on file extension
lsp.check_file(file_path, server_name="pyright")  # Specify server
```

## Supported Servers

- **pyright**: Python type checking (`.py` files)
- **typescript**: TypeScript/JavaScript analysis (`.ts`, `.js`, `.tsx`, `.jsx` files)
- **deno**: Deno LSP server for TypeScript/JavaScript

## Behavior

The LSP tool automatically:
1. Detects the appropriate LSP server based on file extension
2. Starts the LSP server if not already running
3. Opens and analyzes the file
4. Returns diagnostics (errors, warnings, etc.)
5. Formats diagnostics in a readable format
6. Limits output to 20 diagnostics to avoid overwhelming the user

## Integration with File Operations

The LSP tool is automatically integrated with file operations like `write_file` and `search_replace`. After any file modification, the LSP tool will automatically check the file for errors and provide feedback to the LLM.

## Example Output

```
ERROR at line 5, column 3: Name 'undefined_var' is not defined
WARNING at line 10, column 7: Unused variable 'x'
ERROR at line 15, column 1: Missing return statement
```

## Performance Considerations

- LSP servers are started on-demand and cached for reuse
- Servers are automatically stopped when the session ends
- Diagnostic requests are limited to avoid performance issues

Use `lsp` to interact with Language Server Protocol (LSP) servers to get diagnostics and feedback on code.

## Supported Servers

- **pyright**: Python type checking (`.py` files)
- **typescript**: TypeScript/JavaScript analysis (`.ts`, `.js`, `.tsx`, `.jsx` files)
- **deno**: Deno LSP server for TypeScript/JavaScript

## Commands

- **diagnostics**: Get diagnostics (errors, warnings, hints) for a file
- **definition**: Find the definition of a symbol at the given location
- **type_definition**: Find the type definition of a symbol at the given location
- **implementation**: Find implementations of a symbol at the given location
- **references**: Find all references to a symbol at the given location

## Arguments

- `file_path`: Path to the file to check for diagnostics or navigate to symbol
- `command`: LSP command to execute (default: `"diagnostics"`)
- `server_name`: Name of the LSP server (auto-detected if not specified)
- `line`: Line number for goto commands (0-indexed, required for definition/type_definition/implementation)
- `character`: Character position for goto commands (0-indexed)
- `symbol_name`: Symbol name to find on the specified line

## Examples

**Get diagnostics for a file:**
```python
lsp(file_path="/home/user/project/main.py")
```

**Find definition of a symbol:**
```python
lsp(
    file_path="/home/user/project/main.py",
    command="definition",
    line=42,
    character=10
)
```

**Find type definition:**
```python
lsp(
    file_path="/home/user/project/utils.ts",
    command="type_definition",
    line=15,
    character=5
)
```

**Find references to a symbol:**
```python
lsp(
    file_path="/home/user/project/app.py",
    command="references",
    line=20,
    character=8,
    symbol_name="MyClass"
)
```

## Best Practices

1. Use `diagnostics` command (default) to check for errors and warnings in a file
2. For goto commands, provide both `line` and `character` for precise symbol location
3. Use `symbol_name` when you want to find a specific symbol on a line
4. The `server_name` parameter is optional - the tool auto-detects the appropriate server

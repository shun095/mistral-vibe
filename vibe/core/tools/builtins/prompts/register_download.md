Use `register_download` to register a file as downloadable content in the WebUI. Creates a download button in the chat interface.

## Behavior

- Files must exist on disk at registration time
- Files must be within the current project directory — paths outside are rejected with a `ToolError`
- Relative paths are resolved against the project directory (cwd)
- Filename is auto-generated from the file path
- MIME type is auto-detected from file extension
- Creates a download card with button in the chat

## Arguments

- `file_path`: Path to the file to register (absolute or relative, must be within project directory)
- `description`: Optional description of the file for display purposes

## Examples

```python
# Register a file within the project directory
register_download(
    file_path="output/results.csv",
    description="Analysis results"
)

# Register using an absolute path (must still be within project directory)
register_download(file_path="/path/to/project/report.pdf")
```

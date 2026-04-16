Use `register_download` to register a file as downloadable content in the WebUI. Creates a download button in the chat interface.

## Behavior

- Files must exist on disk at registration time
- Filename is auto-generated from the file path
- MIME type is auto-detected from file extension
- Creates a download card with button in the chat

## Arguments

- `file_path`: Path to the file to register (absolute or relative)
- `description`: Optional description of the file for display purposes

## Examples

```python
# Register a file with description
register_download(
    file_path="/tmp/results.csv",
    description="Analysis results"
)

# Register without description
register_download(file_path="/tmp/output.txt")
```

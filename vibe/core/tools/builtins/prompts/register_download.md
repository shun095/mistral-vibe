Use `register_download` to make a file downloadable in the WebUI.

- Files must exist on disk at registration time
- Filename is auto-generated from the file path
- MIME type is auto-detected from file extension
- Creates a download card with button in the chat

**Arguments:**
- `file_path`: Path to the file to register
- `description`: Optional description for display

**Usage Examples:**

```python
# Register a file with description
register_download(
    file_path="/tmp/results.csv",
    description="Analysis results"
)

# Register without description
register_download(file_path="/tmp/output.txt")
```

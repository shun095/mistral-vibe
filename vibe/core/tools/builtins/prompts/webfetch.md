Fetches content from a specified URL and converts HTML to markdown for readability. Use this tool when you need to retrieve and analyze web content.

## Behavior

- Prefer a more specialized tool over `web_fetch` when one is available
- URLs must be valid
- Read-only: does not modify any files
- Defaults to reading first 1000 lines with line numbers (e.g., `1: content`)
- Content is capped at a byte limit. If `was_truncated` is true, the page had more content that was cut off

## Arguments

- `url`: URL to fetch (http/https)
- `timeout`: Timeout in seconds (max 120)
- `pattern`: Optional regex pattern to filter lines. Returns matching lines with line numbers
- `offset`: Number of lines to skip from the start (0-indexed). Default: 0
- `limit`: Maximum number of lines to read. Default: 1000

## Notes

- Cannot combine `pattern` with custom `offset`/`limit` - use one or the other
- Result includes `lines_read`, `total_lines`, and `was_truncated` for pagination

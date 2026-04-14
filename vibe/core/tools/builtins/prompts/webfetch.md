Fetches content from a specified URL and converts HTML to markdown for readability.
Use this tool when you need to retrieve and analyze web content.

- Prefer a more specialized tool over `web_fetch` when one is available.
- URLs must be valid.
- Read-only: does not modify any files.
- Defaults to reading first 1000 lines with line numbers (e.g., `1: content`).
- Use `pattern` (regex) to find matching lines with original line numbers.
- Use `offset` (0-indexed) and `limit` to read specific line ranges.
- Cannot combine `pattern` with custom `offset`/`limit` - use one or the other.
- Result includes `lines_read`, `total_lines`, and `was_truncated` for pagination.
- Content is capped at a byte limit. If `was_truncated` is true, the page had more content that was cut off.

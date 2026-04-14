Use `read_image` to read an image file or fetch an image from a URL. Returns the image in a format suitable for LLM processing.

- Supports `file://`, `http://`, and `https://` URLs
- Validates that the file/content is an actual image before processing
- Raises an error if the target is not a supported image type

**Supported image types:**
- JPEG (`image/jpeg`)
- PNG (`image/png`)
- GIF (`image/gif`)
- WebP (`image/webp`)
- BMP (`image/bmp`)
- TIFF (`image/tiff`)
- SVG (`image/svg+xml`)
- AVIF (`image/avif`)

**Arguments:**
- `image_url`: URL for the image. Can be `http://...`, `https://...`, or `file://...`

**Error cases:**
- Non-image files (e.g., `.txt`, `.pdf`, `.py`) raise `ToolError` with detected MIME type
- Missing files raise `ToolError` with "Image file not found"
- Directories raise `ToolError` with "Path is a directory, not a file"
- Files exceeding size limit (default 10MB) raise `ToolError` with size details
- HTTP URLs returning non-image Content-Type raise `ToolError` with detected type

**Examples:**

```python
# Read a local image file
read_image(image_url="file:///path/to/image.png")

# Fetch an image from a URL
read_image(image_url="https://example.com/image.jpg")
```

**Remember:** The tool validates image types before encoding. Non-image files will raise an error instead of being sent to the LLM backend.

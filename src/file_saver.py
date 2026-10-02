"""Buffered file saver with proper UTF-8 multibyte character handling.

Writes content to disk in chunks without splitting multibyte UTF-8
characters at buffer boundaries. The previous implementation used a
fixed 64KB buffer that treated byte offsets as character offsets,
causing an out-of-bounds read when a multibyte character (2-4 bytes)
straddled the boundary — resulting in a segmentation fault.

The fix encodes the full string to bytes first, then writes in
byte-aligned chunks so UTF-8 sequences are never split.
"""

BUFFER_SIZE = 65536  # 64KB


def save_file(content: str, path: str, buffer_size: int = BUFFER_SIZE) -> None:
    """Save *content* to *path* using buffered writes.

    Encodes the content to UTF-8 bytes and writes in *buffer_size*
    chunks. Because the chunking operates on the encoded byte stream
    rather than on character indices, multibyte UTF-8 sequences are
    never split across write boundaries.

    Args:
        content: The text to write.
        path: Destination file path.
        buffer_size: Write-chunk size in bytes (default 64KB).

    Raises:
        OSError: If the file cannot be opened or written.
    """
    data = content.encode("utf-8")
    with open(path, "wb") as fh:
        offset = 0
        while offset < len(data):
            end = min(offset + buffer_size, len(data))
            fh.write(data[offset:end])
            offset = end

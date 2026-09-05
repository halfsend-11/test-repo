"""Chunked file writer with UTF-8-aware chunk boundaries.

Writes data to files in fixed-size chunks (default 64 KB).  Before v2.3.1
the chunked writer split at exact byte offsets, which could bisect a
multibyte UTF-8 character and produce invalid byte sequences or a
segmentation fault.

This module ensures chunk boundaries never split a multibyte UTF-8
sequence by adjusting the split point backward to the start of any
incomplete character at the chunk edge.
"""

from __future__ import annotations

# Default chunk size: 64 KB
DEFAULT_CHUNK_SIZE = 65536

# Minimum chunk size: must be at least 4 bytes (the maximum length of a
# single UTF-8 encoded character) to guarantee forward progress.
MIN_CHUNK_SIZE = 4


def _find_utf8_safe_split(data: bytes, offset: int) -> int:
    """Return the largest split point <= *offset* that does not bisect a
    UTF-8 character.

    UTF-8 encoding reference:
      0xxxxxxx  (0x00–0x7F)  single-byte (ASCII)
      110xxxxx  (0xC0–0xDF)  leading byte of a 2-byte sequence
      1110xxxx  (0xE0–0xEF)  leading byte of a 3-byte sequence
      11110xxx  (0xF0–0xF7)  leading byte of a 4-byte sequence
      10xxxxxx  (0x80–0xBF)  continuation byte

    If the byte at *offset* is a continuation byte we walk backward
    (at most 3 bytes, the maximum number of continuation bytes in a
    valid UTF-8 character) to find the leading byte and return its
    position so the character stays intact in the next chunk.

    Args:
        data: A ``bytes`` object containing UTF-8 encoded text.
        offset: Proposed split point (byte index).

    Returns:
        An adjusted split point that keeps all multibyte characters
        intact.
    """
    if offset >= len(data):
        return len(data)
    if offset <= 0:
        return 0

    # If the byte at offset is not a continuation byte it is either
    # ASCII or the leading byte of a new character — safe to split here.
    if (data[offset] & 0xC0) != 0x80:
        return offset

    # Walk backward up to 3 positions to locate the leading byte of the
    # character that straddles the boundary.
    for i in range(1, 4):
        pos = offset - i
        if pos < 0:
            return 0
        if (data[pos] & 0xC0) != 0x80:
            return pos

    # Fallback: after 3 steps we still see continuation bytes.  This
    # should not happen with valid UTF-8; return the original offset.
    return offset


def save_file(filepath: str, content: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> int:
    """Save *content* to *filepath* using UTF-8-aware chunked writes.

    The string is first encoded to UTF-8 bytes, then written in chunks
    whose boundaries are adjusted so that no multibyte character is split
    across two writes.

    Args:
        filepath: Destination file path.
        content: The text to write (must be ``str``).
        chunk_size: Maximum chunk size in bytes (default 64 KB).
            Must be >= 4 (the maximum byte length of a UTF-8 character).

    Returns:
        Total number of bytes written.

    Raises:
        TypeError: If *content* is not a ``str``.
        ValueError: If *chunk_size* is less than ``MIN_CHUNK_SIZE`` (4).
        OSError: If the file cannot be opened or written to.
    """
    if not isinstance(content, str):
        raise TypeError(
            f"content must be a string, got {type(content).__name__}"
        )
    if chunk_size < MIN_CHUNK_SIZE:
        raise ValueError(
            f"chunk_size must be >= {MIN_CHUNK_SIZE}, got {chunk_size}"
        )

    data = content.encode("utf-8")
    total = len(data)
    written = 0

    with open(filepath, "wb") as fh:
        while written < total:
            end = min(written + chunk_size, total)
            if end < total:
                end = _find_utf8_safe_split(data, end)
            fh.write(data[written:end])
            written = end

    return total


def read_file(filepath: str) -> str:
    """Read *filepath* and return its content decoded as UTF-8.

    Args:
        filepath: Path to the file to read.

    Returns:
        The decoded text content.

    Raises:
        OSError: If the file cannot be opened.
    """
    with open(filepath, "rb") as fh:
        return fh.read().decode("utf-8")

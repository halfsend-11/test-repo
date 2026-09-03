"""Chunked file writer with UTF-8-aware chunk boundaries.

Writes data to files in fixed-size chunks (default 64KB). Prior to v2.3.1,
the chunked writer split at exact byte offsets, which could bisect a
multibyte UTF-8 character and produce invalid byte sequences or crashes.

This module ensures chunk boundaries never split a multibyte UTF-8
sequence by adjusting the split point backward to the start of any
incomplete character at the chunk edge.
"""

# Default chunk size: 64KB
DEFAULT_CHUNK_SIZE = 65536


def _find_utf8_safe_split(data, offset):
    """Find the largest split point <= offset that does not bisect a UTF-8 character.

    UTF-8 encoding rules:
      - 0xxxxxxx  (0x00-0x7F): single-byte (ASCII)
      - 110xxxxx  (0xC0-0xDF): first byte of a 2-byte sequence
      - 1110xxxx  (0xE0-0xEF): first byte of a 3-byte sequence
      - 11110xxx  (0xF0-0xF7): first byte of a 4-byte sequence
      - 10xxxxxx  (0x80-0xBF): continuation byte

    If the byte at `offset` is a continuation byte, we walk backward to
    find the leading byte of the character and split before it.

    Args:
        data: The bytes object to split.
        offset: The proposed split point (byte index).

    Returns:
        A safe split point that does not bisect a multibyte character.
    """
    if offset >= len(data):
        return len(data)

    if offset <= 0:
        return 0

    # If the byte at offset is not a continuation byte, it's a valid
    # split point (it's either ASCII or the start of a new character).
    if (data[offset] & 0xC0) != 0x80:
        return offset

    # Walk backward (up to 3 bytes, since max UTF-8 char is 4 bytes)
    # to find the leading byte of the character that straddles the boundary.
    for i in range(1, 4):
        pos = offset - i
        if pos < 0:
            return 0
        byte = data[pos]
        # Check if this is a leading byte (not a continuation byte)
        if (byte & 0xC0) != 0x80:
            return pos

    # Fallback: should not happen with valid UTF-8, but if we walked
    # back 3 bytes and still found continuation bytes, split at offset.
    return offset


def save_file(filepath, content, chunk_size=DEFAULT_CHUNK_SIZE):
    """Save content to a file using UTF-8-aware chunked writes.

    Encodes the string content as UTF-8 bytes and writes it in chunks,
    ensuring that chunk boundaries never split a multibyte character.

    Args:
        filepath: Path to the output file.
        content: The string content to write.
        chunk_size: Size of each write chunk in bytes (default 64KB).

    Returns:
        The number of bytes written.

    Raises:
        OSError: If the file cannot be opened or written.
        TypeError: If content is not a string.
    """
    if not isinstance(content, str):
        raise TypeError(f"content must be a string, got {type(content).__name__}")

    data = content.encode("utf-8")
    total = len(data)
    written = 0

    with open(filepath, "wb") as f:
        while written < total:
            end = min(written + chunk_size, total)
            if end < total:
                end = _find_utf8_safe_split(data, end)
            chunk = data[written:end]
            f.write(chunk)
            written = end

    return total


def read_file(filepath):
    """Read a file and return its content as a string.

    Args:
        filepath: Path to the file to read.

    Returns:
        The file content as a string.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    with open(filepath, "rb") as f:
        data = f.read()
    return data.decode("utf-8")

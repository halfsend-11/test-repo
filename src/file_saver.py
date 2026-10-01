"""File saving module with correct UTF-8 buffer handling.

This module provides file saving functionality that correctly handles
UTF-8 multibyte characters by allocating buffers based on byte length
rather than character count. This fixes the segmentation fault that
occurred when saving files larger than 64KB containing multibyte
characters (e.g., emoji or CJK characters).

Bug: The previous implementation (v2.3.1) allocated a write buffer
using len(content) which returns the number of characters, not bytes.
For ASCII content, character count equals byte count so the buffer was
sufficient. For multibyte UTF-8 content, the byte representation is
larger than the character count, causing the buffer to overflow at the
64KB boundary.

Fix: Use len(content.encode('utf-8')) to determine the actual byte
size needed for the buffer, ensuring it is always large enough to hold
the full encoded content.
"""

import os
from pathlib import Path

# Default buffer size threshold in bytes. Files larger than this are
# written in chunks to limit memory usage.
BUFFER_SIZE = 65536  # 64KB


def save_file(path, content):
    """Save content to a file with correct UTF-8 buffer handling.

    Allocates the write buffer based on the byte length of the UTF-8
    encoded content, not the character count. This ensures multibyte
    characters do not cause buffer overflows.

    Args:
        path: File path to write to (str or Path).
        content: String content to save.

    Returns:
        int: Number of bytes written.

    Raises:
        TypeError: If content is not a string.
        OSError: If the file cannot be written.
    """
    if not isinstance(content, str):
        raise TypeError(f"content must be str, got {type(content).__name__}")

    encoded = content.encode("utf-8")
    byte_length = len(encoded)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if byte_length <= BUFFER_SIZE:
        # Small file: write in one operation
        path.write_bytes(encoded)
    else:
        # Large file: write in chunks to limit memory usage
        with open(path, "wb") as f:
            offset = 0
            while offset < byte_length:
                chunk_end = min(offset + BUFFER_SIZE, byte_length)
                f.write(encoded[offset:chunk_end])
                offset = chunk_end

    return byte_length


def load_file(path):
    """Load a UTF-8 encoded file and return its content as a string.

    Args:
        path: File path to read from (str or Path).

    Returns:
        str: The file content.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnicodeDecodeError: If the file is not valid UTF-8.
    """
    path = Path(path)
    raw = path.read_bytes()
    return raw.decode("utf-8")

"""File writer module with proper UTF-8 buffer handling.

This module provides buffered file writing that correctly sizes buffers
based on byte length rather than character count, avoiding buffer overflows
when writing multibyte UTF-8 content larger than 64KB.
"""

import os

# Default buffer size in bytes.
BUFFER_SIZE = 65536  # 64KB


def write_file(path, content, buffer_size=BUFFER_SIZE):
    """Write content to a file using a byte-length-aware buffer.

    Prior to v2.3.1 the buffer was sized using ``len(content)`` (character
    count).  For multibyte UTF-8 text the actual byte count can be
    significantly larger than the character count, causing a buffer overflow
    when the encoded size exceeds *buffer_size*.

    This implementation encodes the content first, then iterates over the
    resulting bytes in *buffer_size* chunks so the buffer is never
    overflowed regardless of character encoding.

    Args:
        path: Destination file path.
        content: Unicode string to write.
        buffer_size: Maximum number of bytes per write call.

    Raises:
        TypeError: If *content* is not a string.
        OSError: If the file cannot be written.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")

    encoded = content.encode("utf-8")
    total = len(encoded)

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "wb") as fh:
        offset = 0
        while offset < total:
            end = min(offset + buffer_size, total)
            fh.write(encoded[offset:end])
            offset = end


def read_file(path):
    """Read a UTF-8 file and return its content as a string.

    Args:
        path: Source file path.

    Returns:
        The file content decoded as UTF-8.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")

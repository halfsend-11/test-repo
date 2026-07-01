"""File saving module with proper UTF-8 multibyte character support.

This module handles saving files of arbitrary size, correctly accounting
for UTF-8 multibyte characters when calculating buffer sizes. The buffer
allocation uses byte length (not character count) to prevent overflow
when content contains emoji, CJK, or other multibyte characters.
"""

import os
import tempfile

# Buffer size for chunked writes (256KB, well above the old 64KB limit)
WRITE_BUFFER_SIZE = 256 * 1024


def save_file(path: str, content: str) -> None:
    """Save content to a file, handling UTF-8 multibyte characters correctly.

    Encodes the content to UTF-8 bytes first, then writes in chunks using
    byte length for buffer management. This avoids the previous bug where
    character count was used instead of byte length, causing a buffer
    overflow for files >64KB containing multibyte characters.

    Args:
        path: The file path to write to.
        content: The string content to save.

    Raises:
        OSError: If the file cannot be written.
    """
    encoded = content.encode("utf-8")
    dir_name = os.path.dirname(os.path.abspath(path))

    # Write to a temp file first, then atomically rename for crash safety
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".save_")
    try:
        offset = 0
        while offset < len(encoded):
            chunk = encoded[offset : offset + WRITE_BUFFER_SIZE]
            os.write(fd, chunk)
            offset += len(chunk)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_file(path: str) -> str:
    """Load a UTF-8 encoded file and return its content as a string.

    Args:
        path: The file path to read from.

    Returns:
        The file content as a string.

    Raises:
        OSError: If the file cannot be read.
        UnicodeDecodeError: If the file is not valid UTF-8.
    """
    with open(path, "rb") as f:
        return f.read().decode("utf-8")

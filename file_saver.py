"""File saving module with correct UTF-8 multibyte character handling.

Provides save/load helpers that use byte length (not character count)
for buffer allocation, preventing overflow when content contains emoji,
CJK, or other multibyte UTF-8 characters above the 64KB chunk boundary.
"""

import os
import tempfile

# Chunk size for buffered writes.  Previous versions used a 64KB buffer
# sized by *character count*, which under-allocated when multibyte
# characters expanded the byte length past the buffer.  We now size
# in bytes and use 256KB to reduce the number of write syscalls.
WRITE_CHUNK_SIZE = 256 * 1024


def save_file(path: str, content: str) -> None:
    """Save *content* to *path* as UTF-8, safe for any size or encoding.

    The content is encoded to bytes first so that the write loop always
    operates on byte lengths.  A temporary file + atomic rename guards
    against partial writes on crash.

    Args:
        path: Destination file path.
        content: Unicode string to persist.

    Raises:
        OSError: If the file cannot be written.
    """
    data = content.encode("utf-8")
    dest_dir = os.path.dirname(os.path.abspath(path))

    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix=".save_")
    try:
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + WRITE_CHUNK_SIZE]
            os.write(fd, chunk)
            offset += len(chunk)
        os.fsync(fd)
        os.close(fd)
        fd = -1  # mark as closed so the except block skips it
        os.replace(tmp_path, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_file(path: str) -> str:
    """Read a UTF-8 file and return its content as a string.

    Args:
        path: File to read.

    Returns:
        Decoded file content.

    Raises:
        OSError: If the file cannot be read.
        UnicodeDecodeError: If the file is not valid UTF-8.
    """
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")

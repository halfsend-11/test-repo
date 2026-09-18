"""File save module with proper UTF-8 multibyte character handling.

This module provides file saving functionality that correctly calculates
buffer sizes based on byte length rather than character count, preventing
buffer overruns when saving files containing multibyte UTF-8 characters
(e.g., emoji, CJK characters) that exceed 64KB.
"""

import os
import tempfile

# Buffer size constant: 64KB
BUFFER_SIZE = 64 * 1024


def _calculate_buffer_size(content: str) -> int:
    """Calculate the required buffer size based on byte length.

    Uses the encoded byte length of the content rather than the character
    count. This ensures multibyte UTF-8 characters (which can be 2-4 bytes
    each) are accounted for correctly.

    Args:
        content: The string content to calculate buffer size for.

    Returns:
        The required buffer size in bytes, rounded up to the nearest
        multiple of BUFFER_SIZE.
    """
    byte_length = len(content.encode("utf-8"))
    if byte_length == 0:
        return BUFFER_SIZE
    # Round up to the nearest multiple of BUFFER_SIZE
    return ((byte_length - 1) // BUFFER_SIZE + 1) * BUFFER_SIZE


def save_file(filepath: str, content: str) -> int:
    """Save content to a file with proper UTF-8 handling.

    Writes the content to a temporary file first, then atomically renames
    it to the target path to prevent data corruption on failure.

    Args:
        filepath: The destination file path.
        content: The string content to save.

    Returns:
        The number of bytes written.

    Raises:
        OSError: If the file cannot be written.
        ValueError: If content is None.
    """
    if content is None:
        raise ValueError("content must not be None")

    encoded = content.encode("utf-8")
    byte_length = len(encoded)

    # Allocate buffer based on byte length, not character count
    buffer_size = _calculate_buffer_size(content)

    # Verify buffer is large enough for the encoded content
    if buffer_size < byte_length:
        raise RuntimeError(
            f"Buffer size {buffer_size} is smaller than content "
            f"byte length {byte_length}"
        )

    dir_name = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(dir_name, exist_ok=True)

    # Write to a temporary file first for atomic save
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".save_")
    try:
        with os.fdopen(fd, "wb") as f:
            # Write in buffer-sized chunks
            offset = 0
            while offset < byte_length:
                chunk = encoded[offset : offset + buffer_size]
                f.write(chunk)
                offset += len(chunk)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return byte_length


def load_file(filepath: str) -> str:
    """Load a UTF-8 encoded file.

    Args:
        filepath: The file path to read.

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

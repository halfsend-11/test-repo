"""File save module with proper UTF-8 byte-length buffer allocation.

Prior to v2.3.1, the save routine allocated buffers based on byte length
of the content. A regression in v2.3.1 changed the allocation to use
character count (len(text)) instead of byte length (len(text.encode())),
causing a buffer overflow and segfault when saving files larger than 64KB
that contain multibyte UTF-8 characters (emoji, CJK, etc.).

Fix: allocate the write buffer based on the encoded byte length of the
content, not the character count.
"""

BUFFER_SIZE = 65536  # 64KB


def calculate_buffer_size(content: str) -> int:
    """Calculate the required buffer size for saving content.

    Uses the byte length of the UTF-8 encoded content to determine
    the buffer size. This correctly handles multibyte characters
    (emoji, CJK, accented characters, etc.) whose byte representation
    is larger than their character count.

    Args:
        content: The text content to save.

    Returns:
        The required buffer size in bytes, rounded up to the nearest
        multiple of BUFFER_SIZE.
    """
    byte_length = len(content.encode("utf-8"))
    if byte_length == 0:
        return BUFFER_SIZE
    # Round up to the nearest multiple of BUFFER_SIZE
    return ((byte_length - 1) // BUFFER_SIZE + 1) * BUFFER_SIZE


def save_file(path: str, content: str) -> int:
    """Save text content to a file with proper UTF-8 encoding.

    Allocates a buffer based on the byte length of the encoded content,
    ensuring that multibyte UTF-8 characters do not cause buffer overflow.

    Args:
        path: The file path to write to.
        content: The text content to save.

    Returns:
        The number of bytes written.

    Raises:
        OSError: If the file cannot be written.
    """
    encoded = content.encode("utf-8")
    buffer_size = calculate_buffer_size(content)

    if len(encoded) > buffer_size:
        raise RuntimeError(
            f"Buffer allocation error: content requires {len(encoded)} bytes "
            f"but buffer is {buffer_size} bytes"
        )

    with open(path, "wb") as f:
        bytes_written = f.write(encoded)

    return bytes_written


def read_file(path: str) -> str:
    """Read a UTF-8 encoded file back into a string.

    Args:
        path: The file path to read from.

    Returns:
        The decoded text content.

    Raises:
        OSError: If the file cannot be read.
    """
    with open(path, "rb") as f:
        return f.read().decode("utf-8")

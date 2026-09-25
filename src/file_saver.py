"""File save module with correct UTF-8 buffer allocation.

Prior to this fix (v2.3.1), the save path allocated a write buffer
using the *character count* of the content. For ASCII-only text, character
count equals byte length, so files under 64 KB saved correctly. When
the content contained multibyte UTF-8 characters (emoji = 4 bytes,
CJK = 3 bytes), the actual byte length could exceed the 64 KB buffer
even though the character count did not, causing a segmentation fault
on write.

The fix uses ``len(data)`` on the encoded bytes instead of
``len(text)`` on the string to size the buffer.
"""

BUFFER_SIZE = 65536  # 64 KB


def _allocate_buffer(content: str) -> bytearray:
    """Return a buffer large enough to hold *content* encoded as UTF-8.

    Bug fix: size the buffer from the **byte length** of the encoded
    content, not from the character count.
    """
    encoded = content.encode("utf-8")
    size = max(BUFFER_SIZE, len(encoded))
    return bytearray(size)


def save_file(path: str, content: str) -> int:
    """Write *content* to *path* and return the number of bytes written.

    The content is encoded as UTF-8. A write buffer is allocated that
    is at least ``BUFFER_SIZE`` bytes or the encoded byte length,
    whichever is larger, so that multibyte characters never overflow
    the buffer.
    """
    encoded = content.encode("utf-8")
    buffer = _allocate_buffer(content)
    buffer[: len(encoded)] = encoded

    with open(path, "wb") as fh:
        fh.write(buffer[: len(encoded)])

    return len(encoded)

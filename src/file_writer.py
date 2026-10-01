"""Chunked file writer with UTF-8-aware buffer handling.

Writes files in chunks (default 64KB) while ensuring multibyte UTF-8
character sequences are never split across chunk boundaries.
"""

import os

BUFFER_SIZE = 65536  # 64KB


def _find_utf8_safe_boundary(data: bytes, limit: int) -> int:
    """Find the largest offset <= limit that does not split a UTF-8 sequence.

    UTF-8 continuation bytes have the form 10xxxxxx (0x80..0xBF).
    If the byte at *limit* is a continuation byte we walk backwards
    until we find the leading byte of the sequence and split just
    before it.
    """
    if limit >= len(data):
        return len(data)

    pos = limit
    # Walk back over any continuation bytes (max 3 for a 4-byte char).
    while pos > 0 and (data[pos] & 0xC0) == 0x80:
        pos -= 1

    return pos


def save_file(content: str, path: str, buffer_size: int = BUFFER_SIZE) -> None:
    """Save *content* to *path* using chunked writes.

    The content is encoded to UTF-8, then written in chunks of at most
    *buffer_size* bytes.  Chunk boundaries are adjusted so that
    multibyte characters are never split across writes.
    """
    encoded = content.encode("utf-8")
    tmp_path = path + ".tmp"

    try:
        with open(tmp_path, "wb") as fh:
            offset = 0
            while offset < len(encoded):
                end = min(offset + buffer_size, len(encoded))
                end = _find_utf8_safe_boundary(encoded, end)
                fh.write(encoded[offset:end])
                offset = end
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_file(path: str) -> str:
    """Read and return the UTF-8 content of *path*."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")

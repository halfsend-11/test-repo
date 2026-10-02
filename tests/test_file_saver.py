"""Tests for the buffered file saver with UTF-8 multibyte handling.

Covers the boundary conditions described in issue #1805: files larger
than 64KB containing multibyte UTF-8 characters must save without error
and round-trip correctly when reopened.
"""

import os
import tempfile

from src.file_saver import BUFFER_SIZE, save_file


def _roundtrip(content: str) -> str:
    """Save *content* via save_file, read it back, and return the result."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        save_file(content, path)
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    finally:
        os.unlink(path)


class TestSaveFileUTF8Boundaries:
    """Regression tests for the 64KB buffer boundary segfault (#1805)."""

    def test_ascii_over_64kb(self) -> None:
        """ASCII-only content over 64KB saves correctly (baseline)."""
        content = "A" * (BUFFER_SIZE + 1024)
        assert _roundtrip(content) == content

    def test_64kb_trailing_4byte_emoji(self) -> None:
        """64KB file ending with a 4-byte emoji saves correctly."""
        filler = "x" * (BUFFER_SIZE - 1)
        content = filler + "\U0001F600"  # 😀 is 4 bytes in UTF-8
        assert _roundtrip(content) == content

    def test_multibyte_straddling_boundary(self) -> None:
        """4-byte UTF-8 char starting at byte 65534 straddles the boundary."""
        filler = "a" * (BUFFER_SIZE - 2)
        content = filler + "\U0001F600" + "tail"
        assert _roundtrip(content) == content

    def test_65kb_mixed_multibyte(self) -> None:
        """65KB file with multibyte chars around the boundary saves."""
        cjk_block = "世界"  # 6 bytes per pair
        repetitions = (BUFFER_SIZE + 1024) // 6
        content = cjk_block * repetitions
        assert _roundtrip(content) == content

    def test_70kb_mixed_ascii_and_emoji(self) -> None:
        """70KB+ file with mixed ASCII and emoji throughout saves."""
        unit = "hello \U0001F600 world \U0001F680 "
        repetitions = (70 * 1024) // len(unit.encode("utf-8")) + 1
        content = unit * repetitions
        assert len(content.encode("utf-8")) > 70 * 1024
        assert _roundtrip(content) == content

    def test_small_file_ascii(self) -> None:
        """Small ASCII file (under 64KB) still works."""
        content = "small file\n"
        assert _roundtrip(content) == content

    def test_small_file_multibyte(self) -> None:
        """Small file with multibyte chars (under 64KB) still works."""
        content = "café résumé naïve \U0001F389\n"
        assert _roundtrip(content) == content

    def test_empty_file(self) -> None:
        """Empty content saves correctly."""
        assert _roundtrip("") == ""

    def test_exactly_64kb_boundary(self) -> None:
        """Content that is exactly 64KB in encoded bytes."""
        content = "B" * BUFFER_SIZE
        assert _roundtrip(content) == content

    def test_2byte_char_straddling_boundary(self) -> None:
        """2-byte UTF-8 char at the buffer boundary."""
        filler = "a" * (BUFFER_SIZE - 1)
        content = filler + "é" + "after"
        assert _roundtrip(content) == content

    def test_3byte_char_straddling_boundary(self) -> None:
        """3-byte UTF-8 char straddling the buffer boundary."""
        filler = "a" * (BUFFER_SIZE - 1)
        content = filler + "世" + "after"
        assert _roundtrip(content) == content

    def test_128kb_mixed_content(self) -> None:
        """128KB file with mixed content saves correctly."""
        unit = "abc\U0001F600def世界ghi\n"
        byte_len = len(unit.encode("utf-8"))
        repetitions = (128 * 1024) // byte_len + 1
        content = unit * repetitions
        assert len(content.encode("utf-8")) > 128 * 1024
        assert _roundtrip(content) == content

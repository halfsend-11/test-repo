"""Tests for the file writer module.

Covers the boundary conditions around the 64KB buffer with multibyte
UTF-8 characters to verify the segfault reported in issue #1730 is
resolved.
"""

import os
import tempfile

import pytest

from src.file_writer import BUFFER_SIZE, read_file, write_file


@pytest.fixture()
def tmp_path_file(tmp_path):
    """Return a temporary file path inside *tmp_path*."""
    return str(tmp_path / "output.txt")


class TestWriteFileUTF8Boundaries:
    """Verify correct handling at the 64KB buffer boundary."""

    def test_multibyte_utf8_over_64kb(self, tmp_path_file):
        """Multibyte content exceeding 64KB must save without error."""
        # Each emoji is 4 bytes in UTF-8; 18000 emojis = 72KB encoded.
        content = "\U0001f600" * 18000
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_multibyte_utf8_at_64kb_boundary(self, tmp_path_file):
        """Content whose byte length is exactly 64KB."""
        # 4-byte emoji: 16384 emojis = 65536 bytes exactly.
        content = "\U0001f600" * (BUFFER_SIZE // 4)
        assert len(content.encode("utf-8")) == BUFFER_SIZE

        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_multibyte_utf8_just_over_64kb(self, tmp_path_file):
        """Content one character past the 64KB boundary."""
        content = "\U0001f600" * (BUFFER_SIZE // 4 + 1)
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_ascii_over_64kb(self, tmp_path_file):
        """Large ASCII-only content must save correctly (control case)."""
        content = "A" * (BUFFER_SIZE + 1024)
        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_mixed_ascii_and_multibyte_over_64kb(self, tmp_path_file):
        """Mixed ASCII and multibyte characters exceeding 64KB."""
        # Alternate ASCII and emoji to create mixed content > 64KB.
        unit = "Hello \U0001f600 World 世界 "  # mixed ASCII/emoji/CJK
        repeat = (BUFFER_SIZE // len(unit.encode("utf-8"))) + 10
        content = unit * repeat
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_cjk_characters_over_64kb(self, tmp_path_file):
        """CJK characters (3-byte UTF-8) exceeding 64KB."""
        # Each CJK char is 3 bytes; 22000 chars = 66KB.
        content = "世" * 22000
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content


class TestWriteFileGeneral:
    """General write_file behavior."""

    def test_empty_content(self, tmp_path_file):
        """Empty string produces an empty file."""
        write_file(tmp_path_file, "")
        assert read_file(tmp_path_file) == ""

    def test_small_content(self, tmp_path_file):
        """Content well under the buffer size."""
        content = "Hello, world!"
        write_file(tmp_path_file, content)
        assert read_file(tmp_path_file) == content

    def test_creates_parent_directories(self, tmp_path):
        """Missing parent directories are created automatically."""
        path = str(tmp_path / "a" / "b" / "c" / "output.txt")
        write_file(path, "nested")
        assert read_file(path) == "nested"

    def test_rejects_non_string_content(self, tmp_path_file):
        """Passing bytes instead of str raises TypeError."""
        with pytest.raises(TypeError):
            write_file(tmp_path_file, b"bytes")

    def test_overwrites_existing_file(self, tmp_path_file):
        """Writing to an existing file replaces its content."""
        write_file(tmp_path_file, "first")
        write_file(tmp_path_file, "second")
        assert read_file(tmp_path_file) == "second"

"""Tests for the file save module.

Covers the UTF-8 multibyte buffer allocation fix for issue #1359:
segfault when saving files >64KB containing multibyte characters.
"""

import os
import tempfile

import pytest

from src.file_saver import BUFFER_SIZE, calculate_buffer_size, read_file, save_file


class TestCalculateBufferSize:
    """Tests for buffer size calculation based on byte length."""

    def test_empty_content_returns_one_buffer(self):
        assert calculate_buffer_size("") == BUFFER_SIZE

    def test_ascii_under_64kb(self):
        content = "a" * 1000
        assert calculate_buffer_size(content) == BUFFER_SIZE

    def test_ascii_exactly_64kb(self):
        content = "a" * BUFFER_SIZE
        assert calculate_buffer_size(content) == BUFFER_SIZE

    def test_ascii_over_64kb(self):
        content = "a" * (BUFFER_SIZE + 1)
        assert calculate_buffer_size(content) == BUFFER_SIZE * 2

    def test_multibyte_chars_byte_count_exceeds_char_count(self):
        """Multibyte characters: char count < 64K but byte count > 64KB.

        This is the core regression case. Each emoji is 4 bytes in UTF-8,
        so 20000 emoji = 80000 bytes > 64KB, but only 20000 characters.
        The old (buggy) code would allocate based on len(content) = 20000,
        which fits in one 64KB buffer, but the actual byte representation
        needs 80000 bytes.
        """
        # 4-byte emoji: each is 4 bytes in UTF-8
        emoji = "\U0001F600"  # 😀
        content = emoji * 20000  # 80000 bytes, 20000 chars
        byte_len = len(content.encode("utf-8"))
        assert byte_len == 80000
        assert len(content) == 20000
        # Must allocate 2 buffers (128KB) to hold 80000 bytes
        assert calculate_buffer_size(content) == BUFFER_SIZE * 2

    def test_mixed_ascii_and_multibyte_over_64kb(self):
        """Mixed ASCII + multibyte totaling >64KB in bytes."""
        ascii_part = "a" * 50000  # 50000 bytes
        emoji_part = "\U0001F600" * 5000  # 20000 bytes
        content = ascii_part + emoji_part  # 70000 bytes total
        byte_len = len(content.encode("utf-8"))
        assert byte_len == 70000
        assert calculate_buffer_size(content) == BUFFER_SIZE * 2

    def test_exactly_64kb_with_4byte_emoji_at_boundary(self):
        """Exactly 64KB with final character being a 4-byte emoji."""
        # Fill to BUFFER_SIZE - 4 bytes with ASCII, then one 4-byte emoji
        ascii_part = "a" * (BUFFER_SIZE - 4)
        emoji = "\U0001F600"  # 4 bytes
        content = ascii_part + emoji
        byte_len = len(content.encode("utf-8"))
        assert byte_len == BUFFER_SIZE
        assert calculate_buffer_size(content) == BUFFER_SIZE

    def test_2byte_utf8_characters(self):
        """2-byte UTF-8 characters (e.g., accented Latin, Greek)."""
        # ñ is 2 bytes in UTF-8
        content = "ñ" * 40000  # 80000 bytes, 40000 chars
        byte_len = len(content.encode("utf-8"))
        assert byte_len == 80000
        assert calculate_buffer_size(content) == BUFFER_SIZE * 2

    def test_3byte_utf8_characters(self):
        """3-byte UTF-8 characters (CJK characters)."""
        # 中 is 3 bytes in UTF-8
        content = "中" * 25000  # 75000 bytes, 25000 chars
        byte_len = len(content.encode("utf-8"))
        assert byte_len == 75000
        assert calculate_buffer_size(content) == BUFFER_SIZE * 2


class TestSaveFile:
    """Tests for file save with proper UTF-8 handling."""

    def test_save_and_read_ascii(self, tmp_path):
        path = str(tmp_path / "test.txt")
        content = "Hello, World!"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content)
        assert read_file(path) == content

    def test_save_and_read_multibyte_under_64kb(self, tmp_path):
        path = str(tmp_path / "test.txt")
        content = "Hello 😀🎉 World 中文"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert read_file(path) == content

    def test_save_large_file_with_multibyte_over_64kb(self, tmp_path):
        """Core regression test: >64KB with multibyte UTF-8 must not crash."""
        path = str(tmp_path / "large.txt")
        # ~70KB of emoji content (each emoji is 4 bytes)
        content = "\U0001F600" * 18000  # 72000 bytes
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE  # Confirm we're over 64KB

        bytes_written = save_file(path, content)
        assert bytes_written == byte_len
        assert read_file(path) == content

    def test_save_large_ascii_over_64kb(self, tmp_path):
        """Files >64KB with ASCII-only should still work."""
        path = str(tmp_path / "large_ascii.txt")
        content = "a" * 70000
        bytes_written = save_file(path, content)
        assert bytes_written == 70000
        assert read_file(path) == content

    def test_save_mixed_content_over_64kb(self, tmp_path):
        """Mixed ASCII + multibyte totaling >64KB."""
        path = str(tmp_path / "mixed.txt")
        ascii_part = "a" * 50000
        emoji_part = "\U0001F600" * 5000  # 20000 bytes
        content = ascii_part + emoji_part  # 70000 bytes total
        byte_len = len(content.encode("utf-8"))
        assert byte_len == 70000

        bytes_written = save_file(path, content)
        assert bytes_written == byte_len
        assert read_file(path) == content

    def test_save_exactly_64kb_boundary_with_emoji(self, tmp_path):
        """Exactly at the 64KB boundary with a 4-byte emoji at the end."""
        path = str(tmp_path / "boundary.txt")
        content = "a" * (BUFFER_SIZE - 4) + "\U0001F600"
        byte_len = len(content.encode("utf-8"))
        assert byte_len == BUFFER_SIZE

        bytes_written = save_file(path, content)
        assert bytes_written == byte_len
        assert read_file(path) == content

    def test_save_empty_file(self, tmp_path):
        path = str(tmp_path / "empty.txt")
        bytes_written = save_file(path, "")
        assert bytes_written == 0
        assert read_file(path) == ""

    def test_save_cjk_characters_over_64kb(self, tmp_path):
        """CJK characters (3 bytes each) over 64KB."""
        path = str(tmp_path / "cjk.txt")
        content = "中" * 25000  # 75000 bytes
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE

        bytes_written = save_file(path, content)
        assert bytes_written == byte_len
        assert read_file(path) == content

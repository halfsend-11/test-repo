"""Tests for the chunked file writer with UTF-8-aware boundaries.

Covers the segfault scenario from issue #1307: saving files larger than
64KB that contain multibyte UTF-8 characters (emoji, CJK) would crash
because the chunked writer split at fixed byte offsets without respecting
character boundaries.
"""

import os
import tempfile

import pytest

from src.file_writer import (
    DEFAULT_CHUNK_SIZE,
    _find_utf8_safe_split,
    read_file,
    save_file,
)


@pytest.fixture
def tmp_path_file():
    """Provide a temporary file path that is cleaned up after the test."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestFindUtf8SafeSplit:
    """Unit tests for _find_utf8_safe_split."""

    def test_split_at_ascii_boundary(self):
        data = b"Hello, World!"
        assert _find_utf8_safe_split(data, 5) == 5

    def test_split_at_start_of_multibyte_char(self):
        # 'e\xcc\x81' is e + combining accent (2-byte sequence for accent)
        # \xc3\xa9 is 'e' with accent (2-byte UTF-8 char)
        data = b"abc\xc3\xa9def"
        # Offset 3 is the start of \xc3 — valid split point
        assert _find_utf8_safe_split(data, 3) == 3

    def test_split_in_middle_of_2byte_char(self):
        data = b"abc\xc3\xa9def"
        # Offset 4 is \xa9 — continuation byte, should move back to 3
        assert _find_utf8_safe_split(data, 4) == 3

    def test_split_in_middle_of_3byte_char(self):
        # \xe2\x9c\x93 is the check mark character (U+2713)
        data = b"abc\xe2\x9c\x93def"
        # Offset 4 is \x9c — continuation byte
        assert _find_utf8_safe_split(data, 4) == 3
        # Offset 5 is \x93 — continuation byte
        assert _find_utf8_safe_split(data, 5) == 3

    def test_split_in_middle_of_4byte_char(self):
        # \xf0\x9f\x98\x80 is the grinning face emoji (U+1F600)
        data = b"abc\xf0\x9f\x98\x80def"
        # Offsets 4, 5, 6 are continuation bytes
        assert _find_utf8_safe_split(data, 4) == 3
        assert _find_utf8_safe_split(data, 5) == 3
        assert _find_utf8_safe_split(data, 6) == 3

    def test_split_after_complete_char(self):
        data = b"abc\xf0\x9f\x98\x80def"
        # Offset 7 is 'd' — valid split point after the emoji
        assert _find_utf8_safe_split(data, 7) == 7

    def test_split_at_end(self):
        data = b"Hello"
        assert _find_utf8_safe_split(data, 10) == 5

    def test_split_at_zero(self):
        data = b"Hello"
        assert _find_utf8_safe_split(data, 0) == 0


class TestSaveFile:
    """Tests for save_file, focused on the 64KB boundary bug."""

    def test_save_small_ascii_file(self, tmp_path_file):
        content = "Hello, World!"
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_small_file_with_emoji(self, tmp_path_file):
        content = "Hello \U0001f600 World!"
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_large_ascii_file(self, tmp_path_file):
        """Files >64KB with only ASCII should save fine."""
        content = "A" * (DEFAULT_CHUNK_SIZE + 1024)
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_large_file_with_emoji_at_boundary(self, tmp_path_file):
        """Core regression test for issue #1307.

        Generate ~65KB of content where a 4-byte emoji character is
        positioned to straddle the 64KB chunk boundary.
        """
        # Fill with ASCII up to just before the 64KB boundary,
        # then place a 4-byte emoji so it straddles the boundary.
        padding_size = DEFAULT_CHUNK_SIZE - 2  # 2 bytes before boundary
        content = "A" * padding_size + "\U0001f600" + "B" * 1024
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_large_file_with_3byte_char_at_boundary(self, tmp_path_file):
        """3-byte CJK character straddling the 64KB boundary."""
        # U+4E16 (world in Chinese) is 3 bytes: \xe4\xb8\x96
        padding_size = DEFAULT_CHUNK_SIZE - 1
        content = "A" * padding_size + "世" + "B" * 1024
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_large_file_with_2byte_char_at_boundary(self, tmp_path_file):
        """2-byte character straddling the 64KB boundary."""
        # U+00E9 (e accent) is 2 bytes: \xc3\xa9
        padding_size = DEFAULT_CHUNK_SIZE - 1
        content = "A" * padding_size + "é" + "B" * 1024
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_exactly_64kb_ending_mid_character(self, tmp_path_file):
        """Edge case: content is exactly 64KB but last char is multibyte."""
        # Build content where encoded size is exactly 64KB,
        # with the last character being a 4-byte emoji
        padding_size = DEFAULT_CHUNK_SIZE - 4  # leave room for 4-byte emoji
        content = "A" * padding_size + "\U0001f600"
        assert len(content.encode("utf-8")) == DEFAULT_CHUNK_SIZE
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_128kb_with_multibyte_throughout(self, tmp_path_file):
        """Large file (128KB+) with multibyte chars throughout."""
        # Mix of ASCII and emoji throughout
        segment = "Hello \U0001f600 World 世界 "  # 22 chars, 28 bytes
        repeat_count = (DEFAULT_CHUNK_SIZE * 2) // len(segment.encode("utf-8")) + 1
        content = segment * repeat_count
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_mixed_ascii_multibyte_at_boundary(self, tmp_path_file):
        """Mixed ASCII/multibyte content exactly at the boundary."""
        # Place multiple emoji right at the 64KB boundary
        padding_size = DEFAULT_CHUNK_SIZE - 6  # 6 bytes before boundary
        emoji_cluster = "\U0001f600\U0001f601\U0001f602"  # 12 bytes
        content = "A" * padding_size + emoji_cluster + "B" * 1024
        save_file(tmp_path_file, content)
        result = read_file(tmp_path_file)
        assert result == content

    def test_save_returns_byte_count(self, tmp_path_file):
        content = "Hello \U0001f600"
        byte_count = save_file(tmp_path_file, content)
        assert byte_count == len(content.encode("utf-8"))

    def test_save_rejects_non_string(self, tmp_path_file):
        with pytest.raises(TypeError):
            save_file(tmp_path_file, b"bytes are not strings")

    def test_save_empty_string(self, tmp_path_file):
        save_file(tmp_path_file, "")
        result = read_file(tmp_path_file)
        assert result == ""

    def test_roundtrip_integrity_custom_chunk_size(self, tmp_path_file):
        """Verify round-trip integrity with a small chunk size."""
        content = "\U0001f600" * 100  # 400 bytes of 4-byte emoji
        save_file(tmp_path_file, content, chunk_size=7)
        result = read_file(tmp_path_file)
        assert result == content

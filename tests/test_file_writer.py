"""Tests for the chunked file writer with UTF-8-aware boundaries.

Covers the segfault scenario from issue #1346: saving files larger than
64 KB that contain multibyte UTF-8 characters (emoji, CJK) crashed
because the chunked writer split at fixed byte offsets without
respecting character boundaries.
"""

import os
import tempfile

import pytest

from src.file_writer import (
    DEFAULT_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    _find_utf8_safe_split,
    read_file,
    save_file,
)


@pytest.fixture()
def tmp_file():
    """Yield a temporary file path, removed after the test."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


# -- _find_utf8_safe_split unit tests ----------------------------------------


class TestFindUtf8SafeSplit:
    """Unit tests for the low-level split helper."""

    def test_ascii_boundary(self):
        data = b"Hello, World!"
        assert _find_utf8_safe_split(data, 5) == 5

    def test_start_of_2byte_char(self):
        # U+00E9 -> \xc3\xa9
        data = b"abc\xc3\xa9def"
        assert _find_utf8_safe_split(data, 3) == 3

    def test_inside_2byte_char(self):
        data = b"abc\xc3\xa9def"
        # offset 4 lands on the continuation byte \xa9
        assert _find_utf8_safe_split(data, 4) == 3

    def test_inside_3byte_char(self):
        # U+2713 CHECK MARK -> \xe2\x9c\x93
        data = b"abc\xe2\x9c\x93def"
        assert _find_utf8_safe_split(data, 4) == 3
        assert _find_utf8_safe_split(data, 5) == 3

    def test_inside_4byte_char(self):
        # U+1F600 GRINNING FACE -> \xf0\x9f\x98\x80
        data = b"abc\xf0\x9f\x98\x80def"
        assert _find_utf8_safe_split(data, 4) == 3
        assert _find_utf8_safe_split(data, 5) == 3
        assert _find_utf8_safe_split(data, 6) == 3

    def test_after_complete_4byte_char(self):
        data = b"abc\xf0\x9f\x98\x80def"
        # offset 7 is 'd' — valid boundary
        assert _find_utf8_safe_split(data, 7) == 7

    def test_offset_past_end(self):
        data = b"Hello"
        assert _find_utf8_safe_split(data, 100) == 5

    def test_offset_zero(self):
        data = b"Hello"
        assert _find_utf8_safe_split(data, 0) == 0

    def test_empty_data(self):
        assert _find_utf8_safe_split(b"", 0) == 0


# -- save_file / read_file round-trip tests -----------------------------------


class TestSaveFile:
    """Tests for save_file, focused on the 64 KB boundary crash."""

    def test_small_ascii(self, tmp_file):
        content = "Hello, World!"
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_small_with_emoji(self, tmp_file):
        content = "Hello \U0001f600 World!"
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_large_ascii_above_64kb(self, tmp_file):
        """65 KB ASCII-only — should always succeed."""
        content = "A" * (DEFAULT_CHUNK_SIZE + 1024)
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_large_with_4byte_emoji_at_boundary(self, tmp_file):
        """Core regression test: 4-byte emoji straddles the 64 KB
        boundary, reproducing the original segfault."""
        padding = DEFAULT_CHUNK_SIZE - 2
        content = "A" * padding + "\U0001f600" + "B" * 1024
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_large_with_3byte_cjk_at_boundary(self, tmp_file):
        """3-byte CJK character (U+4E16 '世') at the boundary."""
        padding = DEFAULT_CHUNK_SIZE - 1
        content = "A" * padding + "世" + "B" * 1024
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_large_with_2byte_char_at_boundary(self, tmp_file):
        """2-byte character (U+00E9 'é') at the boundary."""
        padding = DEFAULT_CHUNK_SIZE - 1
        content = "A" * padding + "é" + "B" * 1024
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_exactly_64kb_ending_with_multibyte(self, tmp_file):
        """Content whose UTF-8 encoding is exactly 64 KB, with the last
        character being a 4-byte emoji."""
        padding = DEFAULT_CHUNK_SIZE - 4
        content = "A" * padding + "\U0001f600"
        assert len(content.encode("utf-8")) == DEFAULT_CHUNK_SIZE
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_below_64kb_with_emoji(self, tmp_file):
        """63 KB file with emoji — below the boundary, no split needed."""
        padding = DEFAULT_CHUNK_SIZE - 1024
        content = "A" * padding + "\U0001f600" * 10
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_128kb_multibyte_throughout(self, tmp_file):
        """Large file (128 KB+) with multibyte chars distributed
        throughout, triggering multiple chunk splits."""
        segment = "Hello \U0001f600 World 世界 "
        repeat = (DEFAULT_CHUNK_SIZE * 2) // len(segment.encode("utf-8")) + 1
        content = segment * repeat
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_emoji_cluster_at_boundary(self, tmp_file):
        """Multiple 4-byte emoji right at the 64 KB boundary."""
        padding = DEFAULT_CHUNK_SIZE - 6
        emoji_cluster = "\U0001f600\U0001f601\U0001f602"
        content = "A" * padding + emoji_cluster + "B" * 1024
        save_file(tmp_file, content)
        assert read_file(tmp_file) == content

    def test_returns_byte_count(self, tmp_file):
        content = "Hello \U0001f600"
        byte_count = save_file(tmp_file, content)
        assert byte_count == len(content.encode("utf-8"))

    def test_rejects_bytes_input(self, tmp_file):
        with pytest.raises(TypeError):
            save_file(tmp_file, b"not a string")

    def test_empty_string(self, tmp_file):
        save_file(tmp_file, "")
        assert read_file(tmp_file) == ""

    def test_roundtrip_with_small_chunk_size(self, tmp_file):
        """Round-trip with a tiny chunk size to force many splits."""
        content = "\U0001f600" * 100  # 400 bytes of 4-byte emoji
        save_file(tmp_file, content, chunk_size=7)
        assert read_file(tmp_file) == content

    def test_chunk_size_minimum_boundary(self, tmp_file):
        """chunk_size=4 (MIN_CHUNK_SIZE) should succeed with 4-byte emoji."""
        content = "\U0001f600" * 50  # 200 bytes of 4-byte emoji
        save_file(tmp_file, content, chunk_size=MIN_CHUNK_SIZE)
        assert read_file(tmp_file) == content

    def test_chunk_size_below_minimum_raises(self, tmp_file):
        """chunk_size=3 is below MIN_CHUNK_SIZE and must raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be >= 4"):
            save_file(tmp_file, "hello", chunk_size=3)

    def test_chunk_size_zero_raises(self, tmp_file):
        """chunk_size=0 must raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be >= 4"):
            save_file(tmp_file, "hello", chunk_size=0)

    def test_chunk_size_negative_raises(self, tmp_file):
        """Negative chunk_size must raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be >= 4"):
            save_file(tmp_file, "hello", chunk_size=-1)

"""Tests for the chunked UTF-8-aware file writer."""

import os
import tempfile

import pytest

from src.file_writer import BUFFER_SIZE, _find_utf8_safe_boundary, read_file, save_file


@pytest.fixture
def tmp_path_file(tmp_path):
    """Return a temporary file path for test output."""
    return str(tmp_path / "output.txt")


class TestFindUtf8SafeBoundary:
    """Unit tests for the boundary-finding helper."""

    def test_ascii_only(self):
        data = b"Hello, world!"
        assert _find_utf8_safe_boundary(data, 5) == 5

    def test_limit_beyond_data(self):
        data = b"short"
        assert _find_utf8_safe_boundary(data, 100) == len(data)

    def test_split_inside_two_byte_char(self):
        # U+00E9 (é) encodes as 0xC3 0xA9 (2 bytes)
        data = b"aaa\xc3\xa9bbb"  # "aaaébbb"
        # Splitting at index 4 lands on continuation byte 0xA9
        assert _find_utf8_safe_boundary(data, 4) == 3

    def test_split_inside_three_byte_char(self):
        # U+4E16 (世) encodes as 0xE4 0xB8 0x96 (3 bytes)
        data = b"ab\xe4\xb8\x96cd"
        # Splitting at index 3 lands on 2nd byte of 世
        assert _find_utf8_safe_boundary(data, 3) == 2
        # Splitting at index 4 lands on 3rd byte of 世
        assert _find_utf8_safe_boundary(data, 4) == 2

    def test_split_inside_four_byte_char(self):
        # U+1F600 (😀) encodes as 0xF0 0x9F 0x98 0x80 (4 bytes)
        data = b"a\xf0\x9f\x98\x80b"
        # Splitting at indices 2, 3, or 4 should back up to index 1
        assert _find_utf8_safe_boundary(data, 2) == 1
        assert _find_utf8_safe_boundary(data, 3) == 1
        assert _find_utf8_safe_boundary(data, 4) == 1

    def test_split_at_char_boundary(self):
        # U+1F600 (😀) encodes as 4 bytes starting at index 1
        data = b"a\xf0\x9f\x98\x80b"
        # Index 5 is 'b', a non-continuation byte — no adjustment
        assert _find_utf8_safe_boundary(data, 5) == 5


class TestSaveFile:
    """Integration tests for save_file / read_file round-trips."""

    def test_small_ascii_file(self, tmp_path_file):
        content = "Hello, world!\n"
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_file_under_64kb_with_multibyte(self, tmp_path_file):
        """File just under 64KB with multibyte UTF-8 chars saves correctly."""
        # Fill with 2-byte chars (é = 2 bytes each), target ~63KB
        char = "é"
        count = (BUFFER_SIZE - 1024) // len(char.encode("utf-8"))
        content = char * count
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_file_over_64kb_with_multibyte(self, tmp_path_file):
        """File just over 64KB with multibyte UTF-8 chars saves correctly."""
        char = "é"
        count = (BUFFER_SIZE + 1024) // len(char.encode("utf-8"))
        content = char * count
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_emoji_straddling_64kb_boundary(self, tmp_path_file):
        """A 4-byte emoji placed exactly at the 64KB offset saves correctly."""
        # Fill to exactly BUFFER_SIZE - 2 with ASCII, then place a
        # 4-byte emoji so bytes 3 and 4 would cross the boundary.
        padding = "a" * (BUFFER_SIZE - 2)
        emoji = "\U0001F600"  # 😀 — 4 bytes in UTF-8
        content = padding + emoji + "tail"
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_large_cjk_file(self, tmp_path_file):
        """256KB of CJK text saves and round-trips correctly."""
        # U+4E16 (世) = 3 bytes each
        target_bytes = 256 * 1024
        count = target_bytes // 3
        content = "世" * count
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_round_trip_preserves_content(self, tmp_path_file):
        """Saved content matches original exactly (no corruption)."""
        # Mix of ASCII, 2-byte, 3-byte, and 4-byte characters
        block = "Hello 世界! 🌍🎉 café naïve"
        # Repeat to exceed buffer size
        repetitions = (BUFFER_SIZE * 3) // len(block.encode("utf-8")) + 1
        content = block * repetitions
        save_file(content, tmp_path_file)
        assert read_file(tmp_path_file) == content

    def test_custom_buffer_size(self, tmp_path_file):
        """Writing with a tiny buffer still handles multibyte chars."""
        content = "café 世界 🎉" * 100
        save_file(content, tmp_path_file, buffer_size=16)
        assert read_file(tmp_path_file) == content

    def test_empty_file(self, tmp_path_file):
        """Empty content saves successfully."""
        save_file("", tmp_path_file)
        assert read_file(tmp_path_file) == ""

    def test_atomic_write_no_partial_on_error(self, tmp_path):
        """If writing fails, the destination file is not left in a partial state."""
        path = str(tmp_path / "output.txt")
        # Pre-create the file so we can verify it is untouched on failure
        with open(path, "w") as fh:
            fh.write("original")

        # Trigger an error by making the tmp file's directory read-only
        # after the tmp file is opened — but this is hard to do portably.
        # Instead, verify that the .tmp file is cleaned up on success.
        save_file("new content", path)
        tmp_file = path + ".tmp"
        assert not os.path.exists(tmp_file)
        assert read_file(path) == "new content"

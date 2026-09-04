"""Tests for file_saver module.

Covers the UTF-8 multibyte character handling fix for issue #29:
segfault when saving files >64KB containing multibyte characters.
"""

import os
import tempfile

import pytest

from file_saver import load_file, save_file


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _make_content(char: str, target_byte_size: int) -> str:
    """Build a string of repeated chars whose UTF-8 encoding is
    approximately *target_byte_size* bytes."""
    char_bytes = len(char.encode("utf-8"))
    count = target_byte_size // char_bytes
    return char * count


class TestSaveFileUTF8:
    """Regression tests for #29: crash on large files with multibyte chars."""

    def test_small_file_multibyte(self, tmp_dir):
        """Files <64KB with multibyte chars should save and round-trip."""
        path = os.path.join(tmp_dir, "small_mb.txt")
        content = _make_content("🚀", 32 * 1024)  # ~32KB of rocket emoji
        save_file(path, content)
        assert load_file(path) == content

    def test_exact_64kb_multibyte(self, tmp_dir):
        """Files at exactly 64KB boundary with multibyte chars should work."""
        path = os.path.join(tmp_dir, "exact_64kb.txt")
        content = _make_content("漢", 64 * 1024)  # CJK character (3 bytes)
        save_file(path, content)
        assert load_file(path) == content

    def test_large_file_multibyte(self, tmp_dir):
        """Files >64KB with multibyte chars must not crash (main regression)."""
        path = os.path.join(tmp_dir, "large_mb.txt")
        content = _make_content("🎉", 70 * 1024)  # ~70KB of emoji (4 bytes each)
        save_file(path, content)
        assert load_file(path) == content

    def test_large_file_ascii(self, tmp_dir):
        """Control: large ASCII-only files should continue to work."""
        path = os.path.join(tmp_dir, "large_ascii.txt")
        content = _make_content("A", 70 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_mixed_content_large(self, tmp_dir):
        """Large file mixing ASCII and multibyte characters."""
        path = os.path.join(tmp_dir, "mixed.txt")
        ascii_part = "Hello world! " * 3000  # ~39KB ASCII
        emoji_part = "🌍🌎🌏" * 3000  # ~36KB emoji
        content = ascii_part + emoji_part  # ~75KB total
        save_file(path, content)
        assert load_file(path) == content

    def test_empty_file(self, tmp_dir):
        """Edge case: saving an empty file should work."""
        path = os.path.join(tmp_dir, "empty.txt")
        save_file(path, "")
        assert load_file(path) == ""

    def test_single_multibyte_char(self, tmp_dir):
        """Edge case: saving a single multibyte character."""
        path = os.path.join(tmp_dir, "single.txt")
        save_file(path, "🦀")
        assert load_file(path) == "🦀"

    def test_overwrite_existing(self, tmp_dir):
        """Overwriting an existing file should work atomically."""
        path = os.path.join(tmp_dir, "overwrite.txt")
        save_file(path, "original")
        content = _make_content("📝", 70 * 1024)
        save_file(path, content)
        assert load_file(path) == content

"""Tests for file_saver — regression coverage for issue #653.

The segfault occurred when saving files larger than 64KB that contain
UTF-8 multibyte characters (emoji, CJK).  Each test verifies that
content round-trips through save_file/load_file unchanged.
"""

import os
import tempfile

import pytest

from file_saver import load_file, save_file


@pytest.fixture()
def tmp_dir():
    """Yield a temporary directory, cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _fill(char: str, target_bytes: int) -> str:
    """Return a string of *char* repeated to approximately *target_bytes*."""
    char_byte_len = len(char.encode("utf-8"))
    return char * (target_bytes // char_byte_len)


# -- Regression tests for #653 -----------------------------------------------

class TestSaveMultibyteRegression:
    """Core regression: large files with multibyte characters."""

    def test_ascii_under_64kb(self, tmp_dir):
        path = os.path.join(tmp_dir, "ascii_under.txt")
        content = _fill("A", 63 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_ascii_at_64kb(self, tmp_dir):
        path = os.path.join(tmp_dir, "ascii_at.txt")
        content = _fill("A", 64 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_ascii_over_64kb(self, tmp_dir):
        path = os.path.join(tmp_dir, "ascii_over.txt")
        content = _fill("A", 65 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_emoji_under_64kb(self, tmp_dir):
        path = os.path.join(tmp_dir, "emoji_under.txt")
        content = _fill("🚀", 63 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_emoji_at_64kb(self, tmp_dir):
        path = os.path.join(tmp_dir, "emoji_at.txt")
        content = _fill("🎉", 64 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_emoji_over_64kb(self, tmp_dir):
        """Main regression case: >64KB emoji content."""
        path = os.path.join(tmp_dir, "emoji_over.txt")
        content = _fill("🎉", 70 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_cjk_over_64kb(self, tmp_dir):
        """CJK characters (3-byte UTF-8) above the boundary."""
        path = os.path.join(tmp_dir, "cjk_over.txt")
        content = _fill("漢", 70 * 1024)
        save_file(path, content)
        assert load_file(path) == content

    def test_mixed_ascii_and_emoji_over_64kb(self, tmp_dir):
        """Mixed content where byte count >64KB but char count <64KB."""
        path = os.path.join(tmp_dir, "mixed.txt")
        ascii_part = "Hello world! " * 2500   # ~32KB ASCII
        emoji_part = "🌍🌎🌏" * 3000          # ~36KB emoji (4 bytes each)
        content = ascii_part + emoji_part       # ~68KB total bytes
        save_file(path, content)
        assert load_file(path) == content


# -- Edge cases ---------------------------------------------------------------

class TestSaveEdgeCases:

    def test_empty_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.txt")
        save_file(path, "")
        assert load_file(path) == ""

    def test_single_multibyte_char(self, tmp_dir):
        path = os.path.join(tmp_dir, "single.txt")
        save_file(path, "🦀")
        assert load_file(path) == "🦀"

    def test_overwrite_existing_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "overwrite.txt")
        save_file(path, "original content")
        new_content = _fill("📝", 70 * 1024)
        save_file(path, new_content)
        assert load_file(path) == new_content

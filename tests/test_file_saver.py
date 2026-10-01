"""Tests for file_saver module.

Covers UTF-8 multibyte character handling around the 64KB buffer
boundary to verify the buffer overflow fix.
"""

import pytest

from src.file_saver import BUFFER_SIZE, load_file, save_file


def _make_emoji_content(target_bytes):
    """Generate a string of emoji characters that encodes to approximately
    target_bytes in UTF-8. Each emoji is 4 bytes in UTF-8."""
    num_chars = target_bytes // 4
    return "\U0001f600" * num_chars  # 😀


def _make_cjk_content(target_bytes):
    """Generate a string of CJK characters that encodes to approximately
    target_bytes in UTF-8. Each CJK character is 3 bytes in UTF-8."""
    num_chars = target_bytes // 3
    return "世" * num_chars  # 世


def _make_ascii_content(target_bytes):
    """Generate ASCII content of approximately target_bytes."""
    return "A" * target_bytes


class TestSaveFileMultibyteUTF8:
    """Test saving files with multibyte UTF-8 characters around the
    64KB boundary."""

    def test_save_63kb_emoji_content(self, tmp_path):
        """63KB file with emoji content should save successfully."""
        content = _make_emoji_content(63 * 1024)
        path = tmp_path / "63kb_emoji.txt"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert path.exists()

    def test_save_64kb_emoji_content(self, tmp_path):
        """64KB file with emoji content should save successfully."""
        content = _make_emoji_content(64 * 1024)
        path = tmp_path / "64kb_emoji.txt"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert path.exists()

    def test_save_65kb_emoji_content(self, tmp_path):
        """65KB file with emoji content should save successfully.
        This is the exact scenario that triggered the segfault."""
        content = _make_emoji_content(65 * 1024)
        path = tmp_path / "65kb_emoji.txt"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert path.exists()

    def test_save_128kb_cjk_content(self, tmp_path):
        """128KB file with CJK characters should save successfully."""
        content = _make_cjk_content(128 * 1024)
        path = tmp_path / "128kb_cjk.txt"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert path.exists()

    def test_save_65kb_ascii_content(self, tmp_path):
        """65KB ASCII-only file should save successfully
        (regression guard)."""
        content = _make_ascii_content(65 * 1024)
        path = tmp_path / "65kb_ascii.txt"
        bytes_written = save_file(path, content)
        assert bytes_written == len(content.encode("utf-8"))
        assert path.exists()


class TestRoundTrip:
    """Verify that saved content matches input byte-for-byte."""

    def test_roundtrip_emoji_over_64kb(self, tmp_path):
        """Content with emoji over 64KB round-trips correctly."""
        content = _make_emoji_content(70 * 1024)
        path = tmp_path / "roundtrip_emoji.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content

    def test_roundtrip_cjk_over_64kb(self, tmp_path):
        """Content with CJK characters over 64KB round-trips correctly."""
        content = _make_cjk_content(70 * 1024)
        path = tmp_path / "roundtrip_cjk.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content

    def test_roundtrip_ascii_over_64kb(self, tmp_path):
        """ASCII content over 64KB round-trips correctly."""
        content = _make_ascii_content(70 * 1024)
        path = tmp_path / "roundtrip_ascii.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content

    def test_roundtrip_mixed_content(self, tmp_path):
        """Mixed ASCII, emoji, and CJK content round-trips correctly."""
        ascii_part = _make_ascii_content(20 * 1024)
        emoji_part = _make_emoji_content(30 * 1024)
        cjk_part = _make_cjk_content(30 * 1024)
        content = ascii_part + emoji_part + cjk_part
        path = tmp_path / "roundtrip_mixed.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content


class TestBufferBoundary:
    """Test behavior at exact buffer boundary with multibyte chars."""

    def test_content_at_exact_buffer_size_in_bytes(self, tmp_path):
        """Content whose byte length equals BUFFER_SIZE exactly."""
        num_chars = BUFFER_SIZE // 4
        content = "\U0001f600" * num_chars
        encoded = content.encode("utf-8")
        assert len(encoded) == BUFFER_SIZE
        path = tmp_path / "exact_boundary.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content

    def test_content_one_byte_over_buffer(self, tmp_path):
        """Content whose byte length is BUFFER_SIZE + 1."""
        num_chars = BUFFER_SIZE // 4
        # Add one more character to push past the boundary
        content = "\U0001f600" * num_chars + "A"
        encoded = content.encode("utf-8")
        assert len(encoded) == BUFFER_SIZE + 1
        path = tmp_path / "one_over_boundary.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content

    def test_char_count_under_64k_but_bytes_over(self, tmp_path):
        """Character count < 64K but byte count > 64K.
        This is the core bug scenario: if buffer is allocated by
        character count, it would be too small."""
        # 20000 emoji = 20000 chars but 80000 bytes (> 64KB)
        content = "\U0001f600" * 20000
        char_count = len(content)
        byte_count = len(content.encode("utf-8"))
        assert char_count < BUFFER_SIZE
        assert byte_count > BUFFER_SIZE
        path = tmp_path / "chars_under_bytes_over.txt"
        save_file(path, content)
        loaded = load_file(path)
        assert loaded == content


class TestEdgeCases:
    """Test edge cases for save_file."""

    def test_empty_content(self, tmp_path):
        """Empty string should save successfully."""
        path = tmp_path / "empty.txt"
        bytes_written = save_file(path, "")
        assert bytes_written == 0
        assert path.exists()
        assert load_file(path) == ""

    def test_single_emoji(self, tmp_path):
        """Single emoji character should save successfully."""
        path = tmp_path / "single_emoji.txt"
        bytes_written = save_file(path, "\U0001f600")
        assert bytes_written == 4
        loaded = load_file(path)
        assert loaded == "\U0001f600"

    def test_invalid_content_type(self, tmp_path):
        """Non-string content should raise TypeError."""
        path = tmp_path / "invalid.txt"
        with pytest.raises(TypeError):
            save_file(path, b"bytes content")

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        path = tmp_path / "nested" / "dir" / "file.txt"
        save_file(path, "hello")
        assert path.exists()
        assert load_file(path) == "hello"

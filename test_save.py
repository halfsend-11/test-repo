"""Tests for file save module with UTF-8 multibyte character handling.

Covers the bug reported in issue #1500: segfault when saving files >64KB
containing multibyte UTF-8 characters due to buffer size being calculated
from character count instead of byte count.
"""

import os
import tempfile
import unittest

from save import BUFFER_SIZE, _calculate_buffer_size, load_file, save_file


class TestCalculateBufferSize(unittest.TestCase):
    """Tests for buffer size calculation."""

    def test_empty_string(self):
        self.assertEqual(_calculate_buffer_size(""), BUFFER_SIZE)

    def test_ascii_under_buffer(self):
        content = "a" * 100
        self.assertEqual(_calculate_buffer_size(content), BUFFER_SIZE)

    def test_ascii_at_buffer_boundary(self):
        content = "a" * BUFFER_SIZE
        self.assertEqual(_calculate_buffer_size(content), BUFFER_SIZE)

    def test_ascii_over_buffer(self):
        content = "a" * (BUFFER_SIZE + 1)
        self.assertEqual(_calculate_buffer_size(content), BUFFER_SIZE * 2)

    def test_multibyte_char_count_under_but_bytes_over(self):
        """Key regression test: char count < 64K but byte count > 64K.

        Each emoji is 4 bytes in UTF-8. 20000 emoji = 20000 chars but
        80000 bytes, which exceeds the 64KB (65536 byte) buffer.
        """
        # 20000 emoji characters = 80000 bytes > 64KB
        content = "\U0001F600" * 20000
        char_count = len(content)
        byte_count = len(content.encode("utf-8"))

        self.assertLess(char_count, BUFFER_SIZE)
        self.assertGreater(byte_count, BUFFER_SIZE)

        buffer_size = _calculate_buffer_size(content)
        self.assertGreaterEqual(buffer_size, byte_count)

    def test_cjk_characters(self):
        """CJK characters are 3 bytes each in UTF-8."""
        # 25000 CJK chars = 75000 bytes > 64KB
        content = "世" * 25000
        byte_count = len(content.encode("utf-8"))
        self.assertGreater(byte_count, BUFFER_SIZE)

        buffer_size = _calculate_buffer_size(content)
        self.assertGreaterEqual(buffer_size, byte_count)

    def test_two_byte_characters(self):
        """Two-byte UTF-8 characters (e.g., accented Latin)."""
        # 40000 two-byte chars = 80000 bytes > 64KB
        content = "é" * 40000
        byte_count = len(content.encode("utf-8"))
        self.assertGreater(byte_count, BUFFER_SIZE)

        buffer_size = _calculate_buffer_size(content)
        self.assertGreaterEqual(buffer_size, byte_count)


class TestSaveFile(unittest.TestCase):
    """Tests for save_file function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _filepath(self, name="test.txt"):
        return os.path.join(self.tmpdir, name)

    def test_save_ascii_under_64kb(self):
        """ASCII file under 64KB saves successfully."""
        content = "Hello, world!\n" * 1000
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, len(content.encode("utf-8")))
        self.assertEqual(load_file(filepath), content)

    def test_save_ascii_over_64kb(self):
        """ASCII file over 64KB saves successfully."""
        content = "a" * (65 * 1024)
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, len(content.encode("utf-8")))
        self.assertEqual(load_file(filepath), content)

    def test_save_emoji_over_64kb(self):
        """File with emoji characters exceeding 64KB saves successfully.

        This is the primary regression test for issue #1500.
        """
        # 20000 emoji (4 bytes each) = 80000 bytes > 64KB
        content = "\U0001F600" * 20000
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, 80000)
        self.assertEqual(load_file(filepath), content)

    def test_save_cjk_over_64kb(self):
        """File with CJK characters exceeding 64KB saves successfully."""
        # CJK chars (3 bytes each), enough to exceed 64KB
        content = "世界你好" * 6000  # 24000 chars = 72000 bytes
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, len(content.encode("utf-8")))
        self.assertEqual(load_file(filepath), content)

    def test_save_multibyte_under_64kb(self):
        """Multibyte file under 64KB saves successfully (boundary)."""
        # 15000 emoji = 60000 bytes < 64KB
        content = "\U0001F600" * 15000
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, 60000)
        self.assertEqual(load_file(filepath), content)

    def test_save_multibyte_exactly_64kb(self):
        """File with multibyte chars at exactly 64KB boundary."""
        # 16384 emoji (4 bytes each) = 65536 bytes = exactly 64KB
        content = "\U0001F600" * 16384
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, BUFFER_SIZE)
        self.assertEqual(load_file(filepath), content)

    def test_save_128kb_multibyte(self):
        """Large file (128KB) with multibyte UTF-8 saves successfully."""
        # 32768 emoji (4 bytes each) = 131072 bytes = 128KB
        content = "\U0001F600" * 32768
        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, 131072)
        self.assertEqual(load_file(filepath), content)

    def test_roundtrip_mixed_content(self):
        """Round-trip: saved content matches original exactly."""
        content = "Hello \U0001F600 World 世界 éèê\n" * 5000
        filepath = self._filepath()
        save_file(filepath, content)
        loaded = load_file(filepath)
        self.assertEqual(loaded, content)

    def test_save_empty_string(self):
        """Empty string saves successfully."""
        filepath = self._filepath()
        bytes_written = save_file(filepath, "")
        self.assertEqual(bytes_written, 0)
        self.assertEqual(load_file(filepath), "")

    def test_save_none_raises(self):
        """Saving None raises ValueError."""
        filepath = self._filepath()
        with self.assertRaises(ValueError):
            save_file(filepath, None)

    def test_save_creates_directories(self):
        """Save creates parent directories if they don't exist."""
        filepath = os.path.join(self.tmpdir, "subdir", "test.txt")
        save_file(filepath, "hello")
        self.assertEqual(load_file(filepath), "hello")
        # Clean up
        os.unlink(filepath)
        os.rmdir(os.path.join(self.tmpdir, "subdir"))

    def test_char_count_less_than_64k_byte_count_greater(self):
        """Key test: char count < 64K but byte count > 64K.

        This is the exact scenario that caused the segfault in v2.3.1.
        """
        # 20000 4-byte emoji: 20000 chars < 65536, but 80000 bytes > 65536
        content = "\U0001F600" * 20000
        self.assertLess(len(content), BUFFER_SIZE)
        self.assertGreater(len(content.encode("utf-8")), BUFFER_SIZE)

        filepath = self._filepath()
        bytes_written = save_file(filepath, content)
        self.assertEqual(bytes_written, 80000)
        self.assertEqual(load_file(filepath), content)


if __name__ == "__main__":
    unittest.main()

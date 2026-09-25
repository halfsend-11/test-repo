"""Tests for the UTF-8 file save buffer fix.

Covers the five scenarios identified in the triage:
1. ASCII-only file >64 KB saves successfully (baseline).
2. UTF-8 multibyte file exactly at the 64 KB boundary saves.
3. UTF-8 multibyte file ~70 KB saves (the crashing case).
4. Mixed file where char count < 64 K but byte count > 64 KB saves.
5. Round-trip integrity: saved file contents match the original.
"""

import os
import tempfile

from src.file_saver import BUFFER_SIZE, _allocate_buffer, save_file


class TestAllocateBuffer:
    """Unit tests for _allocate_buffer."""

    def test_ascii_under_buffer_size(self):
        content = "a" * 100
        buf = _allocate_buffer(content)
        assert len(buf) >= BUFFER_SIZE

    def test_ascii_over_buffer_size(self):
        content = "a" * (BUFFER_SIZE + 1)
        buf = _allocate_buffer(content)
        assert len(buf) >= BUFFER_SIZE + 1

    def test_multibyte_over_buffer_size(self):
        """Emoji are 4 bytes each in UTF-8.

        16385 emoji × 4 bytes = 65540 bytes, which exceeds the 64 KB
        buffer.  The old code used len(text) == 16385 < 65536 and
        allocated only 64 KB, causing the overflow.
        """
        content = "\U0001f600" * (BUFFER_SIZE // 4 + 1)
        encoded_len = len(content.encode("utf-8"))
        buf = _allocate_buffer(content)
        assert len(buf) >= encoded_len


class TestSaveFile:
    """Integration tests for save_file."""

    def test_ascii_large_file(self):
        """Scenario 1: ASCII-only file >64 KB."""
        content = "A" * (BUFFER_SIZE + 1024)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            written = save_file(path, content)
            assert written == len(content)
            with open(path, "rb") as fh:
                assert fh.read() == content.encode("utf-8")
        finally:
            os.unlink(path)

    def test_utf8_at_boundary(self):
        """Scenario 2: UTF-8 multibyte file exactly at 64 KB boundary."""
        # 3-byte CJK characters: fill exactly BUFFER_SIZE bytes
        chars_needed = BUFFER_SIZE // 3
        content = "世" * chars_needed  # 世
        encoded = content.encode("utf-8")
        assert len(encoded) == chars_needed * 3

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            written = save_file(path, content)
            assert written == len(encoded)
            with open(path, "rb") as fh:
                assert fh.read() == encoded
        finally:
            os.unlink(path)

    def test_utf8_large_file(self):
        """Scenario 3: UTF-8 multibyte file ~70 KB (previously crashed)."""
        # 4-byte emoji: 17500 × 4 = 70000 bytes
        content = "\U0001f600" * 17500
        encoded = content.encode("utf-8")
        assert len(encoded) == 70000

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            written = save_file(path, content)
            assert written == 70000
            with open(path, "rb") as fh:
                assert fh.read() == encoded
        finally:
            os.unlink(path)

    def test_mixed_char_count_below_byte_count_above(self):
        """Scenario 4: char count < 64 K but byte count > 64 KB.

        Use 4-byte emoji so that 16384 characters = 65536 bytes, right
        at the boundary.  Add one more to push byte count past it while
        char count stays well below 64 K.
        """
        content = "\U0001f600" * (BUFFER_SIZE // 4 + 1)
        encoded = content.encode("utf-8")
        assert len(content) < BUFFER_SIZE
        assert len(encoded) > BUFFER_SIZE

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            written = save_file(path, content)
            assert written == len(encoded)
            with open(path, "rb") as fh:
                assert fh.read() == encoded
        finally:
            os.unlink(path)

    def test_round_trip_integrity(self):
        """Scenario 5: saved file contents match original."""
        content = "Hello \U0001f30d世界! " * 5000
        encoded = content.encode("utf-8")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            save_file(path, content)
            with open(path, "rb") as fh:
                data = fh.read()
            assert data == encoded
            assert data.decode("utf-8") == content
        finally:
            os.unlink(path)

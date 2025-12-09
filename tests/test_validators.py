"""
Tests for the validators module.
Run with: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators import (
    validate_file_extension,
    validate_file_content,
    generate_safe_filename,
    sanitize_event_id,
    validate_token
)


class TestValidateFileExtension:
    """Tests for validate_file_extension function."""
    
    def test_valid_jpg(self):
        valid, ext = validate_file_extension("photo.jpg")
        assert valid is True
        assert ext == ".jpg"
    
    def test_valid_jpeg(self):
        valid, ext = validate_file_extension("photo.jpeg")
        assert valid is True
        assert ext == ".jpeg"
    
    def test_valid_png(self):
        valid, ext = validate_file_extension("image.png")
        assert valid is True
        assert ext == ".png"
    
    def test_valid_heic(self):
        valid, ext = validate_file_extension("IMG_001.HEIC")
        assert valid is True
        assert ext == ".heic"
    
    def test_invalid_extension(self):
        valid, ext = validate_file_extension("document.pdf")
        assert valid is False
        assert ext == ".pdf"
    
    def test_no_extension(self):
        valid, ext = validate_file_extension("filename")
        assert valid is False
        assert ext == ""
    
    def test_empty_filename(self):
        valid, ext = validate_file_extension("")
        assert valid is False


class TestValidateFileContent:
    """Tests for validate_file_content function."""
    
    def test_empty_content(self):
        result = validate_file_content(b"", "test.jpg")
        assert result.valid is False
        assert "Empty" in result.error
    
    def test_invalid_extension(self):
        result = validate_file_content(b"some content", "test.pdf")
        assert result.valid is False
        assert "extension" in result.error.lower()
    
    def test_valid_jpeg_magic_bytes(self):
        # JPEG magic bytes
        jpeg_content = b"\xff\xd8\xff" + b"\x00" * 100
        result = validate_file_content(jpeg_content, "test.jpg")
        assert result.valid is True
        assert result.detected_mime == "image/jpeg"
    
    def test_valid_png_magic_bytes(self):
        # PNG magic bytes
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = validate_file_content(png_content, "test.png")
        assert result.valid is True
        assert result.detected_mime == "image/png"


class TestGenerateSafeFilename:
    """Tests for generate_safe_filename function."""
    
    def test_preserves_extension(self):
        filename = generate_safe_filename("photo.jpg")
        assert filename.endswith(".jpg")
    
    def test_preserves_extension_case_insensitive(self):
        filename = generate_safe_filename("photo.JPG")
        assert filename.endswith(".jpg")
    
    def test_unique_filenames(self):
        filename1 = generate_safe_filename("photo.jpg")
        filename2 = generate_safe_filename("photo.jpg")
        assert filename1 != filename2
    
    def test_contains_timestamp(self):
        filename = generate_safe_filename("photo.jpg")
        # Should contain date pattern YYYYMMDD
        import re
        assert re.search(r"\d{8}_\d{6}", filename)
    
    def test_with_prefix(self):
        filename = generate_safe_filename("photo.jpg", prefix="event123")
        assert filename.startswith("event123_")


class TestSanitizeEventId:
    """Tests for sanitize_event_id function."""
    
    def test_valid_event_id(self):
        assert sanitize_event_id("boda-2024") == "boda-2024"
    
    def test_with_underscores(self):
        assert sanitize_event_id("my_event_123") == "my_event_123"
    
    def test_removes_special_chars(self):
        result = sanitize_event_id("event/../../../etc")
        assert "/" not in result
        assert ".." not in result
    
    def test_empty_returns_default(self):
        assert sanitize_event_id("") == "default"
    
    def test_only_special_chars_returns_default(self):
        assert sanitize_event_id("!@#$%") == "default"
    
    def test_truncates_long_ids(self):
        long_id = "a" * 100
        result = sanitize_event_id(long_id)
        assert len(result) <= 50


class TestValidateToken:
    """Tests for validate_token function."""
    
    def test_empty_token(self):
        assert validate_token("") is False
        assert validate_token(None) is False
    
    def test_wrong_token(self):
        assert validate_token("wrong_token") is False
    
    # Note: Correct token test requires setting up config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
EventFolio - File Validation Module
Robust validation for uploaded files including MIME type detection.
"""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass

from config import settings

logger = logging.getLogger("eventfolio.validators")

# MIME type mapping for allowed image types
ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/heic": [".heic"],
    "image/heif": [".heif", ".heic"],
}

# Magic bytes for common image formats
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",           # JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",        # PNG
    b"ftypheic": "image/heic",                # HEIC (offset 4)
    b"ftypmif1": "image/heif",                # HEIF
    b"ftypheix": "image/heic",                # HEIC variant
}


@dataclass
class ValidationResult:
    """Result of file validation."""
    valid: bool
    error: Optional[str] = None
    detected_mime: Optional[str] = None
    file_size: int = 0


def detect_mime_type(content: bytes) -> Optional[str]:
    """
    Detect MIME type from file content using magic bytes.
    Falls back to python-magic if available.
    """
    # Check magic bytes
    for magic, mime in MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime
    
    # Special case for HEIC/HEIF (magic bytes at offset 4)
    if len(content) > 12:
        ftyp = content[4:12]
        for magic, mime in MAGIC_BYTES.items():
            if ftyp.startswith(magic):
                return mime
    
    # Try python-magic if available
    try:
        import magic
        mime = magic.from_buffer(content, mime=True)
        return mime
    except ImportError:
        logger.debug("python-magic not available, using basic detection")
    except Exception as e:
        logger.warning(f"Magic detection failed: {e}")
    
    return None


def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """
    Validate file extension.
    Returns (is_valid, extension_lowercase).
    """
    if not filename:
        return False, ""
    
    ext = Path(filename).suffix.lower()
    is_valid = ext in settings.ALLOWED_EXTENSIONS
    
    return is_valid, ext


def validate_file_content(content: bytes, filename: str) -> ValidationResult:
    """
    Comprehensive file validation:
    1. Check file size
    2. Validate extension
    3. Detect and verify MIME type
    """
    # Check empty file
    if not content or len(content) == 0:
        return ValidationResult(
            valid=False,
            error="Empty file",
            file_size=0
        )
    
    file_size = len(content)
    
    # Check file size
    if file_size > settings.MAX_FILE_SIZE_BYTES:
        return ValidationResult(
            valid=False,
            error=f"File too large ({file_size / 1024 / 1024:.1f} MB). Maximum: {settings.MAX_FILE_SIZE_MB} MB",
            file_size=file_size
        )
    
    # Validate extension
    ext_valid, ext = validate_file_extension(filename)
    if not ext_valid:
        return ValidationResult(
            valid=False,
            error=f"Invalid extension '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            file_size=file_size
        )
    
    # Detect MIME type
    detected_mime = detect_mime_type(content)
    
    if detected_mime:
        # Verify MIME type matches extension
        if detected_mime in ALLOWED_MIME_TYPES:
            allowed_exts = ALLOWED_MIME_TYPES[detected_mime]
            if ext not in allowed_exts:
                logger.warning(
                    f"MIME mismatch: {filename} has extension {ext} but detected as {detected_mime}"
                )
                # Allow if MIME type is valid (more permissive)
        elif detected_mime.startswith("image/"):
            # Unknown image type but still an image
            logger.info(f"Unknown image MIME type: {detected_mime} for {filename}")
        else:
            return ValidationResult(
                valid=False,
                error=f"File is not a valid image (detected: {detected_mime})",
                detected_mime=detected_mime,
                file_size=file_size
            )
    
    return ValidationResult(
        valid=True,
        detected_mime=detected_mime,
        file_size=file_size
    )


def normalize_name(name: str) -> str:
    """
    Normalize a person's name for use in filenames.
    
    - Converts to lowercase
    - Replaces spaces with hyphens
    - Removes accents/diacritics
    - Removes special characters
    
    Args:
        name: Person's name as entered (e.g., "Ana López García")
    
    Returns:
        Normalized name (e.g., "ana-lopez-garcia")
    """
    import unicodedata
    
    if not name:
        return ""
    
    # Convert to lowercase
    name = name.lower().strip()
    
    # Remove accents/diacritics (normalize to NFD, then remove combining characters)
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    
    # Replace spaces with hyphens
    name = name.replace(' ', '-')
    
    # Keep only alphanumeric and hyphens
    name = ''.join(c for c in name if c.isalnum() or c == '-')
    
    # Remove multiple consecutive hyphens
    while '--' in name:
        name = name.replace('--', '-')
    
    # Remove leading/trailing hyphens
    name = name.strip('-')
    
    # Limit length
    return name[:30]


def generate_safe_filename(original_filename: str, uploader_name: str = "") -> str:
    """
    Generate a safe, unique filename.
    
    Format: [uploader-name_]YYYYMMDD_HHMMSS_<uuid8>.<ext>
    
    Args:
        original_filename: Original filename to extract extension from
        uploader_name: Name of the person uploading (will be normalized)
    
    Returns:
        Safe filename string
    
    Examples:
        - "Ana López" + "foto.jpg" -> "ana-lopez_20241209_120000_abc123.jpg"
        - "" + "foto.jpg" -> "20241209_120000_abc123.jpg"
    """
    ext = Path(original_filename).suffix.lower()
    
    # Ensure extension is valid
    if ext not in settings.ALLOWED_EXTENSIONS:
        ext = ".jpg"  # Default fallback
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    
    # Normalize uploader name if provided
    if uploader_name:
        normalized_name = normalize_name(uploader_name)
        if normalized_name:
            return f"{normalized_name}_{timestamp}_{unique_id}{ext}"
    
    return f"{timestamp}_{unique_id}{ext}"


def sanitize_event_id(event_id: str) -> str:
    """
    Sanitize event ID to prevent path traversal and invalid characters.
    
    Args:
        event_id: Raw event ID from user input
    
    Returns:
        Safe event ID string
    """
    if not event_id:
        return "default"
    
    # Remove any path separators and special characters
    safe_id = "".join(c for c in event_id if c.isalnum() or c in "-_")
    
    # Limit length
    safe_id = safe_id[:50]
    
    # Ensure not empty after sanitization
    if not safe_id:
        return "default"
    
    return safe_id


def validate_token(token: Optional[str]) -> bool:
    """
    Validate the upload authentication token.
    
    Args:
        token: Token from request
    
    Returns:
        True if token is valid
    """
    if not token:
        return False
    
    # Constant-time comparison to prevent timing attacks
    expected = settings.UPLOAD_TOKEN
    if len(token) != len(expected):
        return False
    
    result = 0
    for a, b in zip(token.encode(), expected.encode()):
        result |= a ^ b
    
    return result == 0

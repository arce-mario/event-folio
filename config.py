"""
EventFolio Configuration Module
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if exists
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # FTP Configuration
    FTP_HOST: str = os.getenv("FTP_HOST", "10.0.0.2")
    FTP_PORT: int = int(os.getenv("FTP_PORT", "21"))
    FTP_USER: str = os.getenv("FTP_USER", "eventuploader")
    FTP_PASSWORD: str = os.getenv("FTP_PASSWORD", "")
    FTP_REMOTE_DIR: str = os.getenv("FTP_REMOTE_DIR", "/srv/event_photos/incoming/")
    FTP_TIMEOUT: int = int(os.getenv("FTP_TIMEOUT", "30"))
    
    # Local Storage
    LOCAL_UPLOAD_DIR: Path = Path(os.getenv("LOCAL_UPLOAD_DIR", "./uploads"))
    
    # Security
    UPLOAD_TOKEN: str = os.getenv("UPLOAD_TOKEN", "default_insecure_token")
    
    # Upload Limits
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
    MAX_FILES_PER_REQUEST: int = int(os.getenv("MAX_FILES_PER_REQUEST", "20"))
    
    # Allowed extensions (lowercase)
    ALLOWED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
    
    # Retry Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_INTERVAL_MINUTES: int = int(os.getenv("RETRY_INTERVAL_MINUTES", "5"))
    
    # Cleanup: delete local file after successful FTP transfer
    DELETE_AFTER_FTP: bool = os.getenv("DELETE_AFTER_FTP", "true").lower() == "true"
    
    # Concurrency: max simultaneous upload requests being processed
    MAX_CONCURRENT_UPLOADS: int = int(os.getenv("MAX_CONCURRENT_UPLOADS", "3"))
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Jobs file for pending FTP transfers
    JOBS_FILE: Path = LOCAL_UPLOAD_DIR / "pending_jobs.json"
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_event_dir(cls, event_id: str) -> Path:
        """Get the upload directory for a specific event."""
        import os
        # Sanitize event_id to prevent path traversal
        safe_event_id = "".join(c for c in event_id if c.isalnum() or c in "-_")
        if not safe_event_id:
            safe_event_id = "default"
        event_dir = cls.LOCAL_UPLOAD_DIR / safe_event_id
        event_dir.mkdir(parents=True, exist_ok=True)
        # Ensure directory has write permissions for all users
        os.chmod(event_dir, 0o777)
        return event_dir


# Global settings instance
settings = Settings()

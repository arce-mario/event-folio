"""
EventFolio - FTP Client Module
Handles FTP connections and file transfers using Python's ftplib.
"""

import ftplib
import logging
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

from config import settings

logger = logging.getLogger("eventfolio.ftp")


@dataclass
class FTPTransferResult:
    """Result of an FTP transfer operation."""
    success: bool
    filename: str
    remote_path: str
    error: Optional[str] = None
    bytes_transferred: int = 0


class FTPClient:
    """
    FTP client for transferring files to the remote server.
    Uses ftplib from Python standard library.
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        remote_dir: str = None,
        timeout: int = None
    ):
        """
        Initialize FTP client with connection parameters.
        Falls back to settings if parameters not provided.
        """
        self.host = host or settings.FTP_HOST
        self.port = port or settings.FTP_PORT
        self.username = username or settings.FTP_USER
        self.password = password or settings.FTP_PASSWORD
        self.remote_dir = remote_dir or settings.FTP_REMOTE_DIR
        self.timeout = timeout or settings.FTP_TIMEOUT
        self._ftp: Optional[ftplib.FTP] = None
    
    @contextmanager
    def connection(self):
        """
        Context manager for FTP connection.
        Ensures proper connection and disconnection.
        
        Usage:
            with ftp_client.connection() as ftp:
                ftp.nlst()
        """
        try:
            self._connect()
            yield self._ftp
        finally:
            self._disconnect()
    
    def _connect(self) -> None:
        """Establish FTP connection and login."""
        try:
            logger.info(f"Connecting to FTP server {self.host}:{self.port}")
            
            self._ftp = ftplib.FTP()
            self._ftp.connect(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            # Login
            if self.username:
                self._ftp.login(user=self.username, passwd=self.password)
                logger.info(f"Logged in as {self.username}")
            else:
                self._ftp.login()  # Anonymous login
                logger.info("Logged in anonymously")
            
            # Set binary mode
            self._ftp.voidcmd("TYPE I")
            
            logger.info(f"FTP connection established: {self._ftp.getwelcome()}")
            
        except ftplib.all_errors as e:
            logger.error(f"FTP connection failed: {e}")
            self._ftp = None
            raise ConnectionError(f"Failed to connect to FTP server: {e}")
    
    def _disconnect(self) -> None:
        """Close FTP connection gracefully."""
        if self._ftp:
            try:
                self._ftp.quit()
                logger.info("FTP connection closed")
            except ftplib.all_errors:
                try:
                    self._ftp.close()
                except:
                    pass
            finally:
                self._ftp = None
    
    def _ensure_remote_directory(self, remote_dir: str) -> None:
        """
        Ensure remote directory exists, creating it if necessary.
        Handles nested directories.
        """
        if not self._ftp:
            raise ConnectionError("Not connected to FTP server")
        
        # Normalize path
        remote_dir = remote_dir.rstrip("/")
        if not remote_dir:
            return
        
        # Split into components
        parts = remote_dir.split("/")
        current_path = ""
        
        for part in parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}"
            
            try:
                self._ftp.cwd(current_path)
            except ftplib.error_perm:
                # Directory doesn't exist, create it
                try:
                    self._ftp.mkd(current_path)
                    logger.info(f"Created remote directory: {current_path}")
                except ftplib.error_perm as e:
                    # Might already exist (race condition) or permission denied
                    if "exists" not in str(e).lower():
                        logger.warning(f"Could not create directory {current_path}: {e}")
        
        # Return to root
        self._ftp.cwd("/")
    
    def upload_file(
        self,
        local_path: Path,
        event_id: str = "default",
        remote_filename: str = None
    ) -> FTPTransferResult:
        """
        Upload a single file to the FTP server.
        
        Args:
            local_path: Path to the local file
            event_id: Event identifier for organizing files
            remote_filename: Optional custom filename on remote server
        
        Returns:
            FTPTransferResult with success status and details
        """
        local_path = Path(local_path)
        
        if not local_path.exists():
            return FTPTransferResult(
                success=False,
                filename=local_path.name,
                remote_path="",
                error=f"Local file not found: {local_path}"
            )
        
        # Determine remote path
        remote_dir = f"{self.remote_dir.rstrip('/')}/{event_id}"
        remote_filename = remote_filename or local_path.name
        remote_path = f"{remote_dir}/{remote_filename}"
        
        try:
            with self.connection() as ftp:
                # Ensure directory exists
                self._ensure_remote_directory(remote_dir)
                
                # Change to target directory
                ftp.cwd(remote_dir)
                
                # Upload file
                file_size = local_path.stat().st_size
                
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {remote_filename}", f)
                
                logger.info(f"Uploaded {local_path.name} ({file_size} bytes) to {remote_path}")
                
                return FTPTransferResult(
                    success=True,
                    filename=local_path.name,
                    remote_path=remote_path,
                    bytes_transferred=file_size
                )
                
        except ftplib.all_errors as e:
            error_msg = f"FTP transfer failed: {e}"
            logger.error(error_msg)
            return FTPTransferResult(
                success=False,
                filename=local_path.name,
                remote_path=remote_path,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Unexpected error during FTP transfer: {e}"
            logger.error(error_msg)
            return FTPTransferResult(
                success=False,
                filename=local_path.name,
                remote_path=remote_path,
                error=error_msg
            )
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test FTP connection without transferring files.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.connection() as ftp:
                # Try to list root directory
                ftp.nlst()
                return True, f"Connected to {self.host}:{self.port}"
        except Exception as e:
            return False, f"Connection failed: {e}"


# Global FTP client instance
ftp_client = FTPClient()


def upload_to_ftp(local_path: Path, event_id: str) -> FTPTransferResult:
    """
    Convenience function to upload a file to FTP.
    
    Args:
        local_path: Path to the local file
        event_id: Event identifier
    
    Returns:
        FTPTransferResult
    """
    return ftp_client.upload_file(local_path, event_id)


def test_ftp_connection() -> Tuple[bool, str]:
    """
    Test FTP connection.
    
    Returns:
        Tuple of (success, message)
    """
    return ftp_client.test_connection()

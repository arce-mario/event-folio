"""
EventFolio - Main FastAPI Application
Photo upload service with FTP transfer for events.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from validators import (
    validate_token,
    validate_file_content,
    generate_safe_filename,
    sanitize_event_id
)
from tasks import (
    queue_ftp_transfer,
    get_transfer_stats,
    start_scheduler,
    stop_scheduler
)
from ftp_client import test_ftp_connection

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("eventfolio")

# Initialize FastAPI app
app = FastAPI(
    title="EventFolio",
    description="Photo upload service for events with FTP transfer",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Ensure upload directory exists on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    settings.ensure_directories()
    logger.info(f"EventFolio started. Upload dir: {settings.LOCAL_UPLOAD_DIR}")
    logger.info(f"FTP target: {settings.FTP_HOST}:{settings.FTP_PORT}")
    
    # Start the FTP transfer scheduler
    start_scheduler()
    logger.info("FTP transfer scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    stop_scheduler()
    logger.info("EventFolio shutdown complete")


# =============================================================================
# Health Check Endpoint
# =============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify the backend is running.
    Returns basic system status.
    """
    # Get transfer queue stats
    transfer_stats = get_transfer_stats()
    
    # Test FTP connection
    ftp_ok, ftp_msg = test_ftp_connection()
    
    return {
        "status": "healthy",
        "service": "EventFolio",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "max_files_per_request": settings.MAX_FILES_PER_REQUEST,
            "allowed_extensions": list(settings.ALLOWED_EXTENSIONS),
            "ftp_host": settings.FTP_HOST,
            "upload_dir": str(settings.LOCAL_UPLOAD_DIR)
        },
        "ftp": {
            "connected": ftp_ok,
            "message": ftp_msg
        },
        "transfer_queue": transfer_stats
    }


# Validation functions imported from validators.py


# =============================================================================
# Upload Endpoint
# =============================================================================

@app.post("/upload", tags=["Upload"])
async def upload_photos(
    files: List[UploadFile] = File(..., description="Image files to upload"),
    event_id: str = Form(default="default", description="Event identifier"),
    uploader_name: str = Form(default="Anónimo", description="Name of the person uploading"),
    token: str = Query(..., description="Authentication token")
):
    """
    Upload one or more photos for an event.
    
    - **files**: Image files (jpg, jpeg, png, heic)
    - **event_id**: Event identifier for organizing photos
    - **uploader_name**: Name of the person uploading the photos
    - **token**: Authentication token (required)
    
    Files are saved locally and queued for FTP transfer.
    """
    
    # Validate token
    if not validate_token(token):
        logger.warning(f"Invalid token attempt from upload request")
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    
    # Validate file count
    if len(files) > settings.MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {settings.MAX_FILES_PER_REQUEST} files per request."
        )
    
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Sanitize event_id and get directory
    safe_event_id = sanitize_event_id(event_id)
    event_dir = settings.get_event_dir(safe_event_id)
    
    # Process each file
    results = []
    errors = []
    
    for upload_file in files:
        original_name = upload_file.filename or "unknown"
        
        # Read file content
        content = await upload_file.read()
        
        # Comprehensive validation (size, extension, MIME type)
        validation = validate_file_content(content, original_name)
        
        if not validation.valid:
            errors.append({
                "filename": original_name,
                "error": validation.error
            })
            continue
        
        # Generate safe filename (includes normalized uploader name) and save
        safe_filename = generate_safe_filename(original_name, uploader_name)
        destination = event_dir / safe_filename
        
        try:
            with open(destination, "wb") as f:
                f.write(content)
            
            logger.info(
                f"Saved: {safe_filename} ({validation.file_size} bytes) "
                f"[MIME: {validation.detected_mime}] by '{uploader_name}' to {event_dir}"
            )
            
            # Queue for FTP transfer
            job = queue_ftp_transfer(
                local_path=destination,
                event_id=safe_event_id,
                original_filename=original_name,
                immediate=True  # Try to transfer immediately
            )
            
            results.append({
                "original_name": original_name,
                "saved_as": safe_filename,
                "size_bytes": validation.file_size,
                "mime_type": validation.detected_mime,
                "event_id": safe_event_id,
                "uploader_name": uploader_name,
                "path": str(destination),
                "ftp_job_id": job.job_id,
                "ftp_status": job.status
            })
            
        except Exception as e:
            logger.error(f"Failed to save {original_name}: {e}")
            errors.append({
                "filename": original_name,
                "error": f"Failed to save file: {str(e)}"
            })
    
    # Build response
    response = {
        "success": len(results) > 0,
        "uploaded": len(results),
        "failed": len(errors),
        "event_id": event_id,
        "uploader_name": uploader_name,
        "files": results
    }
    
    if errors:
        response["errors"] = errors
    
    status_code = 200 if len(results) > 0 else 400
    return JSONResponse(content=response, status_code=status_code)


# =============================================================================
# Admin Endpoints (Queue Management)
# =============================================================================

@app.get("/admin/queue", tags=["Admin"])
async def get_queue_status(token: str = Query(..., description="Authentication token")):
    """
    Get the current status of the FTP transfer queue.
    Requires authentication token.
    """
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    
    from tasks import transfer_scheduler
    
    stats = get_transfer_stats()
    jobs = transfer_scheduler.queue.get_all_jobs()
    
    return {
        "stats": stats,
        "jobs": [
            {
                "job_id": job.job_id,
                "filename": job.original_filename,
                "event_id": job.event_id,
                "status": job.status,
                "retry_count": job.retry_count,
                "created_at": job.created_at,
                "last_attempt": job.last_attempt,
                "error": job.error_message
            }
            for job in jobs
        ]
    }


@app.post("/admin/retry", tags=["Admin"])
async def retry_failed_jobs(token: str = Query(..., description="Authentication token")):
    """
    Manually trigger retry of all failed jobs.
    Requires authentication token.
    """
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    
    from tasks import transfer_scheduler
    
    count = transfer_scheduler.retry_failed_jobs()
    
    return {
        "success": True,
        "message": f"Queued {count} failed jobs for retry"
    }


@app.get("/admin/ftp-test", tags=["Admin"])
async def test_ftp(token: str = Query(..., description="Authentication token")):
    """
    Test FTP connection.
    Requires authentication token.
    """
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    
    success, message = test_ftp_connection()
    
    return {
        "success": success,
        "message": message,
        "ftp_host": settings.FTP_HOST,
        "ftp_port": settings.FTP_PORT
    }


# =============================================================================
# Frontend Page
# =============================================================================

@app.get("/event/{event_id}", response_class=HTMLResponse, tags=["Frontend"])
async def upload_page_with_event(
    request: Request,
    event_id: str,
    token: str = Query(default="", description="Authentication token")
):
    """
    Serve the upload page for a specific event.
    URL format: /event/{event_id}/?token=xxx
    Example: /event/boda-2024/?token=dev_token_123
    """
    # Sanitize event_id
    safe_event_id = sanitize_event_id(event_id)
    
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "token": token,
            "event_id": safe_event_id,
            "max_files": settings.MAX_FILES_PER_REQUEST,
            "max_size_mb": settings.MAX_FILE_SIZE_MB,
            "allowed_extensions": ", ".join(settings.ALLOWED_EXTENSIONS)
        }
    )


@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def upload_page_default(
    request: Request,
    token: str = Query(default="", description="Authentication token")
):
    """
    Serve the upload page without event (redirects to default).
    For backwards compatibility.
    """
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "token": token,
            "event_id": "default",
            "max_files": settings.MAX_FILES_PER_REQUEST,
            "max_size_mb": settings.MAX_FILE_SIZE_MB,
            "allowed_extensions": ", ".join(settings.ALLOWED_EXTENSIONS)
        }
    )


# =============================================================================
# Run with Uvicorn (for development)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

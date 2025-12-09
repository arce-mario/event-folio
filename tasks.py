"""
EventFolio - Task Queue and Retry System
Manages pending FTP transfers with automatic retries using APScheduler.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from ftp_client import upload_to_ftp, FTPTransferResult

logger = logging.getLogger("eventfolio.tasks")


class JobStatus(str, Enum):
    """Status of a transfer job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_PERMANENT = "failed_permanent"


@dataclass
class TransferJob:
    """Represents a pending FTP transfer job."""
    job_id: str
    local_path: str
    event_id: str
    original_filename: str
    status: str = JobStatus.PENDING
    retry_count: int = 0
    created_at: str = ""
    last_attempt: str = ""
    error_message: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TransferJob":
        return cls(**data)


class JobQueue:
    """
    Persistent job queue for FTP transfers.
    Jobs are stored in a JSON file for persistence across restarts.
    """
    
    def __init__(self, jobs_file: Path = None):
        self.jobs_file = jobs_file or settings.JOBS_FILE
        self._jobs: dict[str, TransferJob] = {}
        self._lock = threading.Lock()
        self._load_jobs()
    
    def _load_jobs(self) -> None:
        """Load jobs from persistent storage."""
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file, "r") as f:
                    data = json.load(f)
                    self._jobs = {
                        k: TransferJob.from_dict(v) 
                        for k, v in data.items()
                    }
                logger.info(f"Loaded {len(self._jobs)} jobs from {self.jobs_file}")
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")
                self._jobs = {}
        else:
            self._jobs = {}
    
    def _save_jobs(self) -> None:
        """Save jobs to persistent storage."""
        try:
            # Ensure directory exists
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.jobs_file, "w") as f:
                data = {k: v.to_dict() for k, v in self._jobs.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")
    
    def add_job(self, job: TransferJob) -> None:
        """Add a new job to the queue."""
        with self._lock:
            self._jobs[job.job_id] = job
            self._save_jobs()
            logger.info(f"Added job {job.job_id} for {job.original_filename}")
    
    def get_job(self, job_id: str) -> Optional[TransferJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def update_job(self, job: TransferJob) -> None:
        """Update an existing job."""
        with self._lock:
            self._jobs[job.job_id] = job
            self._save_jobs()
    
    def remove_job(self, job_id: str) -> None:
        """Remove a job from the queue."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self._save_jobs()
                logger.info(f"Removed job {job_id}")
    
    def get_pending_jobs(self) -> List[TransferJob]:
        """Get all pending jobs that need processing."""
        return [
            job for job in self._jobs.values()
            if job.status in (JobStatus.PENDING, JobStatus.FAILED)
        ]
    
    def get_all_jobs(self) -> List[TransferJob]:
        """Get all jobs."""
        return list(self._jobs.values())
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "failed_permanent": 0
        }
        
        for job in self._jobs.values():
            if job.status in stats:
                stats[job.status] += 1
        
        return stats


class TransferScheduler:
    """
    Scheduler for automatic FTP transfer retries.
    Uses APScheduler for background job processing.
    """
    
    def __init__(self, job_queue: JobQueue = None):
        self.queue = job_queue or JobQueue()
        self.scheduler = BackgroundScheduler()
        self._is_running = False
    
    def start(self) -> None:
        """Start the scheduler."""
        if self._is_running:
            return
        
        # Add retry job
        self.scheduler.add_job(
            self._process_pending_jobs,
            trigger=IntervalTrigger(minutes=settings.RETRY_INTERVAL_MINUTES),
            id="ftp_retry_job",
            name="FTP Transfer Retry",
            replace_existing=True
        )
        
        self.scheduler.start()
        self._is_running = True
        logger.info(
            f"Transfer scheduler started. "
            f"Retry interval: {settings.RETRY_INTERVAL_MINUTES} minutes"
        )
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Transfer scheduler stopped")
    
    def _process_pending_jobs(self) -> None:
        """Process all pending jobs."""
        pending = self.queue.get_pending_jobs()
        
        if not pending:
            logger.debug("No pending jobs to process")
            return
        
        logger.info(f"Processing {len(pending)} pending jobs")
        
        for job in pending:
            self._process_job(job)
    
    def _process_job(self, job: TransferJob) -> None:
        """Process a single job."""
        # Check if max retries exceeded
        if job.retry_count >= settings.MAX_RETRIES:
            job.status = JobStatus.FAILED_PERMANENT
            job.error_message = f"Max retries ({settings.MAX_RETRIES}) exceeded"
            self.queue.update_job(job)
            logger.warning(f"Job {job.job_id} marked as permanently failed")
            return
        
        # Check if file still exists
        local_path = Path(job.local_path)
        if not local_path.exists():
            job.status = JobStatus.FAILED_PERMANENT
            job.error_message = "Local file no longer exists"
            self.queue.update_job(job)
            logger.warning(f"Job {job.job_id}: local file missing")
            return
        
        # Update job status
        job.status = JobStatus.IN_PROGRESS
        job.last_attempt = datetime.utcnow().isoformat()
        self.queue.update_job(job)
        
        # Attempt transfer
        logger.info(f"Attempting FTP transfer for job {job.job_id} (attempt {job.retry_count + 1})")
        
        result = upload_to_ftp(local_path, job.event_id)
        
        if result.success:
            job.status = JobStatus.COMPLETED
            job.error_message = ""
            self.queue.update_job(job)
            logger.info(f"Job {job.job_id} completed successfully")
            
            # Optionally remove completed jobs after some time
            # self.queue.remove_job(job.job_id)
        else:
            job.status = JobStatus.FAILED
            job.retry_count += 1
            job.error_message = result.error or "Unknown error"
            self.queue.update_job(job)
            logger.warning(
                f"Job {job.job_id} failed (attempt {job.retry_count}): {result.error}"
            )
    
    def queue_transfer(
        self,
        local_path: Path,
        event_id: str,
        original_filename: str,
        immediate: bool = True
    ) -> TransferJob:
        """
        Queue a file for FTP transfer.
        
        Args:
            local_path: Path to the local file
            event_id: Event identifier
            original_filename: Original filename from upload
            immediate: If True, attempt transfer immediately
        
        Returns:
            TransferJob instance
        """
        import uuid
        
        job = TransferJob(
            job_id=str(uuid.uuid4()),
            local_path=str(local_path),
            event_id=event_id,
            original_filename=original_filename
        )
        
        self.queue.add_job(job)
        
        if immediate:
            # Try immediate transfer in background
            self._process_job(job)
        
        return job
    
    def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        return self.queue.get_stats()
    
    def retry_failed_jobs(self) -> int:
        """
        Manually trigger retry of failed jobs.
        Returns number of jobs queued for retry.
        """
        failed_jobs = [
            job for job in self.queue.get_all_jobs()
            if job.status == JobStatus.FAILED
        ]
        
        for job in failed_jobs:
            job.status = JobStatus.PENDING
            self.queue.update_job(job)
        
        logger.info(f"Queued {len(failed_jobs)} failed jobs for retry")
        return len(failed_jobs)


# Global scheduler instance
transfer_scheduler = TransferScheduler()


def queue_ftp_transfer(
    local_path: Path,
    event_id: str,
    original_filename: str,
    immediate: bool = True
) -> TransferJob:
    """
    Convenience function to queue a file for FTP transfer.
    
    Args:
        local_path: Path to the local file
        event_id: Event identifier
        original_filename: Original filename from upload
        immediate: If True, attempt transfer immediately
    
    Returns:
        TransferJob instance
    """
    return transfer_scheduler.queue_transfer(
        local_path, event_id, original_filename, immediate
    )


def get_transfer_stats() -> dict:
    """Get transfer queue statistics."""
    return transfer_scheduler.get_queue_stats()


def start_scheduler() -> None:
    """Start the transfer scheduler."""
    transfer_scheduler.start()


def stop_scheduler() -> None:
    """Stop the transfer scheduler."""
    transfer_scheduler.stop()

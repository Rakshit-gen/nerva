"""
File storage service for uploading files to S3 or local filesystem.
"""
import os
from typing import Optional
from pathlib import Path

from app.core.config import settings


class StorageService:
    """Service for storing files locally or in S3."""
    
    def __init__(self):
        """Initialize storage service."""
        self.storage_type = settings.STORAGE_TYPE.lower()
        self._s3_client = None
        
        if self.storage_type == "s3":
            self._init_s3()
    
    def _init_s3(self):
        """Initialize S3 client."""
        try:
            import boto3
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.S3_REGION,
            )
        except ImportError:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize S3 client: {e}")
    
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: Optional[str] = None,
        public: bool = True,
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            local_path: Path to local file
            remote_path: Path in storage (e.g., "episodes/{episode_id}/audio.mp3")
            content_type: MIME type (e.g., "audio/mpeg")
            public: Whether file should be publicly accessible
            
        Returns:
            URL to access the file
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        if self.storage_type == "s3":
            return self._upload_to_s3(local_path, remote_path, content_type, public)
        else:
            # Local storage - just return the path
            return f"/api/v1/export/{remote_path}"
    
    def _upload_to_s3(
        self,
        local_path: str,
        remote_path: str,
        content_type: Optional[str] = None,
        public: bool = True,
    ) -> str:
        """Upload file to S3."""
        if not self._s3_client:
            raise RuntimeError("S3 client not initialized")
        
        if not settings.S3_BUCKET_NAME:
            raise RuntimeError("S3_BUCKET_NAME not configured")
        
        # Upload to S3
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        if public:
            extra_args['ACL'] = 'public-read'
        
        try:
            self._s3_client.upload_file(
                local_path,
                settings.S3_BUCKET_NAME,
                remote_path,
                ExtraArgs=extra_args if extra_args else None,
            )
            
            # Return public URL
            # Format: https://{bucket}.s3.{region}.amazonaws.com/{key}
            url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com/{remote_path}"
            return url
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload to S3: {e}")
    
    def delete_file(self, remote_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            remote_path: Path in storage
            
        Returns:
            True if deleted, False otherwise
        """
        if self.storage_type == "s3":
            return self._delete_from_s3(remote_path)
        else:
            # Local storage - delete local file
            local_path = os.path.join(settings.OUTPUT_DIR, remote_path)
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                    return True
            except Exception:
                pass
            return False
    
    def _delete_from_s3(self, remote_path: str) -> bool:
        """Delete file from S3."""
        if not self._s3_client or not settings.S3_BUCKET_NAME:
            return False
        
        try:
            self._s3_client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=remote_path,
            )
            return True
        except Exception:
            return False
    
    def file_exists(self, remote_path: str) -> bool:
        """Check if file exists in storage."""
        if self.storage_type == "s3":
            return self._s3_file_exists(remote_path)
        else:
            local_path = os.path.join(settings.OUTPUT_DIR, remote_path)
            return os.path.exists(local_path)
    
    def _s3_file_exists(self, remote_path: str) -> bool:
        """Check if file exists in S3."""
        if not self._s3_client or not settings.S3_BUCKET_NAME:
            return False
        
        try:
            self._s3_client.head_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=remote_path,
            )
            return True
        except Exception:
            return False


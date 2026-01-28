"""
Document Storage Service - Abstraction layer for local and S3 storage.

Provides a unified interface for document storage operations that can
switch between local filesystem and AWS S3 based on configuration.

For AWS deployment, set DOCUMENT_STORAGE_MODE=s3 and configure:
- AWS_S3_BUCKET: S3 bucket name for documents
- AWS_REGION: AWS region (default: us-east-1)
- AWS credentials via IAM role (preferred) or environment variables
"""

import os
import logging
from datetime import datetime
from typing import Optional, Tuple, BinaryIO
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save(self, file_data: bytes, key: str) -> str:
        """Save file and return the storage path/URL."""
        pass
    
    @abstractmethod
    def load(self, key: str) -> Optional[bytes]:
        """Load file data by key."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete file by key."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    def get_url(self, key: str, expiry_seconds: int = 3600) -> Optional[str]:
        """Get a URL to access the file (presigned for S3)."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: str = 'uploads'):
        self.base_path = base_path
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the base directory exists."""
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
    
    def _get_full_path(self, key: str) -> str:
        """Get full filesystem path for a key."""
        return os.path.join(self.base_path, key)
    
    def save(self, file_data: bytes, key: str) -> str:
        """Save file to local filesystem."""
        self._ensure_directory()
        full_path = self._get_full_path(key)
        
        dir_path = os.path.dirname(full_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(file_data)
        
        logger.info(f"Saved file to local storage: {key}")
        return full_path
    
    def load(self, key: str) -> Optional[bytes]:
        """Load file from local filesystem."""
        full_path = self._get_full_path(key)
        if not os.path.exists(full_path):
            return None
        
        with open(full_path, 'rb') as f:
            return f.read()
    
    def delete(self, key: str) -> bool:
        """Delete file from local filesystem."""
        full_path = self._get_full_path(key)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Deleted file from local storage: {key}")
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if file exists in local filesystem."""
        return os.path.exists(self._get_full_path(key))
    
    def get_url(self, key: str, expiry_seconds: int = 3600) -> Optional[str]:
        """Local storage returns the file path as URL."""
        if self.exists(key):
            return self._get_full_path(key)
        return None


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""
    
    def __init__(self, bucket_name: str, region: str = 'us-east-1', prefix: str = 'documents'):
        self.bucket_name = bucket_name
        self.region = region
        self.prefix = prefix
        self._client = None
    
    @property
    def client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('s3', region_name=self.region)
            except ImportError:
                raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        return self._client
    
    def _get_s3_key(self, key: str) -> str:
        """Get full S3 key with prefix."""
        if self.prefix:
            return f"{self.prefix}/{key}"
        return key
    
    def save(self, file_data: bytes, key: str) -> str:
        """Save file to S3."""
        s3_key = self._get_s3_key(key)
        
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=file_data,
            ServerSideEncryption='AES256'
        )
        
        logger.info(f"Saved file to S3: s3://{self.bucket_name}/{s3_key}")
        return f"s3://{self.bucket_name}/{s3_key}"
    
    def load(self, key: str) -> Optional[bytes]:
        """Load file from S3."""
        try:
            s3_key = self._get_s3_key(key)
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return response['Body'].read()
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.error(f"Error loading from S3: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete file from S3."""
        try:
            s3_key = self._get_s3_key(key)
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted file from S3: s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            s3_key = self._get_s3_key(key)
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except:
            return False
    
    def get_url(self, key: str, expiry_seconds: int = 3600) -> Optional[str]:
        """Get presigned URL for S3 object."""
        try:
            s3_key = self._get_s3_key(key)
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiry_seconds
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None


class DocumentStorage:
    """
    Main document storage interface.
    
    Usage:
        storage = DocumentStorage.get_instance()
        path = storage.save(file_bytes, 'patient_123/doc.pdf')
        data = storage.load('patient_123/doc.pdf')
    """
    
    _instance = None
    
    def __init__(self):
        self.backend = self._create_backend()
    
    @classmethod
    def get_instance(cls) -> 'DocumentStorage':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
    
    def _create_backend(self) -> StorageBackend:
        """Create appropriate backend based on configuration."""
        storage_mode = os.environ.get('DOCUMENT_STORAGE_MODE', 'local').lower()
        
        if storage_mode == 's3':
            bucket = os.environ.get('AWS_S3_BUCKET')
            if not bucket:
                raise ValueError("AWS_S3_BUCKET environment variable required for S3 storage mode")
            
            region = os.environ.get('AWS_REGION', 'us-east-1')
            prefix = os.environ.get('AWS_S3_PREFIX', 'documents')
            
            logger.info(f"Using S3 storage backend: {bucket}/{prefix}")
            return S3StorageBackend(bucket, region, prefix)
        else:
            upload_folder = os.environ.get('UPLOAD_FOLDER', 'uploads')
            logger.info(f"Using local storage backend: {upload_folder}")
            return LocalStorageBackend(upload_folder)
    
    def save(self, file_data: bytes, key: str) -> str:
        """Save file and return storage path/URL."""
        return self.backend.save(file_data, key)
    
    def save_file(self, file_obj: BinaryIO, key: str) -> str:
        """Save file from file object."""
        return self.backend.save(file_obj.read(), key)
    
    def load(self, key: str) -> Optional[bytes]:
        """Load file by key."""
        return self.backend.load(key)
    
    def delete(self, key: str) -> bool:
        """Delete file by key."""
        return self.backend.delete(key)
    
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return self.backend.exists(key)
    
    def get_url(self, key: str, expiry_seconds: int = 3600) -> Optional[str]:
        """Get URL to access file."""
        return self.backend.get_url(key, expiry_seconds)
    
    def generate_key(self, patient_id: int, filename: str) -> str:
        """Generate a storage key for a document."""
        from werkzeug.utils import secure_filename
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(filename)
        return f"patient_{patient_id}/{timestamp}_{safe_filename}"
    
    @property
    def is_s3(self) -> bool:
        """Check if using S3 backend."""
        return isinstance(self.backend, S3StorageBackend)
    
    @property
    def is_local(self) -> bool:
        """Check if using local backend."""
        return isinstance(self.backend, LocalStorageBackend)

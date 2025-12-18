"""
Secure file deletion utilities for HIPAA compliance.

This module provides secure deletion of files containing PHI by:
1. Overwriting file contents with random data (multiple passes)
2. Truncating the file to zero bytes
3. Unlinking (deleting) the file

This ensures that PHI cannot be recovered from disk after deletion.
"""

import os
import logging
import secrets
import tempfile
import shutil
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

OVERWRITE_PASSES = 3
BLOCK_SIZE = 65536


def _get_hash_salt() -> str:
    """Get a secret salt for HIPAA-compliant path hashing.
    
    Uses SESSION_SECRET for cryptographically strong salting.
    Without a proper secret, hashes could be vulnerable to rainbow table attacks.
    
    HIPAA REQUIREMENT: SESSION_SECRET must be set in production for proper
    PHI protection. The salt prevents rainbow table attacks on predictable
    path prefixes like /tmp/healthprep_.
    """
    import os
    salt = os.environ.get('SESSION_SECRET', '')
    if not salt:
        # Generate a random runtime salt - different per process restart
        # This is less ideal than SESSION_SECRET but still provides protection
        import secrets as sec_module
        if not hasattr(_get_hash_salt, '_runtime_salt'):
            _get_hash_salt._runtime_salt = sec_module.token_hex(32)
            logger.warning("SESSION_SECRET not set - using random runtime salt for PHI logging. Set SESSION_SECRET for consistent HIPAA-compliant hashing.")
        salt = _get_hash_salt._runtime_salt
    return salt


def hash_path_for_log(file_path: str) -> str:
    """Hash file/directory path for PHI-safe logging.
    
    HIPAA COMPLIANCE: Paths may contain patient names in filenames or directory
    names, so we hash the entire path with a secret salt to prevent PHI leakage.
    
    The salt prevents rainbow table attacks on predictable path prefixes like
    /tmp/healthprep_. Without salting, an attacker could pre-compute hashes of
    common patient names to reverse the hash.
    
    This is the canonical hashing function for all path logging in the application.
    Import and use this function from utils.secure_delete for consistency.
    
    Args:
        file_path: File or directory path (may contain PHI in any component)
    
    Returns:
        Hashed path identifier like "[path_abc123def456]"
    """
    import hashlib
    if not file_path:
        return "[no-path]"
    
    # Use salted hash to prevent rainbow table reconstruction
    salt = _get_hash_salt()
    salted_path = f"{salt}:{file_path}"
    path_hash = hashlib.sha256(salted_path.encode()).hexdigest()[:16]
    return f"[path_{path_hash}]"




def secure_delete_file(file_path: str, passes: int = OVERWRITE_PASSES) -> bool:
    """Securely delete a file by overwriting with random data before unlinking.
    
    HIPAA COMPLIANCE: All log messages use hashed file paths to prevent
    PHI leakage through filenames that may contain patient names.
    
    Args:
        file_path: Path to the file to delete
        passes: Number of overwrite passes (default 3 for HIPAA compliance)
    
    Returns:
        True if file was successfully deleted, False otherwise
    """
    if not file_path or not os.path.exists(file_path):
        logger.debug(f"File does not exist, skipping secure delete: {hash_path_for_log(file_path)}")
        return False
    
    hashed_path = hash_path_for_log(file_path)
    
    try:
        file_size = os.path.getsize(file_path)
        
        if file_size > 0:
            for pass_num in range(passes):
                with open(file_path, 'r+b') as f:
                    bytes_written = 0
                    while bytes_written < file_size:
                        chunk_size = min(BLOCK_SIZE, file_size - bytes_written)
                        f.write(secrets.token_bytes(chunk_size))
                        bytes_written += chunk_size
                    f.flush()
                    os.fsync(f.fileno())
        
        with open(file_path, 'w') as f:
            f.truncate(0)
            f.flush()
            os.fsync(f.fileno())
        
        os.unlink(file_path)
        
        # Use hashed path to prevent PHI leakage
        logger.info(f"Securely deleted file: {hashed_path} ({file_size} bytes, {passes} passes)")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied during secure delete of {hashed_path}: {e}")
        return False
    except OSError as e:
        logger.error(f"OS error during secure delete of {hashed_path}: {e}")
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.warning(f"Fallback deletion (non-secure) for {hashed_path}")
                return True
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"Unexpected error during secure delete of {hashed_path}: {e}")
        return False


def secure_delete_directory(dir_path: str, passes: int = OVERWRITE_PASSES) -> tuple[int, int]:
    """Securely delete all files in a directory and the directory itself.
    
    HIPAA COMPLIANCE: All log messages use hashed paths to prevent
    PHI leakage through directory names that may contain patient identifiers.
    
    Args:
        dir_path: Path to the directory to delete
        passes: Number of overwrite passes per file
    
    Returns:
        Tuple of (files_deleted, files_failed)
    """
    if not dir_path or not os.path.exists(dir_path):
        return (0, 0)
    
    # Hash directory path for PHI-safe logging
    hashed_dir = hash_path_for_log(dir_path)
    
    files_deleted = 0
    files_failed = 0
    
    try:
        for root, dirs, files in os.walk(dir_path, topdown=False):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if secure_delete_file(file_path, passes):
                    files_deleted += 1
                else:
                    files_failed += 1
            
            for dir_name in dirs:
                subdir_path = os.path.join(root, dir_name)
                try:
                    os.rmdir(subdir_path)
                except OSError:
                    pass
        
        try:
            os.rmdir(dir_path)
        except OSError:
            pass
        
        # Use hashed path to prevent PHI leakage
        logger.info(f"Securely deleted directory: {hashed_dir} ({files_deleted} files, {files_failed} failed)")
        
    except Exception as e:
        logger.error(f"Error during secure directory deletion of {hashed_dir}: {e}")
    
    return (files_deleted, files_failed)


@contextmanager
def secure_temp_directory(prefix: str = "healthprep_", suffix: str = ""):
    """Context manager for a temporary directory with secure cleanup.
    
    Usage:
        with secure_temp_directory() as temp_dir:
            # Use temp_dir for processing
            # Files are securely deleted on exit
    
    Args:
        prefix: Prefix for the temporary directory name
        suffix: Suffix for the temporary directory name
    
    Yields:
        Path to the temporary directory
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix, suffix=suffix)
    
    try:
        yield temp_dir
    finally:
        secure_delete_directory(temp_dir)


@contextmanager
def secure_temp_file(suffix: str = "", prefix: str = "healthprep_", dir: str = None):
    """Context manager for a temporary file with secure cleanup.
    
    Usage:
        with secure_temp_file(suffix='.pdf') as temp_path:
            # Write to temp_path
            # File is securely deleted on exit
    
    Args:
        suffix: File extension/suffix
        prefix: Prefix for the filename
        dir: Directory for the temp file (uses system temp if None)
    
    Yields:
        Path to the temporary file
    """
    fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
    os.close(fd)
    
    try:
        yield temp_path
    finally:
        secure_delete_file(temp_path)


def _hash_filename(filename: str) -> str:
    """Create a PHI-safe hash of a filename for audit logging.
    
    Filenames may contain patient names or other PHI, so we hash them
    before storing in audit logs.
    """
    import hashlib
    if not filename:
        return "[no-file]"
    return f"file_{hashlib.sha256(filename.encode()).hexdigest()[:16]}"


def audit_log_deletion(file_path: str, file_type: str, patient_id: int = None, 
                       org_id: int = None, user_id: int = None) -> None:
    """Log file deletion for HIPAA audit trail.
    
    This creates an audit record of PHI-containing file disposal.
    IMPORTANT: File paths are hashed before logging to prevent PHI leakage
    through filenames that may contain patient names.
    
    Args:
        file_path: Path of the deleted file (will be hashed for PHI safety)
        file_type: Type of file (e.g., 'uploaded_document', 'temp_ocr', 'fhir_binary')
        patient_id: Associated patient ID if applicable
        org_id: Organization ID
        user_id: User who initiated deletion (None for system-initiated)
    """
    try:
        from app import db
        from models import AdminLog
        import json
        
        # Hash the filename to prevent PHI leakage - filenames may contain patient names
        filename_hash = _hash_filename(os.path.basename(file_path))
        
        details = {
            'file_hash': filename_hash,  # Hashed for PHI safety
            'file_type': file_type,
            'deletion_timestamp': datetime.utcnow().isoformat(),
            'secure_deletion': True,
            'overwrite_passes': OVERWRITE_PASSES
        }
        
        audit_entry = AdminLog(
            org_id=org_id or 0,
            user_id=user_id,
            event_type='secure_file_deletion',
            resource_type='document',
            resource_id=patient_id,
            action_details=json.dumps(details),
            ip_address=None
        )
        db.session.add(audit_entry)
        db.session.commit()
        
    except Exception as e:
        logger.warning(f"Failed to create audit log for file deletion: {e}")


class SecureFileManager:
    """Manager for secure file operations with HIPAA compliance."""
    
    def __init__(self, base_upload_dir: str = None):
        self.base_upload_dir = base_upload_dir or os.path.join(os.getcwd(), 'uploads')
        self.logger = logging.getLogger(__name__)
    
    def get_file_path(self, filename: str, org_id: int = None) -> str:
        """Get the full path for a file in the uploads directory."""
        if org_id:
            return os.path.join(self.base_upload_dir, str(org_id), filename)
        return os.path.join(self.base_upload_dir, filename)
    
    def delete_document_file(self, document) -> bool:
        """Securely delete the file associated with a Document model instance.
        
        Args:
            document: Document model instance with file_path attribute
        
        Returns:
            True if deletion was successful
        """
        if not document or not document.file_path:
            return False
        
        file_path = document.file_path
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.base_upload_dir, file_path)
        
        success = secure_delete_file(file_path)
        
        if success:
            audit_log_deletion(
                file_path=file_path,
                file_type='uploaded_document',
                patient_id=getattr(document, 'patient_id', None),
                org_id=getattr(document, 'org_id', None)
            )
            
            document.file_path = None
            document.file_disposed = True
            document.file_disposed_at = datetime.utcnow()
            
            try:
                from app import db
                db.session.commit()
            except Exception as e:
                self.logger.error(f"Failed to update document after file deletion: {e}")
        
        return success
    
    def cleanup_orphaned_files(self, org_id: int = None) -> dict:
        """Find and securely delete orphaned files not referenced by any document.
        
        Args:
            org_id: Optional organization ID to limit cleanup scope
        
        Returns:
            Dict with cleanup statistics
        """
        from app import db
        from models import Document
        
        stats = {
            'files_found': 0,
            'files_orphaned': 0,
            'files_deleted': 0,
            'files_failed': 0
        }
        
        search_dir = self.base_upload_dir
        if org_id:
            search_dir = os.path.join(self.base_upload_dir, str(org_id))
        
        if not os.path.exists(search_dir):
            return stats
        
        query = Document.query.filter(Document.file_path.isnot(None))
        if org_id:
            query = query.filter_by(org_id=org_id)
        
        referenced_files = set()
        for doc in query.all():
            if doc.file_path:
                referenced_files.add(os.path.basename(doc.file_path))
        
        for root, dirs, files in os.walk(search_dir):
            for filename in files:
                stats['files_found'] += 1
                
                if filename not in referenced_files:
                    stats['files_orphaned'] += 1
                    file_path = os.path.join(root, filename)
                    
                    if secure_delete_file(file_path):
                        stats['files_deleted'] += 1
                        audit_log_deletion(
                            file_path=file_path,
                            file_type='orphaned_upload',
                            org_id=org_id
                        )
                    else:
                        stats['files_failed'] += 1
        
        self.logger.info(f"Orphaned file cleanup complete: {stats}")
        return stats


secure_file_manager = SecureFileManager()

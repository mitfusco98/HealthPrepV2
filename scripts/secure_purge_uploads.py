#!/usr/bin/env python3
"""
HIPAA Compliance: Secure Purge of Original Upload Files

This script securely deletes original document files that have been processed
and extracted. It overwrites files with random data before deletion to prevent
PHI recovery from disk.

Usage:
    python scripts/secure_purge_uploads.py --dry-run    # Preview what would be deleted
    python scripts/secure_purge_uploads.py --execute    # Actually delete files

This should be run:
1. After initial deployment to purge any existing original files
2. Periodically as a maintenance task to catch any missed files
3. Before decommissioning storage to ensure complete PHI disposal
"""

import os
import sys
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Document, FHIRDocument, AdminLog
from utils.secure_delete import secure_delete_file, audit_log_deletion, hash_path_for_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)




def get_documents_with_files():
    """Get all documents that still have file_path set and haven't been disposed."""
    return Document.query.filter(
        Document.file_path.isnot(None),
        db.or_(
            Document.file_disposed == False,
            Document.file_disposed.is_(None)
        )
    ).all()


def get_processed_documents_with_files():
    """Get documents that have been processed (OCR complete) but still have original files."""
    return Document.query.filter(
        Document.file_path.isnot(None),
        Document.processed_at.isnot(None),
        db.or_(
            Document.file_disposed == False,
            Document.file_disposed.is_(None)
        )
    ).all()


def purge_document_file(document, dry_run=True):
    """Securely delete a document's original file.
    
    Args:
        document: Document model instance
        dry_run: If True, only log what would be deleted without actually deleting
    
    Returns:
        True if file was deleted (or would be in dry_run), False otherwise
    """
    if not document.file_path:
        return False
    
    file_path = document.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), 'uploads', file_path)
    
    if not os.path.exists(file_path):
        # Use hashed path in logs to prevent PHI leakage via filenames
        logger.info(f"File already deleted or missing: {hash_path_for_log(file_path)} (doc_id={document.id})")
        document.file_path = None
        document.file_disposed = True
        document.file_disposed_at = datetime.utcnow()
        if not dry_run:
            db.session.commit()
        return True
    
    file_size = os.path.getsize(file_path)
    
    if dry_run:
        # Use hashed path in logs to prevent PHI leakage via filenames
        logger.info(f"[DRY RUN] Would securely delete: {hash_path_for_log(file_path)} ({file_size} bytes, doc_id={document.id})")
        return True
    
    if secure_delete_file(file_path):
        document.file_path = None
        document.file_disposed = True
        document.file_disposed_at = datetime.utcnow()
        db.session.commit()
        
        audit_log_deletion(
            file_path=file_path,
            file_type='backfill_purge',
            patient_id=document.patient_id,
            org_id=document.org_id
        )
        
        # Use hashed path in logs to prevent PHI leakage via filenames
        logger.info(f"Securely deleted: {hash_path_for_log(file_path)} ({file_size} bytes, doc_id={document.id})")
        return True
    else:
        logger.error(f"Failed to securely delete: {hash_path_for_log(file_path)} (doc_id={document.id})")
        return False


def scan_orphaned_files(uploads_dir):
    """Find files in uploads directory not referenced by any document."""
    if not os.path.exists(uploads_dir):
        return []
    
    referenced_files = set()
    for doc in Document.query.filter(Document.file_path.isnot(None)).all():
        if doc.file_path:
            referenced_files.add(os.path.basename(doc.file_path))
    
    orphaned = []
    for root, dirs, files in os.walk(uploads_dir):
        for filename in files:
            if filename not in referenced_files:
                file_path = os.path.join(root, filename)
                orphaned.append(file_path)
    
    return orphaned


def purge_orphaned_file(file_path, dry_run=True):
    """Securely delete an orphaned file."""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path)
    
    if dry_run:
        # Use hashed path in logs to prevent PHI leakage via filenames
        logger.info(f"[DRY RUN] Would securely delete orphaned: {hash_path_for_log(file_path)} ({file_size} bytes)")
        return True
    
    if secure_delete_file(file_path):
        audit_log_deletion(
            file_path=file_path,
            file_type='orphaned_file_purge',
            patient_id=None,
            org_id=0
        )
        
        # Use hashed path in logs to prevent PHI leakage via filenames
        logger.info(f"Securely deleted orphaned: {hash_path_for_log(file_path)} ({file_size} bytes)")
        return True
    else:
        logger.error(f"Failed to securely delete orphaned: {hash_path_for_log(file_path)}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Securely purge original upload files for HIPAA compliance')
    parser.add_argument('--dry-run', action='store_true', help='Preview what would be deleted without actually deleting')
    parser.add_argument('--execute', action='store_true', help='Actually delete files (requires explicit flag for safety)')
    parser.add_argument('--processed-only', action='store_true', help='Only delete files for documents that have been processed')
    parser.add_argument('--include-orphans', action='store_true', help='Also delete orphaned files not referenced by any document')
    parser.add_argument('--uploads-dir', default='uploads', help='Path to uploads directory')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        print("ERROR: Must specify either --dry-run or --execute")
        print("Use --dry-run to preview what would be deleted")
        print("Use --execute to actually delete files")
        sys.exit(1)
    
    if args.dry_run and args.execute:
        print("ERROR: Cannot specify both --dry-run and --execute")
        sys.exit(1)
    
    dry_run = args.dry_run
    
    with app.app_context():
        logger.info("=" * 60)
        logger.info("HIPAA Compliance: Secure Upload File Purge")
        logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'EXECUTE (files will be deleted)'}")
        logger.info("=" * 60)
        
        if args.processed_only:
            documents = get_processed_documents_with_files()
            logger.info(f"Found {len(documents)} processed documents with original files")
        else:
            documents = get_documents_with_files()
            logger.info(f"Found {len(documents)} documents with original files")
        
        success_count = 0
        fail_count = 0
        total_bytes = 0
        
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                total_bytes += os.path.getsize(doc.file_path)
            elif doc.file_path:
                file_path = os.path.join(os.getcwd(), 'uploads', doc.file_path)
                if os.path.exists(file_path):
                    total_bytes += os.path.getsize(file_path)
            
            if purge_document_file(doc, dry_run):
                success_count += 1
            else:
                fail_count += 1
        
        orphan_count = 0
        if args.include_orphans:
            logger.info("\nScanning for orphaned files...")
            orphaned_files = scan_orphaned_files(args.uploads_dir)
            logger.info(f"Found {len(orphaned_files)} orphaned files")
            
            for file_path in orphaned_files:
                if os.path.exists(file_path):
                    total_bytes += os.path.getsize(file_path)
                
                if purge_orphaned_file(file_path, dry_run):
                    orphan_count += 1
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Documents processed: {success_count} success, {fail_count} failed")
        if args.include_orphans:
            logger.info(f"  Orphaned files: {orphan_count}")
        logger.info(f"  Total bytes {'would be ' if dry_run else ''}freed: {total_bytes:,}")
        logger.info(f"  Mode: {'DRY RUN - no files were deleted' if dry_run else 'EXECUTE - files were securely deleted'}")
        logger.info("=" * 60)
        
        if dry_run:
            logger.info("\nTo actually delete files, run with --execute flag")


if __name__ == '__main__':
    main()

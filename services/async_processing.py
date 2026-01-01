"""
Asynchronous Processing Service for HealthPrepV2
Handles batch processing of FHIR data and prep sheet generation using RQ (Redis Queue)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json

from flask import current_app
from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from rq.job import JobStatus

logger = logging.getLogger(__name__)


class AsyncProcessingService:
    """Service for managing asynchronous FHIR processing tasks"""
    
    def __init__(self, redis_url='redis://localhost:6379/0'):
        self.redis_conn = Redis.from_url(redis_url)
        self.queue = Queue('fhir_processing', connection=self.redis_conn)
        self.high_priority_queue = Queue('fhir_priority', connection=self.redis_conn)
    
    def enqueue_batch_patient_sync(self, organization_id: int, patient_mrns: List[str], 
                                 user_id: int, priority: str = 'normal') -> str:
        """
        Enqueue batch patient synchronization from Epic FHIR
        
        Args:
            organization_id: Organization ID
            patient_mrns: List of patient MRNs to sync
            user_id: User who initiated the sync
            priority: 'normal' or 'high'
            
        Returns:
            Job ID for tracking progress
        """
        job_data = {
            'organization_id': organization_id,
            'patient_mrns': patient_mrns,
            'user_id': user_id,
            'initiated_at': datetime.utcnow().isoformat(),
            'task_type': 'batch_patient_sync'
        }
        
        queue = self.high_priority_queue if priority == 'high' else self.queue
        job = queue.enqueue(
            'services.async_processing.batch_sync_patients_from_epic',
            job_data,
            job_timeout='30m',  # 30 minutes timeout for batch operations
            job_id=f"batch_sync_{organization_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Log the async job initiation
        from models import log_admin_event
        log_admin_event(
            event_type='async_batch_sync_initiated',
            user_id=user_id,
            org_id=organization_id,
            ip=None,  # Will be set by caller if available
            data={
                'job_id': job.id,
                'patient_count': len(patient_mrns),
                'priority': priority
            },
            action_details=f"Initiated batch sync for {len(patient_mrns)} patients"
        )
        
        logger.info(f"Enqueued batch patient sync job {job.id} for {len(patient_mrns)} patients")
        return job.id
    
    def enqueue_batch_prep_sheet_generation(self, organization_id: int, 
                                          patient_ids: List[int], screening_types: List[int],
                                          user_id: int, priority: str = 'normal') -> str:
        """
        Enqueue batch preparation sheet generation
        
        Args:
            organization_id: Organization ID
            patient_ids: List of patient IDs
            screening_types: List of screening type IDs
            user_id: User who initiated the generation
            priority: 'normal' or 'high'
            
        Returns:
            Job ID for tracking progress
        """
        job_data = {
            'organization_id': organization_id,
            'patient_ids': patient_ids,
            'screening_types': screening_types,
            'user_id': user_id,
            'initiated_at': datetime.utcnow().isoformat(),
            'task_type': 'batch_prep_sheet_generation'
        }
        
        queue = self.high_priority_queue if priority == 'high' else self.queue
        job = queue.enqueue(
            'services.async_processing.batch_generate_prep_sheets',
            job_data,
            job_timeout='45m',  # 45 minutes for prep sheet generation
            job_id=f"prep_sheets_{organization_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Log the async job initiation
        from models import log_admin_event
        log_admin_event(
            event_type='async_prep_sheet_batch_initiated',
            user_id=user_id,
            org_id=organization_id,
            ip=None,
            data={
                'job_id': job.id,
                'patient_count': len(patient_ids),
                'screening_type_count': len(screening_types),
                'priority': priority
            },
            action_details=f"Initiated batch prep sheet generation for {len(patient_ids)} patients"
        )
        
        logger.info(f"Enqueued batch prep sheet generation job {job.id}")
        return job.id
    
    def enqueue_document_processing(self, organization_id: int, fhir_document_ids: List[int],
                                  user_id: int) -> str:
        """
        Enqueue batch FHIR document processing (OCR, relevance scoring)
        """
        job_data = {
            'organization_id': organization_id,
            'fhir_document_ids': fhir_document_ids,
            'user_id': user_id,
            'initiated_at': datetime.utcnow().isoformat(),
            'task_type': 'batch_document_processing'
        }
        
        job = self.queue.enqueue(
            'services.async_processing.batch_process_fhir_documents',
            job_data,
            job_timeout='20m',
            job_id=f"doc_process_{organization_id}_{datetime.utcnow().timestamp()}"
        )
        
        from models import log_admin_event
        log_admin_event(
            event_type='async_document_processing_initiated',
            user_id=user_id,
            org_id=organization_id,
            ip=None,
            data={
                'job_id': job.id,
                'document_count': len(fhir_document_ids)
            },
            action_details=f"Initiated batch processing for {len(fhir_document_ids)} documents"
        )
        
        return job.id
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get detailed status of an async job"""
        try:
            job = Job.fetch(job_id, connection=self.redis_conn)
            
            status_info = {
                'job_id': job_id,
                'status': job.get_status(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                'progress': job.meta.get('progress', {}),
                'result': job.result if job.is_finished else None,
                'exc_info': str(job.exc_info) if job.is_failed else None
            }
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {str(e)}")
            return {'job_id': job_id, 'status': 'unknown', 'error': str(e)}
    
    def get_organization_active_jobs(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get all active jobs for an organization"""
        active_jobs = []
        
        # Check both queues
        for queue in [self.queue, self.high_priority_queue]:
            for job in queue.get_jobs():
                if job.args and len(job.args) > 0:
                    job_data = job.args[0]
                    if isinstance(job_data, dict) and job_data.get('organization_id') == organization_id:
                        active_jobs.append(self.get_job_status(job.id))
        
        return active_jobs
    
    def cancel_job(self, job_id: str, user_id: int, organization_id: int) -> bool:
        """Cancel a running or queued job"""
        try:
            job = Job.fetch(job_id, connection=self.redis_conn)
            job.cancel()
            
            log_admin_event(
                event_type='async_job_cancelled',
                user_id=user_id,
                org_id=organization_id,
                ip=None,
                data={'job_id': job_id},
                action_details=f"Cancelled async job {job_id}"
            )
            
            logger.info(f"Cancelled job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {str(e)}")
            return False


# Background Job Functions (these run in the worker processes)

def batch_sync_patients_from_epic(job_data: Dict[str, Any]):
    """
    Background job: Sync multiple patients from Epic FHIR
    This runs in a separate worker process
    """
    from app import app
    
    with app.app_context():
        organization_id = job_data['organization_id']
        patient_mrns = job_data['patient_mrns']
        user_id = job_data['user_id']
        
        logger.info(f"Starting batch sync for {len(patient_mrns)} patients in org {organization_id}")
        
        # Initialize Epic FHIR service
        epic_service = EpicFHIRService(organization_id)
        
        results = {
            'successful_syncs': [],
            'failed_syncs': [],
            'total_patients': len(patient_mrns),
            'started_at': datetime.utcnow().isoformat()
        }
        
        # Update job progress
        job = Job.fetch(job_data.get('job_id', ''), connection=Redis.from_url('redis://localhost:6379/0'))
        
        for i, mrn in enumerate(patient_mrns):
            try:
                # Update progress
                progress = {
                    'current': i + 1,
                    'total': len(patient_mrns),
                    'percentage': round((i + 1) / len(patient_mrns) * 100, 1),
                    'current_mrn': mrn
                }
                job.meta['progress'] = progress
                job.save_meta()
                
                # Sync patient from Epic
                patient = epic_service.sync_patient_from_epic(mrn)
                
                if patient:
                    # Sync patient documents
                    documents = epic_service.sync_patient_documents(patient)
                    
                    results['successful_syncs'].append({
                        'mrn': mrn,
                        'patient_id': patient.id,
                        'documents_synced': len(documents)
                    })
                    
                    # Log successful sync
                    log_admin_event(
                        event_type='fhir_patient_sync_success',
                        user_id=user_id,
                        org_id=organization_id,
                        patient_id=patient.id,
                        ip=None,
                        data={'mrn': mrn, 'documents_count': len(documents)},
                        action_details=f"Successfully synced patient {mrn} with {len(documents)} documents"
                    )
                else:
                    results['failed_syncs'].append({'mrn': mrn, 'error': 'Patient not found in Epic'})
                    
            except Exception as e:
                error_msg = str(e)
                results['failed_syncs'].append({'mrn': mrn, 'error': error_msg})
                logger.error(f"Failed to sync patient: {error_msg}")
                
                # Log failed sync
                log_admin_event(
                    event_type='fhir_patient_sync_failed',
                    user_id=user_id,
                    org_id=organization_id,
                    ip=None,
                    data={'mrn': mrn, 'error': error_msg},
                    action_details=f"Failed to sync patient {mrn}: {error_msg}"
                )
        
        results['completed_at'] = datetime.utcnow().isoformat()
        results['success_rate'] = len(results['successful_syncs']) / len(patient_mrns) * 100
        
        logger.info(f"Batch sync completed: {len(results['successful_syncs'])}/{len(patient_mrns)} successful")
        
        # Log batch completion
        log_admin_event(
            event_type='async_batch_sync_completed',
            user_id=user_id,
            org_id=organization_id,
            ip=None,
            data=results,
            action_details=f"Batch sync completed: {len(results['successful_syncs'])}/{len(patient_mrns)} successful"
        )
        
        return results


def batch_generate_prep_sheets(job_data: Dict[str, Any]):
    """
    Background job: Generate preparation sheets for multiple patients
    """
    from app import app
    from prep_sheet.generator import PrepSheetGenerator
    
    with app.app_context():
        organization_id = job_data['organization_id']
        patient_ids = job_data['patient_ids']
        screening_type_ids = job_data['screening_types']
        user_id = job_data['user_id']
        
        logger.info(f"Starting batch prep sheet generation for {len(patient_ids)} patients")
        
        # Initialize services
        epic_service = EpicFHIRService(organization_id)
        prep_generator = PrepSheetGenerator()
        
        results = {
            'successful_generations': [],
            'failed_generations': [],
            'total_patients': len(patient_ids),
            'started_at': datetime.utcnow().isoformat()
        }
        
        # Update job progress
        job = Job.fetch(job_data.get('job_id', ''), connection=Redis.from_url('redis://localhost:6379/0'))
        
        for i, patient_id in enumerate(patient_ids):
            try:
                # Update progress
                progress = {
                    'current': i + 1,
                    'total': len(patient_ids),
                    'percentage': round((i + 1) / len(patient_ids) * 100, 1),
                    'current_patient_id': patient_id
                }
                job.meta['progress'] = progress
                job.save_meta()
                
                patient = Patient.query.get(patient_id)
                if not patient:
                    results['failed_generations'].append({
                        'patient_id': patient_id,
                        'error': 'Patient not found'
                    })
                    continue
                
                # Generate prep sheet
                prep_sheet_content = prep_generator.generate_for_patient(
                    patient, screening_type_ids
                )
                
                # Write back to Epic if configured
                if epic_service.ensure_authenticated():
                    screening_types = [st for st in patient.screening_types if st.id in screening_type_ids]
                    epic_doc_id = epic_service.write_prep_sheet_to_epic(
                        patient, prep_sheet_content, screening_types
                    )
                    
                    results['successful_generations'].append({
                        'patient_id': patient_id,
                        'patient_mrn': patient.mrn,
                        'epic_document_id': epic_doc_id,
                        'content_length': len(prep_sheet_content)
                    })
                else:
                    # Store locally if Epic not available
                    results['successful_generations'].append({
                        'patient_id': patient_id,
                        'patient_mrn': patient.mrn,
                        'epic_document_id': None,
                        'content_length': len(prep_sheet_content)
                    })
                
                # Log successful generation
                log_admin_event(
                    event_type='prep_sheet_generated',
                    user_id=user_id,
                    org_id=organization_id,
                    patient_id=patient_id,
                    ip=None,
                    data={'screening_types': screening_type_ids},
                    action_details=f"Generated prep sheet for patient {patient.mrn}"
                )
                
            except Exception as e:
                error_msg = str(e)
                results['failed_generations'].append({
                    'patient_id': patient_id,
                    'error': error_msg
                })
                logger.error(f"Failed to generate prep sheet for patient {patient_id}: {error_msg}")
        
        results['completed_at'] = datetime.utcnow().isoformat()
        results['success_rate'] = len(results['successful_generations']) / len(patient_ids) * 100
        
        logger.info(f"Batch prep sheet generation completed: {len(results['successful_generations'])}/{len(patient_ids)} successful")
        
        # Log batch completion
        log_admin_event(
            event_type='async_prep_sheet_batch_completed',
            user_id=user_id,
            org_id=organization_id,
            ip=None,
            data=results,
            action_details=f"Batch prep sheet generation completed: {len(results['successful_generations'])}/{len(patient_ids)} successful"
        )
        
        return results


def batch_process_fhir_documents(job_data: Dict[str, Any]):
    """
    Background job: Process FHIR documents (OCR, relevance scoring)
    """
    from app import app
    
    with app.app_context():
        organization_id = job_data['organization_id']
        fhir_document_ids = job_data['fhir_document_ids']
        user_id = job_data['user_id']
        
        logger.info(f"Starting batch document processing for {len(fhir_document_ids)} documents")
        
        epic_service = EpicFHIRService(organization_id)
        
        results = {
            'successful_processing': [],
            'failed_processing': [],
            'total_documents': len(fhir_document_ids),
            'started_at': datetime.utcnow().isoformat()
        }
        
        # Update job progress
        job = Job.fetch(job_data.get('job_id', ''), connection=Redis.from_url('redis://localhost:6379/0'))
        
        for i, doc_id in enumerate(fhir_document_ids):
            try:
                # Update progress
                progress = {
                    'current': i + 1,
                    'total': len(fhir_document_ids),
                    'percentage': round((i + 1) / len(fhir_document_ids) * 100, 1),
                    'current_document_id': doc_id
                }
                job.meta['progress'] = progress
                job.save_meta()
                
                fhir_doc = FHIRDocument.query.get(doc_id)
                if not fhir_doc:
                    results['failed_processing'].append({
                        'document_id': doc_id,
                        'error': 'Document not found'
                    })
                    continue
                
                # Process document using Epic service
                epic_service._download_and_process_document(fhir_doc)
                
                results['successful_processing'].append({
                    'document_id': doc_id,
                    'epic_document_id': fhir_doc.epic_document_id,
                    'processing_status': fhir_doc.processing_status,
                    'ocr_text_length': len(fhir_doc.ocr_text or '')
                })
                
            except Exception as e:
                error_msg = str(e)
                results['failed_processing'].append({
                    'document_id': doc_id,
                    'error': error_msg
                })
                logger.error(f"Failed to process document {doc_id}: {error_msg}")
        
        results['completed_at'] = datetime.utcnow().isoformat()
        results['success_rate'] = len(results['successful_processing']) / len(fhir_document_ids) * 100
        
        logger.info(f"Batch document processing completed: {len(results['successful_processing'])}/{len(fhir_document_ids)} successful")
        
        return results


# Factory function for easy service access
def get_async_processing_service() -> AsyncProcessingService:
    """Get async processing service instance"""
    return AsyncProcessingService()
"""
Utility functions for prep sheet generation and caching
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from app import db
from models import (Patient, PatientScreening, MedicalDocument, PatientCondition, 
                   Appointment, ChecklistSettings, ScreeningDocumentMatch)
import hashlib
import json

def cache_timestamp():
    """Generate cache-busting timestamp"""
    return int(datetime.utcnow().timestamp())

def generate_prep_sheet_data(patient: Patient) -> Dict[str, Any]:
    """Generate comprehensive prep sheet data for a patient"""
    try:
        logging.info(f"Generating prep sheet for patient {patient.mrn}")
        
        # Import here to avoid circular imports
        from prep_sheet.generator import PrepSheetGenerator
        
        generator = PrepSheetGenerator()
        prep_data = generator.generate_prep_sheet(patient.id)
        
        return prep_data
        
    except Exception as e:
        logging.error(f"Error generating prep sheet data for patient {patient.id}: {str(e)}")
        raise

def calculate_patient_age(birth_date: datetime) -> int:
    """Calculate patient age from birth date"""
    if not birth_date:
        return 0
    
    today = datetime.now().date()
    birth_date = birth_date.date() if isinstance(birth_date, datetime) else birth_date
    
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def format_screening_status(status: str) -> Dict[str, str]:
    """Format screening status with appropriate styling"""
    status_mapping = {
        'due': {'class': 'badge bg-danger', 'text': 'Due'},
        'due_soon': {'class': 'badge bg-warning', 'text': 'Due Soon'},
        'complete': {'class': 'badge bg-success', 'text': 'Complete'},
        'not_applicable': {'class': 'badge bg-secondary', 'text': 'N/A'}
    }
    
    return status_mapping.get(status, {'class': 'badge bg-secondary', 'text': status.title()})

def format_confidence_level(confidence: Optional[float]) -> Dict[str, str]:
    """Format OCR confidence level with color coding"""
    if confidence is None:
        return {'class': 'badge bg-secondary', 'text': 'Unknown', 'level': 'unknown'}
    
    if confidence >= 0.9:
        return {'class': 'badge bg-success', 'text': 'High', 'level': 'high'}
    elif confidence >= 0.7:
        return {'class': 'badge bg-warning', 'text': 'Medium', 'level': 'medium'}
    elif confidence >= 0.5:
        return {'class': 'badge bg-danger', 'text': 'Low', 'level': 'low'}
    else:
        return {'class': 'badge bg-dark', 'text': 'Very Low', 'level': 'very_low'}

def get_document_icon(document_type: str) -> str:
    """Get Font Awesome icon for document type"""
    icon_mapping = {
        'lab': 'fas fa-vial',
        'imaging': 'fas fa-x-ray',
        'consult': 'fas fa-stethoscope',
        'hospital': 'fas fa-hospital',
        'default': 'fas fa-file-medical'
    }
    
    return icon_mapping.get(document_type, icon_mapping['default'])

def format_document_date(doc_date: Optional[datetime]) -> str:
    """Format document date for display"""
    if not doc_date:
        return 'Unknown'
    
    if isinstance(doc_date, str):
        try:
            doc_date = datetime.strptime(doc_date, '%Y-%m-%d').date()
        except:
            return doc_date
    elif isinstance(doc_date, datetime):
        doc_date = doc_date.date()
    
    return doc_date.strftime('%m/%d/%Y')

def calculate_screening_compliance_rate(patient_id: int) -> float:
    """Calculate overall screening compliance rate for a patient"""
    try:
        total_screenings = PatientScreening.query.filter_by(patient_id=patient_id).count()
        complete_screenings = PatientScreening.query.filter_by(
            patient_id=patient_id,
            status='complete'
        ).count()
        
        if total_screenings == 0:
            return 0.0
        
        return round((complete_screenings / total_screenings) * 100, 1)
        
    except Exception as e:
        logging.error(f"Error calculating compliance rate for patient {patient_id}: {str(e)}")
        return 0.0

def get_overdue_screenings(patient_id: int) -> List[PatientScreening]:
    """Get list of overdue screenings for a patient"""
    try:
        today = datetime.now().date()
        
        overdue_screenings = PatientScreening.query.filter_by(
            patient_id=patient_id,
            status='due'
        ).filter(
            PatientScreening.next_due_date < today
        ).all()
        
        return overdue_screenings
        
    except Exception as e:
        logging.error(f"Error getting overdue screenings for patient {patient_id}: {str(e)}")
        return []

def format_frequency_text(frequency_value: int, frequency_unit: str) -> str:
    """Format screening frequency for display"""
    if frequency_value == 1:
        unit_text = frequency_unit.rstrip('s')  # Remove plural
    else:
        unit_text = frequency_unit
    
    return f"Every {frequency_value} {unit_text}"

def generate_document_preview(document: MedicalDocument, max_length: int = 150) -> str:
    """Generate a preview of document content"""
    if not document.ocr_text:
        return "No text content available"
    
    text = document.ocr_text.strip()
    
    if len(text) <= max_length:
        return text
    
    # Try to find a sentence break
    sentence_end = text[:max_length].rfind('.')
    if sentence_end > max_length // 2:
        return text[:sentence_end + 1]
    
    # Fall back to word boundary
    space_index = text[:max_length].rfind(' ')
    if space_index > max_length // 2:
        return text[:space_index] + "..."
    
    return text[:max_length] + "..."

def get_screening_document_matches(screening_id: int) -> List[Dict[str, Any]]:
    """Get formatted document matches for a screening"""
    try:
        matches = ScreeningDocumentMatch.query.filter_by(screening_id=screening_id).all()
        
        formatted_matches = []
        for match in matches:
            doc = match.document
            formatted_matches.append({
                'document_id': doc.id,
                'filename': doc.original_filename or doc.filename,
                'date': format_document_date(doc.document_date),
                'confidence': match.match_confidence,
                'confidence_display': format_confidence_level(match.match_confidence),
                'document_type': doc.document_type,
                'icon': get_document_icon(doc.document_type),
                'preview': generate_document_preview(doc, 100)
            })
        
        # Sort by confidence and date
        formatted_matches.sort(key=lambda x: (x['confidence'] or 0, x['date']), reverse=True)
        
        return formatted_matches
        
    except Exception as e:
        logging.error(f"Error getting document matches for screening {screening_id}: {str(e)}")
        return []

def validate_date_string(date_string: str) -> Optional[datetime]:
    """Validate and parse date string"""
    if not date_string:
        return None
    
    date_formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%m-%d-%Y',
        '%Y/%m/%d'
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    return None

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    import re
    
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove multiple consecutive underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1
        filename = name[:max_name_length] + '.' + ext if ext else name[:255]
    
    return filename

def generate_patient_summary(patient: Patient) -> Dict[str, Any]:
    """Generate patient summary statistics"""
    try:
        # Get screening statistics
        total_screenings = PatientScreening.query.filter_by(patient_id=patient.id).count()
        due_screenings = PatientScreening.query.filter_by(patient_id=patient.id, status='due').count()
        complete_screenings = PatientScreening.query.filter_by(patient_id=patient.id, status='complete').count()
        
        # Get document statistics
        total_documents = MedicalDocument.query.filter_by(patient_id=patient.id).count()
        recent_documents = MedicalDocument.query.filter_by(patient_id=patient.id).filter(
            MedicalDocument.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Get condition count
        active_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).count()
        
        # Get last appointment
        last_appointment = Appointment.query.filter_by(patient_id=patient.id).order_by(
            Appointment.appointment_date.desc()
        ).first()
        
        return {
            'screenings': {
                'total': total_screenings,
                'due': due_screenings,
                'complete': complete_screenings,
                'compliance_rate': calculate_screening_compliance_rate(patient.id)
            },
            'documents': {
                'total': total_documents,
                'recent': recent_documents
            },
            'conditions': {
                'active': active_conditions
            },
            'last_appointment': {
                'date': last_appointment.appointment_date.strftime('%Y-%m-%d') if last_appointment else None,
                'type': last_appointment.appointment_type if last_appointment else None
            }
        }
        
    except Exception as e:
        logging.error(f"Error generating patient summary for {patient.id}: {str(e)}")
        return {
            'screenings': {'total': 0, 'due': 0, 'complete': 0, 'compliance_rate': 0},
            'documents': {'total': 0, 'recent': 0},
            'conditions': {'active': 0},
            'last_appointment': {'date': None, 'type': None}
        }

def get_system_health_status() -> Dict[str, Any]:
    """Get system health status for monitoring"""
    try:
        # Database connectivity
        db_healthy = True
        try:
            db.session.execute(db.text('SELECT 1')).scalar()
        except:
            db_healthy = False
        
        # Get basic statistics
        total_patients = Patient.query.count()
        total_documents = MedicalDocument.query.count()
        processed_documents = MedicalDocument.query.filter(
            MedicalDocument.ocr_text.isnot(None)
        ).count()
        
        # Calculate processing rate
        processing_rate = (processed_documents / max(total_documents, 1)) * 100
        
        return {
            'status': 'healthy' if db_healthy and processing_rate > 50 else 'warning',
            'database_connected': db_healthy,
            'total_patients': total_patients,
            'total_documents': total_documents,
            'processing_rate': round(processing_rate, 1),
            'last_checked': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error checking system health: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'last_checked': datetime.utcnow().isoformat()
        }

def create_audit_hash(data: Dict[str, Any]) -> str:
    """Create audit hash for data integrity verification"""
    # Convert data to JSON string and create hash
    data_string = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(data_string.encode()).hexdigest()

def mask_phi_in_logs(message: str) -> str:
    """Mask potential PHI in log messages"""
    import re
    
    # Mask SSN patterns
    message = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', 'XXX-XX-XXXX', message)
    
    # Mask phone numbers
    message = re.sub(r'\b\(\d{3}\)\s*\d{3}-\d{4}\b', '(XXX) XXX-XXXX', message)
    message = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', 'XXX-XXX-XXXX', message)
    
    # Mask potential MRN patterns
    message = re.sub(r'\bMRN\s*:?\s*\d+\b', 'MRN: XXXXXXXX', message, flags=re.IGNORECASE)
    
    return message

class PerformanceMonitor:
    """Performance monitoring utilities"""
    
    @staticmethod
    def log_performance_metric(operation: str, duration_seconds: float, details: Dict[str, Any] = None):
        """Log performance metrics for monitoring"""
        try:
            from models import AdminLog
            from app import db
            
            metric_details = {
                'operation': operation,
                'duration_seconds': duration_seconds,
                'details': details or {}
            }
            
            log_entry = AdminLog(
                action='performance_metric',
                details=json.dumps(metric_details),
                ip_address='system',
                user_agent='PerformanceMonitor'
            )
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error logging performance metric: {str(e)}")
    
    @staticmethod
    def time_operation(operation_name: str):
        """Decorator to time operations"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = datetime.utcnow()
                try:
                    result = func(*args, **kwargs)
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    
                    PerformanceMonitor.log_performance_metric(
                        operation_name, 
                        duration,
                        {'success': True}
                    )
                    
                    return result
                    
                except Exception as e:
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    
                    PerformanceMonitor.log_performance_metric(
                        operation_name,
                        duration,
                        {'success': False, 'error': str(e)}
                    )
                    
                    raise
            
            return wrapper
        return decorator


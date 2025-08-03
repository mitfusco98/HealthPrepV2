"""
Utility functions and helpers for the application.
Common functionality used across different modules.
"""

import os
import re
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from werkzeug.utils import secure_filename
from flask import current_app, request

logger = logging.getLogger(__name__)

def format_date(date_obj: Union[date, datetime, str, None], format_string: str = '%Y-%m-%d') -> str:
    """
    Format date object to string
    
    Args:
        date_obj: Date object to format
        format_string: Format string for output
        
    Returns:
        Formatted date string or empty string if None
    """
    if not date_obj:
        return ''
    
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj).date()
        except (ValueError, AttributeError):
            return date_obj
    
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    
    try:
        return date_obj.strftime(format_string)
    except (AttributeError, ValueError):
        return str(date_obj)

def format_datetime(datetime_obj: Union[datetime, str, None], format_string: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format datetime object to string
    
    Args:
        datetime_obj: Datetime object to format
        format_string: Format string for output
        
    Returns:
        Formatted datetime string or empty string if None
    """
    if not datetime_obj:
        return ''
    
    if isinstance(datetime_obj, str):
        try:
            datetime_obj = datetime.fromisoformat(datetime_obj)
        except ValueError:
            return datetime_obj
    
    try:
        return datetime_obj.strftime(format_string)
    except (AttributeError, ValueError):
        return str(datetime_obj)

def calculate_age(birth_date: Union[date, datetime, str]) -> Optional[int]:
    """
    Calculate age from birth date
    
    Args:
        birth_date: Date of birth
        
    Returns:
        Age in years or None if invalid date
    """
    if not birth_date:
        return None
    
    if isinstance(birth_date, str):
        try:
            birth_date = datetime.fromisoformat(birth_date).date()
        except ValueError:
            return None
    
    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    
    try:
        today = date.today()
        age = today.year - birth_date.year
        if today < date(today.year, birth_date.month, birth_date.day):
            age -= 1
        return age
    except (AttributeError, ValueError):
        return None

def parse_keywords(keywords_input: Union[str, List[str]]) -> List[str]:
    """
    Parse keywords from various input formats
    
    Args:
        keywords_input: Keywords as string or list
        
    Returns:
        List of cleaned keywords
    """
    if not keywords_input:
        return []
    
    if isinstance(keywords_input, list):
        return [kw.strip().lower() for kw in keywords_input if kw.strip()]
    
    if isinstance(keywords_input, str):
        try:
            # Try to parse as JSON first
            parsed = json.loads(keywords_input)
            if isinstance(parsed, list):
                return [kw.strip().lower() for kw in parsed if kw.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Parse as comma-separated string
        return [kw.strip().lower() for kw in keywords_input.split(',') if kw.strip()]
    
    return []

def normalize_medical_term(term: str) -> str:
    """
    Normalize medical terminology for consistent matching
    
    Args:
        term: Medical term to normalize
        
    Returns:
        Normalized term
    """
    if not term:
        return ''
    
    # Convert to lowercase
    normalized = term.lower().strip()
    
    # Common medical term normalizations
    normalizations = {
        'hemoglobin a1c': 'a1c',
        'hba1c': 'a1c',
        'glycated hemoglobin': 'a1c',
        'dual energy x-ray': 'dexa',
        'dxa': 'dexa',
        'electrocardiogram': 'ekg',
        'ecg': 'ekg',
        'complete blood count': 'cbc',
        'blood pressure': 'bp'
    }
    
    return normalizations.get(normalized, normalized)

def validate_mrn(mrn: str) -> bool:
    """
    Validate Medical Record Number format
    
    Args:
        mrn: MRN to validate
        
    Returns:
        True if valid MRN format
    """
    if not mrn:
        return False
    
    # MRN should be alphanumeric, typically 3-20 characters
    pattern = re.compile(r'^[A-Z0-9]{3,20}$', re.IGNORECASE)
    return bool(pattern.match(mrn.strip()))

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return 'unnamed_file'
    
    # Use werkzeug's secure_filename and add timestamp
    base_name = secure_filename(filename)
    
    # If secure_filename removes everything, use a default
    if not base_name:
        base_name = 'unnamed_file'
    
    # Add timestamp to prevent conflicts
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(base_name)
    
    return f"{name}_{timestamp}{ext}"

def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename
    
    Args:
        filename: Filename to analyze
        
    Returns:
        File extension (lowercase, without dot)
    """
    if not filename or '.' not in filename:
        return ''
    
    return filename.rsplit('.', 1)[1].lower()

def is_allowed_file(filename: str, allowed_extensions: Optional[set] = None) -> bool:
    """
    Check if file extension is allowed
    
    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions (uses app config if None)
        
    Returns:
        True if file extension is allowed
    """
    if not allowed_extensions:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    
    extension = get_file_extension(filename)
    return extension in allowed_extensions

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def get_confidence_level(confidence: Optional[float]) -> str:
    """
    Get confidence level category from confidence score
    
    Args:
        confidence: Confidence score (0-100)
        
    Returns:
        Confidence level string
    """
    if confidence is None:
        return 'unknown'
    
    if confidence >= 85:
        return 'high'
    elif confidence >= 70:
        return 'medium'
    elif confidence >= 50:
        return 'low'
    else:
        return 'very_low'

def get_confidence_color(confidence: Optional[float]) -> str:
    """
    Get Bootstrap color class for confidence level
    
    Args:
        confidence: Confidence score (0-100)
        
    Returns:
        Bootstrap color class
    """
    level = get_confidence_level(confidence)
    
    color_map = {
        'high': 'success',
        'medium': 'warning',
        'low': 'danger',
        'very_low': 'dark',
        'unknown': 'secondary'
    }
    
    return color_map.get(level, 'secondary')

def parse_json_field(json_string: Union[str, dict, list, None]) -> Any:
    """
    Safely parse JSON field from database
    
    Args:
        json_string: JSON string or already parsed object
        
    Returns:
        Parsed object or empty dict/list on error
    """
    if not json_string:
        return {}
    
    if isinstance(json_string, (dict, list)):
        return json_string
    
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return {} if json_string.strip().startswith('{') else []

def format_screening_frequency(frequency_value: int, frequency_unit: str) -> str:
    """
    Format screening frequency for display
    
    Args:
        frequency_value: Frequency value
        frequency_unit: Frequency unit ('months' or 'years')
        
    Returns:
        Formatted frequency string
    """
    if not frequency_value or not frequency_unit:
        return 'Not specified'
    
    unit_text = frequency_unit
    if frequency_value == 1:
        unit_text = frequency_unit.rstrip('s')  # Remove 's' for singular
    
    return f"Every {frequency_value} {unit_text}"

def get_status_badge_class(status: str) -> str:
    """
    Get Bootstrap badge class for screening status
    
    Args:
        status: Screening status
        
    Returns:
        Bootstrap badge class
    """
    status_classes = {
        'Complete': 'bg-success',
        'Due Soon': 'bg-warning text-dark',
        'Due': 'bg-danger',
        'Overdue': 'bg-danger',
        'Unknown': 'bg-secondary'
    }
    
    return status_classes.get(status, 'bg-secondary')

def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Truncate text to specified length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text:
        return ''
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ''
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common OCR artifacts
    cleaned = re.sub(r'[^\w\s.,;:!?()\[\]{}/-]', '', cleaned)
    
    return cleaned

def extract_medical_values(text: str) -> List[Dict[str, str]]:
    """
    Extract medical values and units from text
    
    Args:
        text: Text to analyze
        
    Returns:
        List of dictionaries with value and unit
    """
    if not text:
        return []
    
    # Pattern for medical values with units
    value_pattern = re.compile(
        r'\b(\d+\.?\d*)\s*(mg/dL|mmol/L|ng/mL|pg/mL|IU/L|U/L|%|mmHg|bpm)\b',
        re.IGNORECASE
    )
    
    matches = value_pattern.findall(text)
    
    return [{'value': value, 'unit': unit} for value, unit in matches]

def is_medical_document(filename: str, content: str = '') -> bool:
    """
    Determine if document appears to be medical based on filename and content
    
    Args:
        filename: Document filename
        content: Document content (optional)
        
    Returns:
        True if appears to be medical document
    """
    if not filename:
        return False
    
    filename_lower = filename.lower()
    
    # Medical keywords in filename
    medical_keywords = [
        'lab', 'test', 'result', 'report', 'imaging', 'xray', 'ct', 'mri',
        'mammogram', 'ultrasound', 'blood', 'urine', 'pathology', 'biopsy',
        'consult', 'discharge', 'admission', 'procedure', 'surgery'
    ]
    
    if any(keyword in filename_lower for keyword in medical_keywords):
        return True
    
    # Check content if provided
    if content:
        content_lower = content.lower()
        medical_terms = [
            'patient', 'diagnosis', 'treatment', 'medication', 'doctor',
            'physician', 'hospital', 'clinic', 'medical', 'health'
        ]
        
        if any(term in content_lower for term in medical_terms):
            return True
    
    return False

def get_user_timezone() -> str:
    """
    Get user timezone from request or default
    
    Returns:
        Timezone string
    """
    # For now, return UTC. Could be enhanced to detect user timezone
    return 'UTC'

def convert_to_user_timezone(datetime_obj: datetime, timezone: str = None) -> datetime:
    """
    Convert datetime to user timezone
    
    Args:
        datetime_obj: Datetime to convert
        timezone: Target timezone (uses user timezone if None)
        
    Returns:
        Converted datetime
    """
    # Placeholder implementation - would use pytz in production
    return datetime_obj

def log_user_action(action: str, description: str = None, level: str = 'INFO'):
    """
    Log user action with context
    
    Args:
        action: Action being performed
        description: Action description
        level: Log level
    """
    try:
        from flask_login import current_user
        
        user_info = 'anonymous'
        if current_user.is_authenticated:
            user_info = current_user.username
        
        ip_address = request.remote_addr if request else 'unknown'
        
        log_message = f"User {user_info} ({ip_address}): {action}"
        if description:
            log_message += f" - {description}"
        
        if level.upper() == 'ERROR':
            logger.error(log_message)
        elif level.upper() == 'WARNING':
            logger.warning(log_message)
        else:
            logger.info(log_message)
            
    except Exception as e:
        logger.error(f"Error logging user action: {str(e)}")

def generate_unique_id(prefix: str = '') -> str:
    """
    Generate unique ID with optional prefix
    
    Args:
        prefix: Prefix for the ID
        
    Returns:
        Unique ID string
    """
    import uuid
    
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    if prefix:
        return f"{prefix}_{timestamp}_{unique_id}"
    else:
        return f"{timestamp}_{unique_id}"

def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def merge_dicts(*dicts: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Merge multiple dictionaries
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result

def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to integer
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def get_client_ip() -> str:
    """
    Get client IP address from request
    
    Returns:
        Client IP address
    """
    try:
        if request.environ.get('HTTP_X_FORWARDED_FOR'):
            return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        elif request.environ.get('HTTP_X_REAL_IP'):
            return request.environ['HTTP_X_REAL_IP']
        else:
            return request.environ.get('REMOTE_ADDR', 'unknown')
    except Exception:
        return 'unknown'

def is_safe_url(target: str) -> bool:
    """
    Check if URL is safe for redirects
    
    Args:
        target: Target URL to check
        
    Returns:
        True if URL is safe
    """
    if not target:
        return False
    
    # Simple check - more sophisticated validation needed for production
    return target.startswith('/') and not target.startswith('//')

class MedicalTerminologyHelper:
    """Helper class for medical terminology operations"""
    
    @staticmethod
    def normalize_condition_name(condition: str) -> str:
        """Normalize condition name for consistent matching"""
        if not condition:
            return ''
        
        condition_lower = condition.lower().strip()
        
        # Common condition normalizations
        normalizations = {
            'diabetes mellitus': 'diabetes',
            'type 1 diabetes mellitus': 'type 1 diabetes',
            'type 2 diabetes mellitus': 'type 2 diabetes',
            'essential hypertension': 'hypertension',
            'high blood pressure': 'hypertension',
            'coronary artery disease': 'cad',
            'chronic obstructive pulmonary disease': 'copd'
        }
        
        return normalizations.get(condition_lower, condition_lower)
    
    @staticmethod
    def get_condition_synonyms(condition: str) -> List[str]:
        """Get list of synonyms for a medical condition"""
        condition_lower = condition.lower().strip()
        
        synonyms_map = {
            'diabetes': ['diabetes mellitus', 'dm', 'type 1 diabetes', 'type 2 diabetes'],
            'hypertension': ['high blood pressure', 'htn', 'elevated blood pressure'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'lipid disorder'],
            'cad': ['coronary artery disease', 'heart disease', 'coronary heart disease'],
            'copd': ['chronic obstructive pulmonary disease', 'emphysema']
        }
        
        return synonyms_map.get(condition_lower, [])
    
    @staticmethod
    def is_chronic_condition(condition: str) -> bool:
        """Check if condition is typically chronic"""
        condition_lower = condition.lower().strip()
        
        chronic_conditions = [
            'diabetes', 'hypertension', 'hyperlipidemia', 'cad', 'copd',
            'asthma', 'arthritis', 'osteoporosis', 'chronic kidney disease'
        ]
        
        return any(chronic in condition_lower for chronic in chronic_conditions)

class PrepSheetHelper:
    """Helper class for prep sheet operations"""
    
    @staticmethod
    def categorize_document_by_name(filename: str) -> str:
        """Categorize document based on filename"""
        if not filename:
            return 'other'
        
        filename_lower = filename.lower()
        
        categories = {
            'lab': ['lab', 'blood', 'urine', 'chemistry', 'hematology', 'microbiology'],
            'imaging': ['xray', 'ct', 'mri', 'ultrasound', 'mammogram', 'scan', 'radiology'],
            'consult': ['consult', 'specialist', 'referral', 'cardiology', 'endocrinology'],
            'hospital': ['discharge', 'admission', 'inpatient', 'hospital', 'er', 'emergency'],
            'screening': ['screening', 'mammogram', 'colonoscopy', 'dexa', 'pap']
        }
        
        for category, keywords in categories.items():
            if any(keyword in filename_lower for keyword in keywords):
                return category
        
        return 'other'
    
    @staticmethod
    def get_document_priority(document_type: str, document_date: date) -> int:
        """Get document priority for sorting (lower number = higher priority)"""
        priority_map = {
            'lab': 1,
            'screening': 2,
            'imaging': 3,
            'consult': 4,
            'hospital': 5,
            'other': 6
        }
        
        base_priority = priority_map.get(document_type, 6)
        
        # Boost priority for recent documents
        if document_date:
            days_old = (date.today() - document_date).days
            if days_old <= 7:
                base_priority -= 1
            elif days_old <= 30:
                base_priority -= 0.5
        
        return base_priority
"""
Utility functions for the screening application
"""

import json
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

def parse_keywords(keywords_string):
    """Parse comma-separated keywords string into a list"""
    if not keywords_string:
        return []
    
    # Split by comma and clean up
    keywords = [keyword.strip().lower() for keyword in keywords_string.split(',')]
    return [kw for kw in keywords if kw]  # Remove empty strings

def calculate_next_due_date(last_completed, frequency_value, frequency_unit):
    """Calculate when the next screening is due"""
    if not last_completed:
        return None
    
    if frequency_unit == 'days':
        return last_completed + timedelta(days=frequency_value)
    elif frequency_unit == 'months':
        return last_completed + relativedelta(months=frequency_value)
    elif frequency_unit == 'years':
        return last_completed + relativedelta(years=frequency_value)
    
    return None

def is_due_soon(next_due_date, days_threshold=30):
    """Check if a screening is due soon (within threshold days)"""
    if not next_due_date:
        return False
    
    today = datetime.now().date()
    threshold_date = today + timedelta(days=days_threshold)
    
    return today <= next_due_date <= threshold_date

def determine_screening_status(last_completed, frequency_value, frequency_unit):
    """Determine the current status of a screening"""
    if not last_completed:
        return 'due'
    
    next_due = calculate_next_due_date(last_completed, frequency_value, frequency_unit)
    if not next_due:
        return 'due'
    
    today = datetime.now().date()
    
    if next_due < today:
        return 'due'
    elif is_due_soon(next_due):
        return 'due_soon'
    else:
        return 'complete'

def format_frequency(frequency_value, frequency_unit):
    """Format frequency for display"""
    if frequency_value == 1:
        unit_map = {'days': 'day', 'months': 'month', 'years': 'year'}
        return f"Every {unit_map.get(frequency_unit, frequency_unit)}"
    else:
        return f"Every {frequency_value} {frequency_unit}"

def safe_json_loads(json_string, default=None):
    """Safely load JSON string, return default if invalid"""
    if default is None:
        default = []
    
    try:
        return json.loads(json_string) if json_string else default
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(data):
    """Safely dump data to JSON string"""
    try:
        return json.dumps(data) if data else None
    except (TypeError, ValueError):
        return None

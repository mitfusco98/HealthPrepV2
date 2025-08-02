"""
Utility functions for medical terminology and screening logic
"""
import re
import json
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional, Tuple

def parse_keywords_string(keywords_text: str) -> List[str]:
    """Parse keywords from text input (newline or comma separated)"""
    if not keywords_text:
        return []
    
    # Split by newlines first, then by commas
    keywords = []
    for line in keywords_text.split('\n'):
        line = line.strip()
        if line:
            # Split by commas and clean up
            for keyword in line.split(','):
                keyword = keyword.strip()
                if keyword:
                    keywords.append(keyword.lower())
    
    return list(set(keywords))  # Remove duplicates

def format_keywords_for_display(keywords: List[str]) -> str:
    """Format keywords list for display in forms"""
    if not keywords:
        return ""
    return '\n'.join(keywords)

def calculate_age(birth_date: date, reference_date: Optional[date] = None) -> int:
    """Calculate age from birth date"""
    if reference_date is None:
        reference_date = date.today()
    
    return reference_date.year - birth_date.year - (
        (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day)
    )

def get_next_due_date(last_date: date, frequency_value: int, frequency_unit: str) -> date:
    """Calculate next due date based on frequency"""
    if frequency_unit == 'years':
        return last_date + relativedelta(years=frequency_value)
    elif frequency_unit == 'months':
        return last_date + relativedelta(months=frequency_value)
    else:  # days
        return last_date + timedelta(days=frequency_value)

def get_screening_status(last_completed: Optional[date], frequency_value: int, frequency_unit: str) -> Tuple[str, Optional[date]]:
    """Determine screening status based on last completion and frequency"""
    if not last_completed:
        return 'Due', None
    
    next_due = get_next_due_date(last_completed, frequency_value, frequency_unit)
    today = date.today()
    
    if today >= next_due:
        return 'Due', next_due
    elif (next_due - today).days <= 30:  # Due within 30 days
        return 'Due Soon', next_due
    else:
        return 'Complete', next_due

def get_confidence_class(confidence: float) -> str:
    """Get CSS class based on confidence score"""
    if confidence >= 0.8:
        return 'confidence-high'
    elif confidence >= 0.5:
        return 'confidence-medium'
    else:
        return 'confidence-low'

def get_confidence_badge_class(confidence: float) -> str:
    """Get Bootstrap badge class based on confidence"""
    if confidence >= 0.8:
        return 'bg-success'
    elif confidence >= 0.5:
        return 'bg-warning'
    else:
        return 'bg-danger'

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    if not filename:
        return "unnamed_file"
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove excessive dots and spaces
    filename = re.sub(r'\.{2,}', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    
    # Ensure reasonable length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_len] + ('.' + ext if ext else '')
    
    return filename

def extract_medical_terms(text: str) -> List[str]:
    """Extract potential medical terms from text"""
    if not text:
        return []
    
    # Common medical term patterns
    medical_patterns = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Capitalized terms
        r'\b\w+(?:gram|graphy|scopy|metry)\b',   # Medical procedure suffixes
        r'\b\w+(?:ology|osis|itis|emia)\b',     # Medical condition suffixes
        r'\b[A-Z]{2,}\b',                        # Abbreviations
        r'\b\d+\.\d+\s*(?:mg|ml|mcg|IU)/\w+\b', # Dosages
        r'\b\d+/\d+\s*mmHg\b',                   # Blood pressure
    ]
    
    terms = []
    for pattern in medical_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        terms.extend(matches)
    
    # Filter out common non-medical words
    common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    medical_terms = [term for term in terms if term.lower() not in common_words]
    
    return list(set(medical_terms))  # Remove duplicates

def normalize_medical_term(term: str) -> str:
    """Normalize medical term for consistent matching"""
    if not term:
        return ""
    
    # Convert to lowercase
    normalized = term.lower().strip()
    
    # Common medical abbreviation expansions
    abbreviations = {
        'bp': 'blood pressure',
        'hr': 'heart rate',
        'temp': 'temperature',
        'wbc': 'white blood count',
        'rbc': 'red blood count',
        'hgb': 'hemoglobin',
        'hct': 'hematocrit',
        'plt': 'platelet',
        'bun': 'blood urea nitrogen',
        'cr': 'creatinine',
        'na': 'sodium',
        'k': 'potassium',
        'cl': 'chloride',
        'co2': 'carbon dioxide'
    }
    
    if normalized in abbreviations:
        normalized = abbreviations[normalized]
    
    return normalized

def get_document_type_icon(doc_type: str) -> str:
    """Get Font Awesome icon for document type"""
    icons = {
        'lab': 'fa-flask',
        'imaging': 'fa-x-ray',
        'consult': 'fa-user-md',
        'hospital': 'fa-hospital',
        'general': 'fa-file-medical',
        'condition': 'fa-heartbeat'
    }
    return icons.get(doc_type, 'fa-file')

def get_screening_status_badge(status: str) -> str:
    """Get Bootstrap badge class for screening status"""
    badges = {
        'Complete': 'bg-success',
        'Due Soon': 'bg-warning',
        'Due': 'bg-danger'
    }
    return badges.get(status, 'bg-secondary')

def format_frequency(value: int, unit: str) -> str:
    """Format frequency for display"""
    if value == 1:
        unit_singular = {
            'days': 'day',
            'months': 'month',
            'years': 'year'
        }
        return f"Every {unit_singular.get(unit, unit)}"
    else:
        return f"Every {value} {unit}"

def parse_trigger_conditions(conditions_text: str) -> List[str]:
    """Parse trigger conditions from text input"""
    if not conditions_text:
        return []
    
    conditions = []
    for line in conditions_text.split('\n'):
        line = line.strip()
        if line:
            # Split by commas and clean up
            for condition in line.split(','):
                condition = condition.strip()
                if condition:
                    conditions.append(normalize_medical_term(condition))
    
    return list(set(conditions))  # Remove duplicates

def calculate_cutoff_date(cutoff_months: int) -> datetime:
    """Calculate cutoff date for filtering data"""
    return datetime.utcnow() - timedelta(days=cutoff_months * 30)

def is_within_cutoff(target_date: datetime, cutoff_months: int) -> bool:
    """Check if date is within cutoff period"""
    cutoff = calculate_cutoff_date(cutoff_months)
    return target_date >= cutoff

def get_time_ago_string(target_date: datetime) -> str:
    """Get human-readable time ago string"""
    now = datetime.utcnow()
    diff = now - target_date
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def validate_medical_record_number(mrn: str) -> bool:
    """Validate MRN format"""
    if not mrn:
        return False
    
    # Basic MRN validation - alphanumeric with optional hyphens
    return bool(re.match(r'^[A-Za-z0-9\-]{3,50}$', mrn))

def generate_unique_filename(original_filename: str, patient_id: int) -> str:
    """Generate unique filename for uploaded documents"""
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    sanitized = sanitize_filename(original_filename)
    
    name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
    
    unique_filename = f"patient_{patient_id}_{timestamp}_{name}"
    if ext:
        unique_filename += f".{ext}"
    
    return unique_filename

def batch_process_items(items: List, batch_size: int = 100):
    """Process items in batches to avoid memory issues"""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

def safe_json_loads(json_string: str, default=None):
    """Safely load JSON string with fallback"""
    if not json_string:
        return default or []
    
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        logging.warning(f"Failed to parse JSON: {json_string}")
        return default or []

def safe_json_dumps(data, default="[]"):
    """Safely dump data to JSON with fallback"""
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logging.warning(f"Failed to serialize JSON: {e}")
        return default


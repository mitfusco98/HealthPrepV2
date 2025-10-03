"""
Utility functions for HealthPrep application
"""
import os
import re
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Union, Any
from dateutil.relativedelta import relativedelta
import secrets
import string

logger = logging.getLogger(__name__)

def calculate_age(birth_date: date, reference_date: date = None) -> int:
    """
    Calculate age from birth date
    
    Args:
        birth_date: Date of birth
        reference_date: Reference date (defaults to today)
        
    Returns:
        Age in years
    """
    if reference_date is None:
        reference_date = date.today()
    
    age = reference_date.year - birth_date.year
    
    # Adjust if birthday hasn't occurred this year
    if (reference_date.month < birth_date.month or 
        (reference_date.month == birth_date.month and reference_date.day < birth_date.day)):
        age -= 1
    
    return age

def format_confidence_level(confidence: float) -> str:
    """
    Format confidence as a level string
    
    Args:
        confidence: Numeric confidence (0-100)
        
    Returns:
        Confidence level string
    """
    if confidence >= 80:
        return 'high'
    elif confidence >= 60:
        return 'medium'
    else:
        return 'low'

def get_confidence_class(confidence: float) -> str:
    """
    Get Bootstrap class for confidence level
    
    Args:
        confidence: Numeric confidence (0-100)
        
    Returns:
        Bootstrap class name
    """
    confidence_classes = {
        'high': 'success',
        'medium': 'warning',
        'low': 'danger'
    }
    level = format_confidence_level(confidence)
    return confidence_classes.get(level, 'secondary')

def format_screening_status(status: str) -> Dict[str, str]:
    """
    Format screening status for display
    
    Args:
        status: Screening status
        
    Returns:
        Dictionary with status formatting info
    """
    status_formats = {
        'Due': {'class': 'danger', 'icon': 'exclamation-circle', 'label': 'Due'},
        'Due Soon': {'class': 'warning', 'icon': 'clock', 'label': 'Due Soon'},
        'Complete': {'class': 'success', 'icon': 'check-circle', 'label': 'Complete'}
    }
    
    return status_formats.get(status, {
        'class': 'secondary', 
        'icon': 'question-circle', 
        'label': status
    })

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)
    
    # Replace potentially dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename

def generate_unique_filename(original_filename: str, directory: str = None) -> str:
    """
    Generate unique filename to avoid collisions
    
    Args:
        original_filename: Original filename
        directory: Directory to check for existing files
        
    Returns:
        Unique filename
    """
    # Sanitize the filename
    filename = sanitize_filename(original_filename)
    
    if not directory:
        return filename
    
    # Check if file exists
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        return filename
    
    # Generate unique variant
    name, ext = os.path.splitext(filename)
    counter = 1
    
    while os.path.exists(filepath):
        new_filename = f"{name}_{counter}{ext}"
        filepath = os.path.join(directory, new_filename)
        counter += 1
    
    return os.path.basename(filepath)

def parse_keywords(keywords_string: str) -> List[str]:
    """
    Parse comma-separated keywords string
    
    Args:
        keywords_string: Comma-separated keywords
        
    Returns:
        List of cleaned keywords
    """
    if not keywords_string:
        return []
    
    keywords = []
    for keyword in keywords_string.split(','):
        keyword = keyword.strip().lower()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    
    return keywords

def format_keywords_string(keywords: List[str]) -> str:
    """
    Format list of keywords as comma-separated string
    
    Args:
        keywords: List of keywords
        
    Returns:
        Comma-separated string
    """
    if not keywords:
        return ""
    
    return ", ".join(str(k) for k in keywords)

def calculate_due_date(last_date: date, frequency_years: float) -> date:
    """
    Calculate when screening is next due
    
    Args:
        last_date: Date of last screening
        frequency_years: Frequency in years
        
    Returns:
        Next due date
    """
    if not last_date or not frequency_years:
        return date.today()
    
    # Use relativedelta for more accurate date calculations
    return last_date + relativedelta(years=int(frequency_years), 
                                   months=int((frequency_years % 1) * 12))

def get_screening_status(last_date: Optional[date], frequency_years: Optional[float]) -> str:
    """
    Determine screening status based on last date and frequency
    
    Args:
        last_date: Date of last screening
        frequency_years: Frequency in years
        
    Returns:
        Screening status ('Due', 'Due Soon', 'Complete')
    """
    if not last_date or not frequency_years:
        return 'Due'
    
    today = date.today()
    next_due = calculate_due_date(last_date, frequency_years)
    
    # Calculate "due soon" threshold (30 days before next due date)
    due_soon_threshold = next_due - timedelta(days=30)
    
    if today >= next_due:
        return 'Due'
    elif today >= due_soon_threshold:
        return 'Due Soon'
    else:
        return 'Complete'

def format_date_range(start_date: date, end_date: date) -> str:
    """
    Format date range for display
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Formatted date range string
    """
    if start_date == end_date:
        return start_date.strftime('%B %d, %Y')
    
    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return f"{start_date.strftime('%B %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    else:
        return f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def extract_medical_terms(text: str) -> List[str]:
    """
    Extract potential medical terms from text
    
    Args:
        text: Text to analyze
        
    Returns:
        List of potential medical terms
    """
    if not text:
        return []
    
    # Common medical term patterns
    medical_patterns = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Capitalized terms
        r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|L|mmol|IU)\b',  # Measurements
        r'\b\d+/\d+\s*mmHg\b',  # Blood pressure
        r'\b\d+\.\d+\s*%\b',  # Percentages
    ]
    
    terms = []
    for pattern in medical_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        terms.extend(matches)
    
    # Remove duplicates and return
    return list(set(terms))

def validate_mrn(mrn: str) -> bool:
    """
    Validate Medical Record Number format
    
    Args:
        mrn: MRN to validate
        
    Returns:
        True if valid format
    """
    if not mrn:
        return False
    
    # Basic validation - alphanumeric, 6-12 characters
    return bool(re.match(r'^[A-Za-z0-9]{6,12}$', mrn))

def generate_session_token() -> str:
    """
    Generate secure session token
    
    Returns:
        Random session token
    """
    return secrets.token_urlsafe(32)

def mask_phi(text: str, mask_char: str = '*') -> str:
    """
    Mask PHI in text for display
    
    Args:
        text: Text containing PHI
        mask_char: Character to use for masking
        
    Returns:
        Text with PHI masked
    """
    if not text:
        return text
    
    # Mask potential SSN patterns
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', f'{mask_char*3}-{mask_char*2}-{mask_char*4}', text)
    
    # Mask potential phone numbers
    text = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', f'{mask_char*3}-{mask_char*3}-{mask_char*4}', text)
    
    # Mask potential MRNs
    text = re.sub(r'\b(?:MRN|Medical Record)[:]\s*\w+\b', f'MRN: {mask_char*8}', text)
    
    return text

def format_processing_time(seconds: float) -> str:
    """
    Format processing time for display
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"

def get_document_icon(document_type: str) -> str:
    """
    Get Font Awesome icon for document type
    
    Args:
        document_type: Type of document
        
    Returns:
        Font Awesome icon class
    """
    icons = {
        'lab': 'flask',
        'imaging': 'x-ray',
        'consult': 'user-md',
        'hospital': 'hospital',
        'pdf': 'file-pdf',
        'image': 'file-image'
    }
    
    return icons.get(document_type, 'file-alt')

def create_breadcrumb(path_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Create breadcrumb navigation items
    
    Args:
        path_items: List of path items with 'name' and 'url' keys
        
    Returns:
        Formatted breadcrumb items
    """
    breadcrumb = []
    
    for i, item in enumerate(path_items):
        breadcrumb.append({
            'name': item['name'],
            'url': item.get('url'),
            'active': i == len(path_items) - 1
        })
    
    return breadcrumb

def safe_divide(numerator: Union[int, float], denominator: Union[int, float], 
               default: Union[int, float] = 0) -> Union[int, float]:
    """
    Safely divide two numbers, handling division by zero
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if division by zero
        
    Returns:
        Division result or default
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default

def parse_date_string(date_string: str, formats: List[str] = None) -> Optional[date]:
    """
    Parse date string with multiple format attempts
    
    Args:
        date_string: Date string to parse
        formats: List of formats to try
        
    Returns:
        Parsed date or None
    """
    if not date_string:
        return None
    
    if formats is None:
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S'
        ]
    
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt).date()
            return parsed_date
        except ValueError:
            continue
    
    return None

def get_time_period_description(days: int) -> str:
    """
    Get human-readable description of time period
    
    Args:
        days: Number of days
        
    Returns:
        Description string
    """
    if days == 1:
        return "1 day"
    elif days == 7:
        return "1 week"
    elif days == 30:
        return "1 month"
    elif days == 90:
        return "3 months"
    elif days == 365:
        return "1 year"
    elif days < 30:
        return f"{days} days"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''}"
    else:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''}"

def fuzzy_match_score(text1: str, text2: str) -> float:
    """
    Calculate fuzzy match score between two strings
    
    Args:
        text1: First string
        text2: Second string
        
    Returns:
        Match score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    text1 = text1.lower().strip()
    text2 = text2.lower().strip()
    
    if text1 == text2:
        return 1.0
    
    # Simple fuzzy matching based on common characters
    common_chars = set(text1) & set(text2)
    total_chars = set(text1) | set(text2)
    
    if not total_chars:
        return 0.0
    
    return len(common_chars) / len(total_chars)

def generate_random_password(length: int = 12) -> str:
    """
    Generate random password
    
    Args:
        length: Password length
        
    Returns:
        Random password
    """
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(length))

def log_execution_time(func):
    """
    Decorator to log function execution time
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.debug(f"{func.__name__} executed in {format_processing_time(execution_time)}")
        return result
    
    return wrapper

def clean_medical_text(text: str) -> str:
    """
    Clean medical text for better processing
    
    Args:
        text: Raw medical text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common OCR artifacts
    text = re.sub(r'[^\w\s\.\,\;\:\(\)\[\]\-\+\%\/]', '', text)
    
    # Fix common medical abbreviations
    replacements = {
        r'\bw\/': 'with',
        r'\bw\/o': 'without',
        r'\bs\/p': 'status post',
        r'\bc\/o': 'complains of',
        r'\bh\/o': 'history of'
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.strip()

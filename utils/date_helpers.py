"""
Date and time utility functions for Health-Prep system.
Handles screening frequency calculations and date formatting.
"""

from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

def calculate_due_date(last_completed: date, frequency_number: int, frequency_unit: str) -> date:
    """Calculate next due date based on last completion and frequency"""
    if not last_completed:
        return date.today()
    
    try:
        if frequency_unit == 'days':
            return last_completed + timedelta(days=frequency_number)
        elif frequency_unit == 'months':
            return last_completed + relativedelta(months=frequency_number)
        elif frequency_unit == 'years':
            return last_completed + relativedelta(years=frequency_number)
        else:
            logger.warning(f"Unknown frequency unit: {frequency_unit}, defaulting to years")
            return last_completed + relativedelta(years=frequency_number)
            
    except Exception as e:
        logger.error(f"Error calculating due date: {str(e)}")
        return date.today()

def get_frequency_delta(frequency_number: int, frequency_unit: str) -> timedelta:
    """Convert frequency to timedelta for calculations"""
    try:
        if frequency_unit == 'days':
            return timedelta(days=frequency_number)
        elif frequency_unit == 'months':
            # Approximate months as 30 days for timedelta
            return timedelta(days=frequency_number * 30)
        elif frequency_unit == 'years':
            # Approximate years as 365 days for timedelta
            return timedelta(days=frequency_number * 365)
        else:
            logger.warning(f"Unknown frequency unit: {frequency_unit}, defaulting to 365 days")
            return timedelta(days=365)
            
    except Exception as e:
        logger.error(f"Error converting frequency to delta: {str(e)}")
        return timedelta(days=365)

def calculate_age(birth_date: date, reference_date: date = None) -> int:
    """Calculate age in years from birth date"""
    if not birth_date:
        return 0
    
    if reference_date is None:
        reference_date = date.today()
    
    try:
        age = reference_date.year - birth_date.year
        
        # Adjust if birthday hasn't occurred this year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return max(0, age)  # Ensure non-negative age
        
    except Exception as e:
        logger.error(f"Error calculating age: {str(e)}")
        return 0

def days_until_due(due_date: date, reference_date: date = None) -> int:
    """Calculate days until due date"""
    if not due_date:
        return 0
    
    if reference_date is None:
        reference_date = date.today()
    
    try:
        delta = due_date - reference_date
        return delta.days
        
    except Exception as e:
        logger.error(f"Error calculating days until due: {str(e)}")
        return 0

def is_overdue(due_date: date, reference_date: date = None) -> bool:
    """Check if a screening is overdue"""
    if not due_date:
        return True
    
    if reference_date is None:
        reference_date = date.today()
    
    return due_date < reference_date

def is_due_soon(due_date: date, days_threshold: int = 30, reference_date: date = None) -> bool:
    """Check if a screening is due soon (within threshold days)"""
    if not due_date:
        return True
    
    if reference_date is None:
        reference_date = date.today()
    
    days_until = days_until_due(due_date, reference_date)
    return 0 <= days_until <= days_threshold

def format_date(date_obj: Optional[date], format_str: str = "%Y-%m-%d") -> str:
    """Format date object to string"""
    if not date_obj:
        return "N/A"
    
    try:
        return date_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting date {date_obj}: {str(e)}")
        return "Invalid Date"

def format_datetime(datetime_obj: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime object to string"""
    if not datetime_obj:
        return "N/A"
    
    try:
        return datetime_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting datetime {datetime_obj}: {str(e)}")
        return "Invalid DateTime"

def parse_date(date_str: str, format_str: str = "%Y-%m-%d") -> Optional[date]:
    """Parse date string to date object"""
    if not date_str or date_str.lower() in ['n/a', 'none', 'null', '']:
        return None
    
    try:
        return datetime.strptime(date_str, format_str).date()
    except ValueError:
        # Try alternative formats
        alternative_formats = [
            "%m/%d/%Y",
            "%m-%d-%Y", 
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y"
        ]
        
        for alt_format in alternative_formats:
            try:
                return datetime.strptime(date_str, alt_format).date()
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date string: {date_str}")
        return None

def parse_datetime(datetime_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """Parse datetime string to datetime object"""
    if not datetime_str or datetime_str.lower() in ['n/a', 'none', 'null', '']:
        return None
    
    try:
        return datetime.strptime(datetime_str, format_str)
    except ValueError:
        # Try alternative formats
        alternative_formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S"
        ]
        
        for alt_format in alternative_formats:
            try:
                return datetime.strptime(datetime_str, alt_format)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime string: {datetime_str}")
        return None

def get_date_range_for_cutoff(cutoff_months: int, reference_date: date = None) -> Tuple[date, date]:
    """Get date range for document filtering based on cutoff months"""
    if reference_date is None:
        reference_date = date.today()
    
    try:
        start_date = reference_date - relativedelta(months=cutoff_months)
        return start_date, reference_date
        
    except Exception as e:
        logger.error(f"Error calculating date range for cutoff: {str(e)}")
        # Fallback to simple calculation
        days_cutoff = cutoff_months * 30
        start_date = reference_date - timedelta(days=days_cutoff)
        return start_date, reference_date

def get_frequency_description(frequency_number: int, frequency_unit: str) -> str:
    """Get human-readable frequency description"""
    if frequency_number == 1:
        unit_singular = {
            'days': 'day',
            'months': 'month', 
            'years': 'year'
        }
        return f"Every {unit_singular.get(frequency_unit, frequency_unit)}"
    else:
        return f"Every {frequency_number} {frequency_unit}"

def calculate_screening_window(last_completed: date, frequency_number: int, 
                             frequency_unit: str, grace_period_days: int = 30) -> Tuple[date, date, date]:
    """
    Calculate screening window dates:
    - Due date: When screening should be completed
    - Grace end: Latest acceptable completion date
    - Next due: When next screening cycle starts
    """
    if not last_completed:
        today = date.today()
        return today, today, today
    
    try:
        due_date = calculate_due_date(last_completed, frequency_number, frequency_unit)
        grace_end = due_date + timedelta(days=grace_period_days)
        next_due = calculate_due_date(due_date, frequency_number, frequency_unit)
        
        return due_date, grace_end, next_due
        
    except Exception as e:
        logger.error(f"Error calculating screening window: {str(e)}")
        today = date.today()
        return today, today, today

def get_quarters_in_range(start_date: date, end_date: date) -> List[Tuple[date, date]]:
    """Get quarterly date ranges within a given period"""
    quarters = []
    
    try:
        current_date = start_date.replace(day=1)  # Start at beginning of month
        
        while current_date <= end_date:
            # Calculate quarter start
            quarter_start_month = ((current_date.month - 1) // 3) * 3 + 1
            quarter_start = current_date.replace(month=quarter_start_month, day=1)
            
            # Calculate quarter end
            if quarter_start_month == 10:  # Q4
                quarter_end = quarter_start.replace(year=quarter_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                quarter_end = quarter_start.replace(month=quarter_start_month + 3, day=1) - timedelta(days=1)
            
            # Adjust to fit within range
            actual_start = max(quarter_start, start_date)
            actual_end = min(quarter_end, end_date)
            
            if actual_start <= actual_end:
                quarters.append((actual_start, actual_end))
            
            # Move to next quarter
            current_date = quarter_end + timedelta(days=1)
        
        return quarters
        
    except Exception as e:
        logger.error(f"Error calculating quarters: {str(e)}")
        return [(start_date, end_date)]

def get_business_days_between(start_date: date, end_date: date) -> int:
    """Calculate business days between two dates (excluding weekends)"""
    if not start_date or not end_date:
        return 0
    
    try:
        business_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday to Friday
                business_days += 1
            current_date += timedelta(days=1)
        
        return business_days
        
    except Exception as e:
        logger.error(f"Error calculating business days: {str(e)}")
        return 0

def format_time_ago(target_date: date, reference_date: date = None) -> str:
    """Format how long ago a date was in human-readable format"""
    if not target_date:
        return "Unknown"
    
    if reference_date is None:
        reference_date = date.today()
    
    try:
        delta = reference_date - target_date
        days = delta.days
        
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
            
    except Exception as e:
        logger.error(f"Error formatting time ago: {str(e)}")
        return "Unknown"

def get_age_group(age: int) -> str:
    """Categorize age into groups for screening recommendations"""
    if age < 18:
        return "Pediatric"
    elif age < 35:
        return "Young Adult"
    elif age < 50:
        return "Adult"
    elif age < 65:
        return "Middle Age"
    elif age < 80:
        return "Senior"
    else:
        return "Elderly"

def validate_date_range(start_date: date, end_date: date) -> bool:
    """Validate that date range is logical"""
    if not start_date or not end_date:
        return False
    
    try:
        return start_date <= end_date
    except Exception as e:
        logger.error(f"Error validating date range: {str(e)}")
        return False

class DateCalculator:
    """Advanced date calculations for medical scheduling"""
    
    @staticmethod
    def next_screening_dates(screening_frequency: str, last_completed: date = None, 
                           count: int = 5) -> List[date]:
        """Calculate next several screening dates"""
        if not last_completed:
            last_completed = date.today()
        
        # Parse frequency string (e.g., "1 years", "6 months")
        try:
            parts = screening_frequency.split()
            if len(parts) >= 2:
                frequency_number = int(parts[0])
                frequency_unit = parts[1]
            else:
                frequency_number = 1
                frequency_unit = "years"
        except:
            frequency_number = 1
            frequency_unit = "years"
        
        dates = []
        current_date = last_completed
        
        for i in range(count):
            next_date = calculate_due_date(current_date, frequency_number, frequency_unit)
            dates.append(next_date)
            current_date = next_date
        
        return dates
    
    @staticmethod
    def calculate_compliance_percentage(completed_screenings: int, due_screenings: int) -> float:
        """Calculate compliance percentage for screenings"""
        if due_screenings == 0:
            return 100.0
        
        return min(100.0, (completed_screenings / due_screenings) * 100)
    
    @staticmethod
    def days_in_frequency_period(frequency_number: int, frequency_unit: str) -> int:
        """Calculate approximate days in a frequency period"""
        if frequency_unit == 'days':
            return frequency_number
        elif frequency_unit == 'months':
            return frequency_number * 30
        elif frequency_unit == 'years':
            return frequency_number * 365
        else:
            return 365  # Default to one year

# Create global instance
date_calculator = DateCalculator()


# ============================================================================
# TIMEZONE-AWARE DORMANCY HELPERS
# For calculating local midnight rollover for screening dormancy/staleness
# ============================================================================

from zoneinfo import ZoneInfo
from datetime import time as dt_time, timezone as dt_timezone

# Common US healthcare timezone mappings from Epic location data
# Epic may return state abbreviations or city names that we map to IANA timezones
LOCATION_TO_TIMEZONE = {
    # US States/Regions
    'eastern': 'America/New_York',
    'central': 'America/Chicago',
    'mountain': 'America/Denver',
    'pacific': 'America/Los_Angeles',
    'alaska': 'America/Anchorage',
    'hawaii': 'Pacific/Honolulu',
    # Common state abbreviations
    'ny': 'America/New_York',
    'ca': 'America/Los_Angeles',
    'tx': 'America/Chicago',
    'fl': 'America/New_York',
    'il': 'America/Chicago',
    'pa': 'America/New_York',
    'oh': 'America/New_York',
    'ga': 'America/New_York',
    'nc': 'America/New_York',
    'mi': 'America/New_York',
    'nj': 'America/New_York',
    'va': 'America/New_York',
    'wa': 'America/Los_Angeles',
    'az': 'America/Phoenix',
    'ma': 'America/New_York',
    'tn': 'America/Chicago',
    'in': 'America/Indiana/Indianapolis',
    'mo': 'America/Chicago',
    'md': 'America/New_York',
    'wi': 'America/Chicago',
    'co': 'America/Denver',
    'mn': 'America/Chicago',
    'sc': 'America/New_York',
    'al': 'America/Chicago',
    'la': 'America/Chicago',
    'ky': 'America/New_York',
    'or': 'America/Los_Angeles',
    'ok': 'America/Chicago',
    'ct': 'America/New_York',
    'ut': 'America/Denver',
    'ia': 'America/Chicago',
    'nv': 'America/Los_Angeles',
    'ar': 'America/Chicago',
    'ms': 'America/Chicago',
    'ks': 'America/Chicago',
    'nm': 'America/Denver',
    'ne': 'America/Chicago',
    'id': 'America/Boise',
    'wv': 'America/New_York',
    'hi': 'Pacific/Honolulu',
    'nh': 'America/New_York',
    'me': 'America/New_York',
    'mt': 'America/Denver',
    'ri': 'America/New_York',
    'de': 'America/New_York',
    'sd': 'America/Chicago',
    'nd': 'America/Chicago',
    'ak': 'America/Anchorage',
    'dc': 'America/New_York',
    'vt': 'America/New_York',
    'wy': 'America/Denver',
}


def get_timezone_from_location(location_hint: str) -> str:
    """
    Convert a location hint (state, city, region) to an IANA timezone.
    
    Args:
        location_hint: Location string from Epic (e.g., 'NY', 'Eastern', 'California')
    
    Returns:
        IANA timezone string (e.g., 'America/New_York'), defaults to 'UTC' if unknown
    """
    if not location_hint:
        return 'UTC'
    
    normalized = location_hint.lower().strip()
    
    # Direct lookup
    if normalized in LOCATION_TO_TIMEZONE:
        return LOCATION_TO_TIMEZONE[normalized]
    
    # Check if it's already a valid IANA timezone
    try:
        ZoneInfo(location_hint)
        return location_hint
    except (KeyError, ValueError):
        pass
    
    # Try partial matching for common patterns
    for key, tz in LOCATION_TO_TIMEZONE.items():
        if key in normalized or normalized in key:
            return tz
    
    logger.warning(f"Could not determine timezone from location hint: {location_hint}, defaulting to UTC")
    return 'UTC'


def get_org_zoneinfo(org_timezone: str) -> ZoneInfo:
    """
    Get a ZoneInfo object for an organization's timezone.
    
    Args:
        org_timezone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        ZoneInfo object, falls back to UTC if invalid timezone
    """
    if not org_timezone:
        return ZoneInfo('UTC')
    
    try:
        return ZoneInfo(org_timezone)
    except (KeyError, ValueError) as e:
        logger.warning(f"Invalid timezone '{org_timezone}', falling back to UTC: {e}")
        return ZoneInfo('UTC')


def get_local_midnight_utc(org_timezone: str = 'UTC') -> datetime:
    """
    Get the current day's local midnight as a UTC datetime.
    
    This is the key function for dormancy rollover - it calculates when
    "today" started in the organization's local timezone, then converts
    that to UTC for comparison with stored UTC timestamps.
    
    Args:
        org_timezone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        UTC datetime representing midnight in the org's local timezone
    
    Example:
        For org in 'America/New_York' (EST, UTC-5):
        - Local midnight Jan 10 = 2026-01-10 00:00:00 EST
        - Converted to UTC = 2026-01-10 05:00:00 UTC
        
        So a screening with last_processed = 2026-01-09 23:00:00 UTC
        would be < today_start_utc (05:00 UTC) and show as dormant.
    """
    zone = get_org_zoneinfo(org_timezone)
    
    # Get current time in the org's timezone
    now_local = datetime.now(zone)
    
    # Get midnight (start of today) in the org's timezone
    midnight_local = datetime.combine(now_local.date(), dt_time.min, tzinfo=zone)
    
    # Convert to UTC for database comparison
    midnight_utc = midnight_local.astimezone(dt_timezone.utc).replace(tzinfo=None)
    
    return midnight_utc


def get_org_local_now(org_timezone: str = 'UTC') -> datetime:
    """
    Get the current time in the organization's local timezone (timezone-aware).
    
    Args:
        org_timezone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        Timezone-aware datetime in the org's local timezone
    """
    zone = get_org_zoneinfo(org_timezone)
    return datetime.now(zone)


def format_timezone_display(org_timezone: str) -> str:
    """
    Get a human-readable timezone display string.
    
    Args:
        org_timezone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        Human-readable string (e.g., 'Eastern Time')
    """
    timezone_display_names = {
        'America/New_York': 'Eastern Time',
        'America/Chicago': 'Central Time',
        'America/Denver': 'Mountain Time',
        'America/Los_Angeles': 'Pacific Time',
        'America/Anchorage': 'Alaska Time',
        'Pacific/Honolulu': 'Hawaii Time',
        'America/Phoenix': 'Arizona Time',
        'UTC': 'UTC',
    }
    
    return timezone_display_names.get(org_timezone, org_timezone)


def get_local_today(org_timezone: str = 'UTC') -> date:
    """
    Get today's date in the organization's local timezone.
    
    This is used for encounter date comparisons to determine if an encounter
    occurred before, on, or after today (for "To Last Encounter" prep sheet cutoffs).
    
    Args:
        org_timezone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        Today's date in the organization's local timezone
    """
    zone = get_org_zoneinfo(org_timezone)
    return datetime.now(zone).date()

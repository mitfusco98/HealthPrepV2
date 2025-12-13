"""
Keyword Validator Utility
Validates screening type keywords to prevent abuse and performance issues.
Blocks common stop words and overly generic terms that would match too many documents.
"""

import re
import logging
from typing import List, Tuple, Set

logger = logging.getLogger(__name__)

# Comprehensive stop word list - common words that would match nearly every document
STOP_WORDS: Set[str] = {
    # English articles and pronouns
    'a', 'an', 'the', 'this', 'that', 'these', 'those',
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
    'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'ours', 'theirs',
    
    # Common conjunctions and prepositions
    'and', 'or', 'but', 'if', 'then', 'so', 'as', 'of', 'to', 'for', 'with',
    'in', 'on', 'at', 'by', 'from', 'up', 'out', 'into', 'over', 'after',
    'before', 'between', 'under', 'above', 'below', 'through', 'during',
    
    # Common verbs
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'must', 'shall', 'get', 'got', 'see', 'saw', 'go', 'went', 'come',
    
    # Common adverbs
    'not', 'no', 'yes', 'very', 'just', 'only', 'also', 'now', 'here', 'there',
    'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'some', 'such', 'than', 'too', 'any', 'well',
    
    # Time-related common words
    'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years',
    'today', 'yesterday', 'tomorrow', 'time', 'date', 'pm', 'am',
    
    # Common medical document terms that are too generic
    'patient', 'patients', 'doctor', 'dr', 'md', 'nurse', 'staff',
    'name', 'age', 'sex', 'male', 'female', 'dob', 'mrn',
    'note', 'notes', 'report', 'reports', 'record', 'records',
    'result', 'results', 'finding', 'findings', 'value', 'values',
    'review', 'reviewed', 'clinic', 'clinics', 'office', 'visit', 'visits',
    'test', 'tests', 'testing', 'exam', 'exams', 'examination',
    'screening', 'screenings', 'procedure', 'procedures',
    'imaging', 'image', 'images', 'scan', 'scans',
    'normal', 'abnormal', 'negative', 'positive', 'pending',
    'history', 'hx', 'medical', 'health', 'healthcare', 'clinical',
    'diagnosis', 'dx', 'treatment', 'tx', 'medication', 'med', 'meds',
    'provider', 'providers', 'physician', 'physicians',
    'department', 'dept', 'unit', 'floor', 'room',
    'hospital', 'facility', 'center', 'centre',
    'please', 'thank', 'thanks', 'sincerely', 'regards',
    'page', 'pages', 'document', 'documents', 'file', 'files',
    'print', 'printed', 'copy', 'copies', 'fax', 'faxed',
    'signed', 'signature', 'electronically', 'approved',
    
    # Common numbers and measurements (as words)
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'first', 'second', 'third', 'last', 'next', 'previous',
    
    # Common abbreviations
    'etc', 'ie', 'eg', 'vs', 'na', 'n/a', 'tbd', 'asap',
}

# Minimum keyword length (characters)
MIN_KEYWORD_LENGTH = 3

# Maximum keywords per screening type
MAX_KEYWORDS_PER_SCREENING = 50

# Maximum match count before warning/throttling
MAX_MATCHES_WARNING_THRESHOLD = 500
MAX_MATCHES_HARD_LIMIT = 1000


class KeywordValidationError(Exception):
    """Exception raised when keyword validation fails"""
    def __init__(self, message: str, invalid_keywords: List[str] | None = None):
        self.message = message
        self.invalid_keywords = invalid_keywords if invalid_keywords is not None else []
        super().__init__(self.message)


def validate_keyword(keyword: str) -> Tuple[bool, str]:
    """
    Validate a single keyword.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not keyword or not isinstance(keyword, str):
        return False, "Keyword cannot be empty"
    
    keyword_clean = keyword.strip().lower()
    
    if not keyword_clean:
        return False, "Keyword cannot be empty or whitespace only"
    
    # Check minimum length (for single-word keywords)
    words = keyword_clean.split()
    if len(words) == 1 and len(keyword_clean) < MIN_KEYWORD_LENGTH:
        return False, f"Single-word keywords must be at least {MIN_KEYWORD_LENGTH} characters"
    
    # Check if it's a stop word
    if keyword_clean in STOP_WORDS:
        return False, f"'{keyword}' is too common and would match too many documents"
    
    # For multi-word keywords, check if ALL words are stop words
    if len(words) > 1:
        non_stop_words = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_KEYWORD_LENGTH]
        if not non_stop_words:
            return False, f"'{keyword}' contains only common words that would match too many documents"
    
    # Check for purely numeric keywords
    if keyword_clean.replace('.', '').replace('-', '').isdigit():
        return False, f"'{keyword}' is purely numeric and would cause too many matches"
    
    return True, ""


def validate_keywords(keywords: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Validate a list of keywords.
    
    Returns:
        Tuple of (valid_keywords, list of (invalid_keyword, reason) tuples)
    """
    if not keywords:
        return [], []
    
    valid_keywords = []
    invalid_keywords = []
    
    # Check max count
    if len(keywords) > MAX_KEYWORDS_PER_SCREENING:
        # Still validate them but note the excess
        logger.warning(f"Too many keywords provided ({len(keywords)}), max is {MAX_KEYWORDS_PER_SCREENING}")
    
    seen = set()
    for keyword in keywords:
        keyword_clean = keyword.strip()
        keyword_lower = keyword_clean.lower()
        
        # Skip duplicates (case-insensitive)
        if keyword_lower in seen:
            continue
        seen.add(keyword_lower)
        
        is_valid, error = validate_keyword(keyword_clean)
        if is_valid:
            valid_keywords.append(keyword_clean)
        else:
            invalid_keywords.append((keyword, error))
    
    # Enforce max limit on valid keywords
    if len(valid_keywords) > MAX_KEYWORDS_PER_SCREENING:
        excess = valid_keywords[MAX_KEYWORDS_PER_SCREENING:]
        valid_keywords = valid_keywords[:MAX_KEYWORDS_PER_SCREENING]
        for kw in excess:
            invalid_keywords.append((kw, f"Exceeds maximum of {MAX_KEYWORDS_PER_SCREENING} keywords"))
    
    return valid_keywords, invalid_keywords


def filter_stop_words(keywords: List[str]) -> List[str]:
    """
    Filter out stop words from a keyword list.
    Returns only valid keywords, silently removing invalid ones.
    """
    valid, _ = validate_keywords(keywords)
    return valid


def is_stop_word(word: str) -> bool:
    """Check if a single word is a stop word"""
    return word.strip().lower() in STOP_WORDS


def get_stop_words() -> Set[str]:
    """Get the set of stop words for display purposes"""
    return STOP_WORDS.copy()


def add_custom_stop_words(words: List[str]) -> None:
    """
    Add custom stop words to the global set.
    Useful for organization-specific common terms.
    """
    global STOP_WORDS
    STOP_WORDS = STOP_WORDS | {w.strip().lower() for w in words if w.strip()}


class ProcessingGuard:
    """
    Guard class to prevent runaway processing from excessive matches.
    Use in document matching loops to enforce limits.
    """
    
    def __init__(self, 
                 warning_threshold: int = MAX_MATCHES_WARNING_THRESHOLD,
                 hard_limit: int = MAX_MATCHES_HARD_LIMIT,
                 context: str = ""):
        self.warning_threshold = warning_threshold
        self.hard_limit = hard_limit
        self.context = context
        self.match_count = 0
        self.warning_issued = False
        self.limit_reached = False
        
    def increment(self) -> bool:
        """
        Increment match count and check limits.
        
        Returns:
            True if processing should continue, False if hard limit reached
        """
        self.match_count += 1
        
        if self.match_count >= self.hard_limit:
            if not self.limit_reached:
                self.limit_reached = True
                logger.error(
                    f"PROCESSING GUARD: Hard limit of {self.hard_limit} matches reached. "
                    f"Context: {self.context}. Stopping processing."
                )
            return False
        
        if self.match_count >= self.warning_threshold and not self.warning_issued:
            self.warning_issued = True
            logger.warning(
                f"PROCESSING GUARD: Warning threshold of {self.warning_threshold} matches reached. "
                f"Context: {self.context}. Consider reviewing keyword configuration."
            )
        
        return True
    
    def can_continue(self) -> bool:
        """Check if processing can continue without incrementing"""
        return self.match_count < self.hard_limit
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        return {
            'match_count': self.match_count,
            'warning_issued': self.warning_issued,
            'limit_reached': self.limit_reached,
            'context': self.context
        }

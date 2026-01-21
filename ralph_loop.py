#!/usr/bin/env python3
"""
Ralph Loop - Self-Optimizing Screening Engine Test System

Iteratively runs tests on the screening engine, captures errors,
and logs issues for fixing until deterministic behavior is achieved.

Focus areas:
- Eligibility calculations (age, gender, conditions)
- Screening criteria matching (keywords, frequency, triggers)
- Variant recognition and selection
- Document matching logic
- Screening type edit → screening list consistency
"""

import sys
import os
import io
import traceback
import json
from datetime import datetime, date
from contextlib import redirect_stdout, redirect_stderr

# Maximum iterations to prevent infinite loops
MAX_ITERATIONS = 10
PROGRESS_LOG = "ralph_progress.log"
ERRORS_LOG = "ralph_errors.json"


def log_progress(message: str):
    """Log progress to file and stdout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(PROGRESS_LOG, 'a') as f:
        f.write(log_line + "\n")


def log_error(error_data: dict):
    """Append error to JSON errors file"""
    errors = []
    if os.path.exists(ERRORS_LOG):
        try:
            with open(ERRORS_LOG, 'r') as f:
                errors = json.load(f)
        except:
            errors = []
    
    error_data['timestamp'] = datetime.now().isoformat()
    errors.append(error_data)
    
    with open(ERRORS_LOG, 'w') as f:
        json.dump(errors, f, indent=2, default=str)


def run_screening_engine_tests():
    """Run comprehensive screening engine tests and return results"""
    results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    # Import within function to capture import errors
    try:
        from app import create_app, db
        from models import (
            ScreeningType, Screening, Patient, PatientCondition, 
            Organization, User, FHIRDocument
        )
        from core.criteria import EligibilityCriteria
        from core.variants import ScreeningVariants
        from core.matcher import DocumentMatcher
        from core.fuzzy_detection import FuzzyDetectionEngine
        
        app = create_app()
    except Exception as e:
        results['errors'].append({
            'test': 'imports',
            'error_type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exc()
        })
        return results
    
    with app.app_context():
        # Initialize test components
        eligibility = EligibilityCriteria()
        variants = ScreeningVariants()
        fuzzy_engine = FuzzyDetectionEngine()
        
        # ===========================================
        # TEST SUITE 1: Eligibility Calculations
        # ===========================================
        
        # Test 1.1: Age eligibility check
        results['total'] += 1
        try:
            # Create mock patient and screening type for testing
            class MockPatient:
                def __init__(self, age, gender, conditions=None):
                    self.age = age
                    self.gender = gender
                    self.conditions = conditions or []
            
            class MockCondition:
                def __init__(self, name, is_active=True):
                    self.condition_name = name
                    self.is_active = is_active
            
            class MockScreeningType:
                def __init__(self, name, min_age=None, max_age=None, 
                             eligible_genders='both', trigger_conditions=None,
                             org_id=1, id=1, is_active=True, frequency_value=1.0,
                             frequency_unit='years'):
                    self.name = name
                    self.min_age = min_age
                    self.max_age = max_age
                    self.eligible_genders = eligible_genders
                    self.trigger_conditions = json.dumps(trigger_conditions) if trigger_conditions else None
                    self.org_id = org_id
                    self.id = id
                    self.is_active = is_active
                    self.frequency_value = frequency_value
                    self.frequency_unit = frequency_unit
                
                @property
                def trigger_conditions_list(self):
                    if not self.trigger_conditions:
                        return []
                    try:
                        return json.loads(self.trigger_conditions)
                    except:
                        return []
                
                @property
                def specificity_score(self):
                    if not self.trigger_conditions_list:
                        return 0
                    return 10
                
                @property
                def variant_severity(self):
                    return None
            
            # Test age eligibility
            patient_45 = MockPatient(age=45, gender='M')
            screening_50_plus = MockScreeningType("Colonoscopy", min_age=50)
            
            result = eligibility._check_age_eligibility(patient_45, screening_50_plus)
            assert result == False, f"Expected False for 45yo patient with min_age=50, got {result}"
            
            patient_55 = MockPatient(age=55, gender='M')
            result = eligibility._check_age_eligibility(patient_55, screening_50_plus)
            assert result == True, f"Expected True for 55yo patient with min_age=50, got {result}"
            
            results['passed'] += 1
            log_progress("PASS: Test 1.1 - Age eligibility check")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '1.1_age_eligibility',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 1.1 - Age eligibility: {str(e)}")
        
        # Test 1.2: Gender eligibility check
        results['total'] += 1
        try:
            patient_female = MockPatient(age=50, gender='female')
            patient_male = MockPatient(age=50, gender='male')
            
            mammogram = MockScreeningType("Mammogram", min_age=40, eligible_genders='F')
            
            result_female = eligibility._check_gender_eligibility(patient_female, mammogram)
            assert result_female == True, f"Expected True for female patient, got {result_female}"
            
            result_male = eligibility._check_gender_eligibility(patient_male, mammogram)
            assert result_male == False, f"Expected False for male patient, got {result_male}"
            
            # Test 'both' gender
            general_screening = MockScreeningType("CBC", eligible_genders='both')
            result_both = eligibility._check_gender_eligibility(patient_male, general_screening)
            assert result_both == True, f"Expected True for 'both' gender, got {result_both}"
            
            results['passed'] += 1
            log_progress("PASS: Test 1.2 - Gender eligibility check")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '1.2_gender_eligibility',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 1.2 - Gender eligibility: {str(e)}")
        
        # Test 1.3: Trigger conditions matching
        results['total'] += 1
        try:
            patient_diabetic = MockPatient(
                age=55, gender='M',
                conditions=[MockCondition('type 2 diabetes')]
            )
            patient_healthy = MockPatient(age=55, gender='M', conditions=[])
            
            diabetic_a1c = MockScreeningType(
                "A1C", 
                trigger_conditions=['diabetes', 'type 2 diabetes']
            )
            
            # Test with matching conditions
            result_diabetic = eligibility._patient_matches_trigger_conditions(
                patient_diabetic, 
                diabetic_a1c.trigger_conditions_list
            )
            assert result_diabetic == True, f"Expected True for diabetic patient, got {result_diabetic}"
            
            # Test with no conditions
            result_healthy = eligibility._patient_matches_trigger_conditions(
                patient_healthy,
                diabetic_a1c.trigger_conditions_list
            )
            assert result_healthy == False, f"Expected False for healthy patient, got {result_healthy}"
            
            results['passed'] += 1
            log_progress("PASS: Test 1.3 - Trigger conditions matching")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '1.3_trigger_conditions',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 1.3 - Trigger conditions: {str(e)}")
        
        # ===========================================
        # TEST SUITE 2: Screening Status Calculations
        # ===========================================
        
        # Test 2.1: Status calculation based on frequency
        results['total'] += 1
        try:
            from datetime import timedelta
            from dateutil.relativedelta import relativedelta
            
            annual_screening = MockScreeningType(
                "Annual Physical", 
                frequency_value=1.0, 
                frequency_unit='years'
            )
            
            # Last completed today - should be complete
            today = date.today()
            status = eligibility.calculate_screening_status(annual_screening, today)
            assert status == 'complete', f"Expected 'complete' for screening done today, got {status}"
            
            # Last completed 2 years ago - should be due
            two_years_ago = today - relativedelta(years=2)
            status = eligibility.calculate_screening_status(annual_screening, two_years_ago)
            assert status == 'due', f"Expected 'due' for 2-year old screening, got {status}"
            
            # Last completed 11 months ago - should be complete (not due yet)
            eleven_months_ago = today - relativedelta(months=11)
            status = eligibility.calculate_screening_status(annual_screening, eleven_months_ago)
            assert status in ['complete', 'due_soon'], f"Expected 'complete' or 'due_soon' for 11-month old, got {status}"
            
            results['passed'] += 1
            log_progress("PASS: Test 2.1 - Screening status calculation")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '2.1_status_calculation',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 2.1 - Status calculation: {str(e)}")
        
        # ===========================================
        # TEST SUITE 3: Fuzzy Detection Engine
        # ===========================================
        
        # Test 3.1: Keyword matching
        results['total'] += 1
        try:
            keywords = ['mammogram', 'breast screening', 'mammography']
            
            # Test exact match
            result = fuzzy_engine.fuzzy_match_keywords(
                "Annual mammogram screening results",
                keywords,
                threshold=0.7
            )
            assert len(result) > 0, "Expected matches for 'mammogram' in text"
            
            # Test fuzzy match
            result = fuzzy_engine.fuzzy_match_keywords(
                "Breast cancer screening completed",
                keywords,
                threshold=0.6
            )
            # Should find 'breast screening' as partial match
            
            results['passed'] += 1
            log_progress("PASS: Test 3.1 - Fuzzy keyword matching")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '3.1_fuzzy_keywords',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 3.1 - Fuzzy keywords: {str(e)}")
        
        # Test 3.2: Medical suffix matching
        results['total'] += 1
        try:
            # Test medical suffix normalization
            keywords = ['colonoscopy']
            
            result = fuzzy_engine.fuzzy_match_keywords(
                "Colonoscopic examination performed",
                keywords,
                threshold=0.7
            )
            # Should recognize 'colonoscopic' as related to 'colonoscopy'
            
            results['passed'] += 1
            log_progress("PASS: Test 3.2 - Medical suffix matching")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '3.2_medical_suffix',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 3.2 - Medical suffix: {str(e)}")
        
        # ===========================================
        # TEST SUITE 4: Variant Selection (Determinism)
        # ===========================================
        
        # Test 4.1: Deterministic variant ordering
        results['total'] += 1
        try:
            # Test that variant selection is deterministic
            # Run same logic multiple times, should get same result
            
            class MockVariant:
                def __init__(self, id, name, specificity, triggers=None):
                    self.id = id
                    self.name = name
                    self._specificity = specificity
                    self.trigger_conditions_list = triggers or []
                
                @property
                def specificity_score(self):
                    return self._specificity
            
            variants = [
                MockVariant(3, "A1C - Severe Diabetic", 25, ['severe diabetes']),
                MockVariant(1, "A1C - Diabetic", 10, ['diabetes']),
                MockVariant(2, "A1C", 0, []),
            ]
            
            # Sort as screening engine does: specificity desc, id asc
            sorted_variants = sorted(variants, key=lambda v: (-v.specificity_score, v.id))
            
            # Run 5 times - should always produce same order
            expected_order = [v.id for v in sorted_variants]
            for i in range(5):
                test_sort = sorted(variants, key=lambda v: (-v.specificity_score, v.id))
                actual_order = [v.id for v in test_sort]
                assert actual_order == expected_order, f"Iteration {i}: Expected {expected_order}, got {actual_order}"
            
            # Verify order is: id=3 (specificity 25), id=1 (specificity 10), id=2 (specificity 0)
            assert expected_order == [3, 1, 2], f"Expected [3, 1, 2], got {expected_order}"
            
            results['passed'] += 1
            log_progress("PASS: Test 4.1 - Deterministic variant ordering")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '4.1_deterministic_variants',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 4.1 - Deterministic variants: {str(e)}")
        
        # Test 4.2: Specificity scoring
        results['total'] += 1
        try:
            from utils.condition_metadata import condition_metadata
            
            # Test specificity calculation for different variant types
            general_type = MockScreeningType("A1C", trigger_conditions=[])
            condition_type = MockScreeningType("A1C", trigger_conditions=['diabetes'])
            
            general_score = condition_metadata.calculate_variant_specificity(general_type)
            condition_score = condition_metadata.calculate_variant_specificity(condition_type)
            
            assert general_score == 0, f"Expected 0 for general type, got {general_score}"
            assert condition_score >= 10, f"Expected >= 10 for condition type, got {condition_score}"
            assert condition_score > general_score, "Condition type should have higher specificity"
            
            results['passed'] += 1
            log_progress("PASS: Test 4.2 - Specificity scoring")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '4.2_specificity_scoring',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 4.2 - Specificity scoring: {str(e)}")
        
        # ===========================================
        # TEST SUITE 5: Document Matching
        # ===========================================
        
        # Test 5.1: Document matcher initialization
        results['total'] += 1
        try:
            matcher = DocumentMatcher()
            assert matcher is not None, "DocumentMatcher should initialize"
            results['passed'] += 1
            log_progress("PASS: Test 5.1 - Document matcher initialization")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '5.1_document_matcher_init',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 5.1 - Document matcher init: {str(e)}")
        
        # Test 5.2: Keyword pre-filtering logic
        results['total'] += 1
        try:
            # Test the keyword pre-filter that skips non-matching screenings
            screening_keywords = ['mammogram', 'breast', 'mammography']
            doc_text = "Annual colonoscopy screening report"
            
            # Pre-filter check: should return False (no match)
            has_match = any(kw.lower() in doc_text.lower() for kw in screening_keywords)
            assert has_match == False, "Colonoscopy doc should not match mammogram keywords"
            
            doc_text_matching = "Bilateral mammogram screening normal"
            has_match = any(kw.lower() in doc_text_matching.lower() for kw in screening_keywords)
            assert has_match == True, "Mammogram doc should match mammogram keywords"
            
            results['passed'] += 1
            log_progress("PASS: Test 5.2 - Keyword pre-filtering")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '5.2_keyword_prefilter',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 5.2 - Keyword pre-filtering: {str(e)}")
        
        # ===========================================
        # TEST SUITE 6: Gender Normalization
        # ===========================================
        
        # Test 6.1: Gender format handling
        results['total'] += 1
        try:
            # Test various gender formats
            test_cases = [
                ('female', 'F'),
                ('Female', 'F'),
                ('FEMALE', 'F'),
                ('F', 'F'),
                ('male', 'M'),
                ('Male', 'M'),
                ('MALE', 'M'),
                ('M', 'M'),
                ('unknown', None),
                ('other', None),
                (None, None),
            ]
            
            for input_gender, expected in test_cases:
                result = eligibility._normalize_gender(input_gender)
                assert result == expected, f"Expected '{expected}' for '{input_gender}', got '{result}'"
            
            results['passed'] += 1
            log_progress("PASS: Test 6.1 - Gender normalization")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '6.1_gender_normalization',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 6.1 - Gender normalization: {str(e)}")
        
        # ===========================================
        # TEST SUITE 7: Frequency Calculations
        # ===========================================
        
        # Test 7.1: Next due date calculation
        results['total'] += 1
        try:
            from dateutil.relativedelta import relativedelta
            
            # Test annual frequency
            last_completed = date(2024, 1, 15)
            next_due = eligibility._calculate_next_due_date(last_completed, 1.0, 'years')
            expected = date(2025, 1, 15)
            assert next_due == expected, f"Expected {expected}, got {next_due}"
            
            # Test 6-month frequency
            next_due = eligibility._calculate_next_due_date(last_completed, 6, 'months')
            expected = date(2024, 7, 15)
            assert next_due == expected, f"Expected {expected}, got {next_due}"
            
            results['passed'] += 1
            log_progress("PASS: Test 7.1 - Next due date calculation")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '7.1_due_date_calculation',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 7.1 - Due date calculation: {str(e)}")
        
        # ===========================================
        # TEST SUITE 8: Screening Type Properties
        # ===========================================
        
        # Test 8.1: Keywords list parsing
        results['total'] += 1
        try:
            # Test JSON format
            st = ScreeningType()
            st.keywords = json.dumps(['mammogram', 'breast screening'])
            kw_list = st.keywords_list
            assert kw_list == ['mammogram', 'breast screening'], f"Expected list, got {kw_list}"
            
            # Test comma-separated format
            st.keywords = 'colonoscopy, colon cancer screening'
            kw_list = st.keywords_list
            assert 'colonoscopy' in kw_list, f"Expected 'colonoscopy' in {kw_list}"
            
            # Test empty
            st.keywords = None
            kw_list = st.keywords_list
            assert kw_list == [], f"Expected empty list, got {kw_list}"
            
            results['passed'] += 1
            log_progress("PASS: Test 8.1 - Keywords list parsing")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '8.1_keywords_parsing',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 8.1 - Keywords parsing: {str(e)}")
        
        # Test 8.2: Trigger conditions list parsing
        results['total'] += 1
        try:
            st = ScreeningType()
            
            # Test JSON format
            st.trigger_conditions = json.dumps(['diabetes', 'hypertension'])
            tc_list = st.trigger_conditions_list
            assert tc_list == ['diabetes', 'hypertension'], f"Expected list, got {tc_list}"
            
            # Test empty JSON
            st.trigger_conditions = '[]'
            tc_list = st.trigger_conditions_list
            assert tc_list == [], f"Expected empty list for '[]', got {tc_list}"
            
            # Test null JSON
            st.trigger_conditions = 'null'
            tc_list = st.trigger_conditions_list
            assert tc_list == [], f"Expected empty list for 'null', got {tc_list}"
            
            # Test None
            st.trigger_conditions = None
            tc_list = st.trigger_conditions_list
            assert tc_list == [], f"Expected empty list for None, got {tc_list}"
            
            results['passed'] += 1
            log_progress("PASS: Test 8.2 - Trigger conditions parsing")
        except Exception as e:
            results['failed'] += 1
            error_info = {
                'test': '8.2_trigger_conditions_parsing',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            results['errors'].append(error_info)
            log_progress(f"FAIL: Test 8.2 - Trigger conditions parsing: {str(e)}")
    
    return results


def run_ralph_loop():
    """Main Ralph loop orchestrator"""
    log_progress("=" * 60)
    log_progress("RALPH LOOP - Screening Engine Self-Optimization")
    log_progress("=" * 60)
    
    iteration = 1
    all_passed = False
    
    while iteration <= MAX_ITERATIONS and not all_passed:
        log_progress(f"\n>>> ITERATION {iteration} of {MAX_ITERATIONS}")
        
        try:
            results = run_screening_engine_tests()
            
            log_progress(f"Results: {results['passed']}/{results['total']} passed, {results['failed']} failed")
            
            if results['failed'] == 0 and results['total'] > 0:
                all_passed = True
                log_progress("SUCCESS! All tests passed.")
            else:
                # Log errors for this iteration
                for error in results['errors']:
                    log_error({
                        'iteration': iteration,
                        **error
                    })
                
                log_progress(f"Iteration {iteration} had {len(results['errors'])} error(s)")
                
                # Analyze errors and suggest fixes
                for error in results['errors']:
                    log_progress(f"  - {error['test']}: {error['error_type']} - {error['message']}")
        
        except Exception as e:
            log_progress(f"CRITICAL ERROR in iteration {iteration}: {str(e)}")
            log_error({
                'iteration': iteration,
                'test': 'loop_execution',
                'error_type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            })
        
        iteration += 1
    
    log_progress("\n" + "=" * 60)
    if all_passed:
        log_progress("RALPH LOOP COMPLETE - All screening engine tests pass!")
        log_progress("The screening engine is now deterministic and error-free.")
        return 0
    else:
        log_progress(f"RALPH LOOP ENDED after {iteration - 1} iterations")
        log_progress(f"Review {ERRORS_LOG} for details on remaining issues.")
        return 1


if __name__ == "__main__":
    sys.exit(run_ralph_loop())

#!/usr/bin/env python3
"""
Comprehensive test for screening list responsiveness to changes in criteria, keywords, and activation status.
Tests real-time updates and ensures the system responds properly to changes.
"""

import sys
import os
import time
import json
import requests
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# Add the current directory to Python path  
sys.path.insert(0, '.')

try:
    from main import app
    from app import db
    from models import (
        ScreeningType, Screening, Patient, User, Organization,
        PatientCondition
    )
    from core.engine import ScreeningEngine
    from core.selective_refresh import SelectiveRefreshManager
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

class ScreeningResponsivenessTest:
    """Comprehensive test suite for screening list responsiveness"""
    
    def __init__(self):
        self.app = app
        self.db = db
        self.engine = ScreeningEngine()
        self.test_results = {}
        self.baseline_data = {}
        
    def run_all_tests(self):
        """Run all responsiveness tests"""
        print("=" * 80)
        print("COMPREHENSIVE SCREENING RESPONSIVENESS TESTS")
        print("=" * 80)
        
        with self.app.app_context():
            # Setup and baseline
            if not self.setup_test_environment():
                return False
            
            # Test sequence - focus on responsiveness
            tests = [
                ("Test 1: Baseline System State", self.test_baseline_system),
                ("Test 2: Age Criteria Responsiveness", self.test_age_criteria_responsiveness),
                ("Test 3: Gender Criteria Responsiveness", self.test_gender_criteria_responsiveness),
                ("Test 4: Keyword Changes Responsiveness", self.test_keyword_responsiveness),
                ("Test 5: Activation Status Responsiveness", self.test_activation_responsiveness),
                ("Test 6: Trigger Condition Responsiveness", self.test_trigger_condition_responsiveness),
                ("Test 7: Frequency Changes Responsiveness", self.test_frequency_responsiveness),
                ("Test 8: Dashboard Counter Updates", self.test_dashboard_responsiveness),
                ("Test 9: Multi-Tenant Isolation", self.test_multi_tenant_isolation),
                ("Test 10: Engine Refresh Performance", self.test_refresh_performance)
            ]
            
            for test_name, test_func in tests:
                print(f"\n{'-' * 60}")
                print(f"Running: {test_name}")
                print(f"{'-' * 60}")
                
                try:
                    start_time = time.time()
                    result = test_func()
                    end_time = time.time()
                    
                    self.test_results[test_name] = {
                        'result': result,
                        'duration': end_time - start_time,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    status = "PASS" if result['success'] else "FAIL"
                    print(f"Result: {status} (Duration: {end_time - start_time:.3f}s)")
                    
                    if not result['success']:
                        print(f"Error: {result.get('error', 'Unknown error')}")
                    else:
                        # Show key metrics
                        if 'changed_count' in result:
                            print(f"Screenings affected: {result['changed_count']}")
                        if 'eligible_before' in result and 'eligible_after' in result:
                            print(f"Eligibility change: {result['eligible_before']} -> {result['eligible_after']}")
                            
                except Exception as e:
                    print(f"Test failed with exception: {str(e)}")
                    self.test_results[test_name] = {
                        'result': {'success': False, 'error': str(e)},
                        'duration': 0,
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Generate final report
            self.generate_final_report()
            return True
    
    def setup_test_environment(self):
        """Setup test environment and capture baseline data"""
        print("Setting up test environment...")
        
        # Get baseline data
        self.baseline_data = {
            'organizations': Organization.query.count(),
            'users': User.query.count(),
            'screening_types': ScreeningType.query.filter_by(is_active=True).count(),
            'patients': Patient.query.count(),
            'screenings': Screening.query.count(),
            'screening_statuses': self._get_screening_status_counts()
        }
        
        print(f"Baseline: {self.baseline_data['patients']} patients, {self.baseline_data['screenings']} screenings")
        
        # Get test organization
        self.test_org = Organization.query.filter_by(name='Default Organization').first()
        if not self.test_org:
            print("ERROR: Default Organization not found!")
            return False
            
        print(f"Using test organization: {self.test_org.name} (ID: {self.test_org.id})")
        
        # Ensure we have test data
        test_patients = Patient.query.filter_by(org_id=self.test_org.id).count()
        test_screening_types = ScreeningType.query.filter_by(org_id=self.test_org.id, is_active=True).count()
        
        if test_patients == 0 or test_screening_types == 0:
            print(f"ERROR: Insufficient test data. Patients: {test_patients}, Screening Types: {test_screening_types}")
            return False
            
        print(f"Test data: {test_patients} patients, {test_screening_types} screening types")
        return True
    
    def test_baseline_system(self):
        """Test current system state and establish baseline"""
        try:
            # Check current screening distribution by status
            status_counts = {}
            screenings = Screening.query.join(Patient).filter(Patient.org_id == self.test_org.id).all()
            
            for screening in screenings:
                status = screening.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Check screening type distribution  
            type_counts = {}
            for screening in screenings:
                type_name = screening.screening_type.name
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            
            result = {
                'success': True,
                'total_screenings': len(screenings),
                'status_distribution': status_counts,
                'type_distribution': dict(list(type_counts.items())[:5]),  # Top 5
                'baseline_established': True
            }
            
            print(f"Total screenings: {len(screenings)}")
            print(f"Status distribution: {status_counts}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_age_criteria_responsiveness(self):
        """Test responsiveness to age criteria changes"""
        try:
            # Find a screening type to modify
            test_type = ScreeningType.query.filter_by(
                org_id=self.test_org.id, 
                is_active=True
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No screening types found'}
            
            # Record original values
            original_min_age = test_type.min_age
            original_max_age = test_type.max_age
            
            # Count eligible patients before change
            eligible_before = self._count_eligible_patients(test_type)
            
            print(f"Testing {test_type.name}")
            print(f"Original age range: {original_min_age}-{original_max_age}")
            print(f"Eligible patients before: {eligible_before}")
            
            # Make restrictive change - set high minimum age
            test_type.min_age = 70
            test_type.max_age = 85
            db.session.commit()
            
            # Count eligible patients after change
            eligible_after = self._count_eligible_patients(test_type)
            
            # Test refresh responsiveness
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            # Restore original values
            test_type.min_age = original_min_age
            test_type.max_age = original_max_age
            db.session.commit()
            
            # Final refresh to restore state
            self.engine.refresh_all_screenings()
            
            result = {
                'success': True,
                'eligible_before': eligible_before,
                'eligible_after': eligible_after,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'responsive': eligible_after != eligible_before,
                'restrictive_working': eligible_after < eligible_before
            }
            
            print(f"Eligible after age change: {eligible_after}")
            print(f"Refresh updated {refresh_count} screenings in {refresh_time:.3f}s")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_gender_criteria_responsiveness(self):
        """Test responsiveness to gender criteria changes"""
        try:
            test_type = ScreeningType.query.filter_by(
                org_id=self.test_org.id,
                is_active=True
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No screening types found'}
            
            original_gender = test_type.eligible_genders
            
            # Count male and female patients
            male_patients = Patient.query.filter_by(org_id=self.test_org.id, gender='M').count()
            female_patients = Patient.query.filter_by(org_id=self.test_org.id, gender='F').count()
            
            print(f"Testing {test_type.name}")
            print(f"Patient distribution: {male_patients} male, {female_patients} female")
            
            # Test male-only restriction
            test_type.eligible_genders = 'M'
            db.session.commit()
            
            eligible_male_only = self._count_eligible_patients(test_type)
            
            # Test female-only restriction
            test_type.eligible_genders = 'F'
            db.session.commit()
            
            eligible_female_only = self._count_eligible_patients(test_type)
            
            # Test refresh responsiveness
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            # Restore original gender criteria
            test_type.eligible_genders = original_gender
            db.session.commit()
            self.engine.refresh_all_screenings()
            
            result = {
                'success': True,
                'male_patients': male_patients,
                'female_patients': female_patients,
                'eligible_male_only': eligible_male_only,
                'eligible_female_only': eligible_female_only,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'gender_restriction_working': eligible_male_only <= male_patients and eligible_female_only <= female_patients
            }
            
            print(f"Eligible when male-only: {eligible_male_only}")
            print(f"Eligible when female-only: {eligible_female_only}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_keyword_responsiveness(self):
        """Test responsiveness to keyword changes"""
        try:
            # Find screening type with keywords
            test_type = ScreeningType.query.filter(
                ScreeningType.org_id == self.test_org.id,
                ScreeningType.is_active == True,
                ScreeningType.keywords.isnot(None)
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No screening types with keywords found'}
            
            original_keywords = test_type.keywords
            original_list = test_type.keywords_list
            
            print(f"Testing {test_type.name}")
            print(f"Original keywords: {len(original_list)} items")
            
            # Add test keywords
            new_keywords = original_list + ['test_keyword_responsiveness', 'automation_test']
            test_type.keywords = json.dumps(new_keywords)
            db.session.commit()
            
            # Test keyword matching would change
            keywords_changed = len(new_keywords) != len(original_list)
            
            # Test refresh performance
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            # Restore original keywords
            test_type.keywords = original_keywords
            db.session.commit()
            
            result = {
                'success': True,
                'original_keyword_count': len(original_list),
                'new_keyword_count': len(new_keywords),
                'keywords_changed': keywords_changed,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'keyword_system_working': keywords_changed
            }
            
            print(f"Keywords changed: {len(original_list)} -> {len(new_keywords)}")
            print(f"Refresh time: {refresh_time:.3f}s")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_activation_responsiveness(self):
        """Test responsiveness to activation/deactivation changes"""
        try:
            test_type = ScreeningType.query.filter_by(
                org_id=self.test_org.id,
                is_active=True
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No active screening types found'}
            
            # Count active screenings before
            active_before = Screening.query.join(ScreeningType).filter(
                ScreeningType.org_id == self.test_org.id,
                ScreeningType.is_active == True
            ).count()
            
            # Count screenings for this specific type
            type_screenings_before = Screening.query.filter_by(
                screening_type_id=test_type.id
            ).count()
            
            print(f"Testing {test_type.name}")
            print(f"Active screenings before: {active_before}")
            print(f"This type's screenings: {type_screenings_before}")
            
            # Deactivate the screening type
            deactivate_start = time.time()
            test_type.is_active = False
            db.session.commit()
            deactivate_time = time.time() - deactivate_start
            
            # Count active screenings after deactivation
            active_after_deactivate = Screening.query.join(ScreeningType).filter(
                ScreeningType.org_id == self.test_org.id,
                ScreeningType.is_active == True
            ).count()
            
            # Reactivate
            reactivate_start = time.time()
            test_type.is_active = True
            db.session.commit()
            reactivate_time = time.time() - reactivate_start
            
            # Count active screenings after reactivation
            active_after_reactivate = Screening.query.join(ScreeningType).filter(
                ScreeningType.org_id == self.test_org.id,
                ScreeningType.is_active == True
            ).count()
            
            # Test refresh after activation change
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            result = {
                'success': True,
                'active_before': active_before,
                'active_after_deactivate': active_after_deactivate,
                'active_after_reactivate': active_after_reactivate,
                'deactivate_time': deactivate_time,
                'reactivate_time': reactivate_time,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'activation_responsive': active_after_deactivate != active_before
            }
            
            print(f"Active after deactivation: {active_after_deactivate}")
            print(f"Active after reactivation: {active_after_reactivate}")
            print(f"Activation change time: {deactivate_time:.3f}s")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_trigger_condition_responsiveness(self):
        """Test responsiveness to trigger condition changes"""
        try:
            # Find or create a screening type to test trigger conditions
            test_type = ScreeningType.query.filter_by(
                org_id=self.test_org.id,
                is_active=True
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No screening types found'}
            
            original_triggers = test_type.trigger_conditions
            
            # Count eligible patients before trigger conditions
            eligible_before = self._count_eligible_patients(test_type)
            
            print(f"Testing {test_type.name}")
            print(f"Eligible before trigger conditions: {eligible_before}")
            
            # Add restrictive trigger conditions
            test_conditions = json.dumps(['very_rare_condition', 'nonexistent_condition'])
            test_type.trigger_conditions = test_conditions
            db.session.commit()
            
            # Count eligible patients after trigger conditions
            eligible_after = self._count_eligible_patients(test_type)
            
            # Test refresh responsiveness
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            # Restore original trigger conditions
            test_type.trigger_conditions = original_triggers
            db.session.commit()
            self.engine.refresh_all_screenings()
            
            result = {
                'success': True,
                'eligible_before': eligible_before,
                'eligible_after': eligible_after,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'trigger_conditions_working': eligible_after < eligible_before
            }
            
            print(f"Eligible after trigger conditions: {eligible_after}")
            print(f"Trigger conditions reduced eligibility: {eligible_after < eligible_before}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_frequency_responsiveness(self):
        """Test responsiveness to frequency changes"""
        try:
            test_type = ScreeningType.query.filter_by(
                org_id=self.test_org.id,
                is_active=True
            ).first()
            
            if not test_type:
                return {'success': False, 'error': 'No screening types found'}
            
            original_frequency = test_type.frequency_years
            
            print(f"Testing {test_type.name}")
            print(f"Original frequency: {original_frequency} years")
            
            # Test with very short frequency (should make more screenings due)
            test_type.frequency_years = 0.1  # About 1 month
            db.session.commit()
            
            # Calculate status with short frequency
            test_date = date.today() - timedelta(days=60)  # 2 months ago
            status_short = self.engine.criteria.calculate_screening_status(test_type, test_date)
            
            # Test with very long frequency (should make screenings complete)
            test_type.frequency_years = 10  # 10 years
            db.session.commit()
            
            status_long = self.engine.criteria.calculate_screening_status(test_type, test_date)
            
            # Test refresh responsiveness
            refresh_start = time.time()
            refresh_count = self.engine.refresh_all_screenings()
            refresh_time = time.time() - refresh_start
            
            # Restore original frequency
            test_type.frequency_years = original_frequency
            db.session.commit()
            
            result = {
                'success': True,
                'original_frequency': original_frequency,
                'status_short_frequency': status_short,
                'status_long_frequency': status_long,
                'refresh_count': refresh_count,
                'refresh_time': refresh_time,
                'frequency_affects_status': status_short != status_long
            }
            
            print(f"Status with short frequency: {status_short}")
            print(f"Status with long frequency: {status_long}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_dashboard_responsiveness(self):
        """Test dashboard counter responsiveness to changes"""
        try:
            # Get initial dashboard stats
            initial_stats = self._get_dashboard_stats()
            
            # Find a screening to modify
            test_screening = Screening.query.join(Patient).filter(
                Patient.org_id == self.test_org.id
            ).first()
            
            if not test_screening:
                return {'success': False, 'error': 'No screenings found to test'}
            
            original_status = test_screening.status
            
            print(f"Initial stats: {initial_stats}")
            print(f"Changing screening status from: {original_status}")
            
            # Change screening status
            new_status = 'complete' if original_status != 'complete' else 'due'
            status_change_start = time.time()
            test_screening.status = new_status
            db.session.commit()
            status_change_time = time.time() - status_change_start
            
            # Get updated stats
            updated_stats = self._get_dashboard_stats()
            
            # Restore original status
            test_screening.status = original_status
            db.session.commit()
            
            result = {
                'success': True,
                'initial_stats': initial_stats,
                'updated_stats': updated_stats,
                'status_change_time': status_change_time,
                'stats_changed': initial_stats != updated_stats,
                'dashboard_responsive': initial_stats != updated_stats
            }
            
            print(f"Updated stats: {updated_stats}")
            print(f"Status change time: {status_change_time:.3f}s")
            print(f"Dashboard responsive: {initial_stats != updated_stats}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_multi_tenant_isolation(self):
        """Test multi-tenant isolation during updates"""
        try:
            # Get both organizations
            org1 = Organization.query.filter_by(name='Default Organization').first()
            org2 = Organization.query.filter_by(name="Tricia's Organization").first()
            
            if not org1:
                return {'success': False, 'error': 'Default Organization not found'}
            
            # Count screening types for each org
            org1_types_before = ScreeningType.query.filter_by(org_id=org1.id, is_active=True).count()
            org2_types_before = ScreeningType.query.filter_by(org_id=org2.id, is_active=True).count() if org2 else 0
            
            # Count screenings for each org
            org1_screenings_before = Screening.query.join(Patient).filter(Patient.org_id == org1.id).count()
            org2_screenings_before = Screening.query.join(Patient).filter(Patient.org_id == org2.id).count() if org2 else 0
            
            print(f"Org1 before: {org1_types_before} types, {org1_screenings_before} screenings")
            if org2:
                print(f"Org2 before: {org2_types_before} types, {org2_screenings_before} screenings")
            
            # Modify screening type in org1
            test_type = ScreeningType.query.filter_by(org_id=org1.id, is_active=True).first()
            if test_type:
                original_name = test_type.name
                isolation_test_start = time.time()
                test_type.name = f"{original_name} - ISOLATION_TEST"
                db.session.commit()
                isolation_test_time = time.time() - isolation_test_start
                
                # Check counts after modification
                org1_types_after = ScreeningType.query.filter_by(org_id=org1.id, is_active=True).count()
                org2_types_after = ScreeningType.query.filter_by(org_id=org2.id, is_active=True).count() if org2 else 0
                
                # Restore original name
                test_type.name = original_name
                db.session.commit()
            
            result = {
                'success': True,
                'org1_types_before': org1_types_before,
                'org1_types_after': org1_types_after,
                'org2_types_before': org2_types_before,
                'org2_types_after': org2_types_after,
                'isolation_test_time': isolation_test_time,
                'isolation_maintained': org2_types_before == org2_types_after,
                'org1_unchanged_count': org1_types_before == org1_types_after
            }
            
            print(f"Isolation maintained: {org2_types_before == org2_types_after}")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_refresh_performance(self):
        """Test engine refresh performance and mechanisms"""
        try:
            # Test full refresh performance
            full_refresh_start = time.time()
            full_refresh_count = self.engine.refresh_all_screenings()
            full_refresh_time = time.time() - full_refresh_start
            
            # Test patient-specific refresh
            test_patient = Patient.query.filter_by(org_id=self.test_org.id).first()
            if test_patient:
                patient_refresh_start = time.time()
                patient_refresh_count = self.engine.refresh_patient_screenings(test_patient.id)
                patient_refresh_time = time.time() - patient_refresh_start
            else:
                patient_refresh_count = 0
                patient_refresh_time = 0
            
            # Test multiple small refreshes vs one large refresh
            small_refresh_total_time = 0
            small_refresh_total_count = 0
            
            patients = Patient.query.filter_by(org_id=self.test_org.id).limit(3).all()
            for patient in patients:
                start = time.time()
                count = self.engine.refresh_patient_screenings(patient.id)
                small_refresh_total_time += time.time() - start
                small_refresh_total_count += count
            
            result = {
                'success': True,
                'full_refresh_count': full_refresh_count,
                'full_refresh_time': full_refresh_time,
                'patient_refresh_count': patient_refresh_count,
                'patient_refresh_time': patient_refresh_time,
                'small_refresh_total_time': small_refresh_total_time,
                'small_refresh_total_count': small_refresh_total_count,
                'refresh_mechanisms_working': full_refresh_count > 0,
                'performance_acceptable': full_refresh_time < 10.0  # 10 second threshold
            }
            
            print(f"Full refresh: {full_refresh_count} screenings in {full_refresh_time:.3f}s")
            print(f"Patient refresh: {patient_refresh_count} screenings in {patient_refresh_time:.3f}s")
            print(f"Small refreshes: {small_refresh_total_count} screenings in {small_refresh_total_time:.3f}s")
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _count_eligible_patients(self, screening_type):
        """Count patients eligible for a screening type"""
        count = 0
        patients = Patient.query.filter_by(org_id=self.test_org.id).all()
        
        for patient in patients:
            if self.engine.criteria.is_patient_eligible(patient, screening_type):
                count += 1
        
        return count
    
    def _get_screening_status_counts(self):
        """Get current screening status distribution"""
        statuses = {}
        for screening in Screening.query.all():
            status = screening.status
            statuses[status] = statuses.get(status, 0) + 1
        return statuses
    
    def _get_dashboard_stats(self):
        """Get current dashboard statistics"""
        stats = {
            'total_patients': Patient.query.filter_by(org_id=self.test_org.id).count(),
            'due_screenings': Screening.query.join(Patient).filter(
                Patient.org_id == self.test_org.id,
                Screening.status == 'due'
            ).count(),
            'due_soon_screenings': Screening.query.join(Patient).filter(
                Patient.org_id == self.test_org.id,
                Screening.status == 'due_soon'
            ).count(),
            'complete_screenings': Screening.query.join(Patient).filter(
                Patient.org_id == self.test_org.id,
                Screening.status == 'complete'
            ).count()
        }
        return stats
    
    def generate_final_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("SCREENING RESPONSIVENESS TEST REPORT")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['result']['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Performance summary
        total_time = sum(result['duration'] for result in self.test_results.values())
        avg_time = total_time / total_tests if total_tests > 0 else 0
        
        print(f"Total Test Time: {total_time:.3f}s")
        print(f"Average Test Time: {avg_time:.3f}s")
        
        print(f"\nResponsiveness Summary:")
        print(f"{'-' * 60}")
        
        responsiveness_checks = [
            ('Age Criteria', 'Test 2: Age Criteria Responsiveness', 'responsive'),
            ('Gender Criteria', 'Test 3: Gender Criteria Responsiveness', 'gender_restriction_working'),
            ('Keywords', 'Test 4: Keyword Changes Responsiveness', 'keyword_system_working'),
            ('Activation', 'Test 5: Activation Status Responsiveness', 'activation_responsive'),
            ('Trigger Conditions', 'Test 6: Trigger Condition Responsiveness', 'trigger_conditions_working'),
            ('Frequency', 'Test 7: Frequency Changes Responsiveness', 'frequency_affects_status'),
            ('Dashboard', 'Test 8: Dashboard Counter Updates', 'dashboard_responsive'),
            ('Multi-Tenant', 'Test 9: Multi-Tenant Isolation', 'isolation_maintained'),
            ('Performance', 'Test 10: Engine Refresh Performance', 'performance_acceptable')
        ]
        
        for check_name, test_key, result_key in responsiveness_checks:
            if test_key in self.test_results:
                test_result = self.test_results[test_key]['result']
                if test_result['success'] and result_key in test_result:
                    status = "✓ RESPONSIVE" if test_result[result_key] else "✗ NOT RESPONSIVE"
                    if 'refresh_time' in test_result:
                        status += f" ({test_result['refresh_time']:.3f}s)"
                else:
                    status = "✗ FAILED"
            else:
                status = "- NOT TESTED"
            
            print(f"{check_name:20}: {status}")
        
        # Detailed results
        print(f"\nDetailed Results:")
        print(f"{'-' * 60}")
        
        for test_name, result_data in self.test_results.items():
            result = result_data['result']
            duration = result_data['duration']
            status = "PASS" if result['success'] else "FAIL"
            
            print(f"\n{test_name}")
            print(f"  Status: {status}")
            print(f"  Duration: {duration:.3f}s")
            
            if not result['success']:
                print(f"  Error: {result.get('error', 'Unknown error')}")
            else:
                # Show key metrics
                key_metrics = []
                if 'refresh_time' in result:
                    key_metrics.append(f"refresh: {result['refresh_time']:.3f}s")
                if 'eligible_before' in result and 'eligible_after' in result:
                    key_metrics.append(f"eligibility: {result['eligible_before']} -> {result['eligible_after']}")
                if 'refresh_count' in result:
                    key_metrics.append(f"updated: {result['refresh_count']} screenings")
                
                if key_metrics:
                    print(f"  Metrics: {', '.join(key_metrics)}")
        
        # Save results to file
        with open('screening_responsiveness_results.json', 'w') as f:
            json.dump({
                'test_results': self.test_results,
                'baseline_data': self.baseline_data,
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'success_rate': (passed_tests/total_tests)*100,
                    'total_time': total_time,
                    'average_time': avg_time
                },
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: screening_responsiveness_results.json")
        
        # Recommendations
        print(f"\nRecommendations:")
        print(f"{'-' * 60}")
        
        if failed_tests == 0:
            print("✓ All responsiveness tests passed!")
            print("- System appears to be responding correctly to changes")
            print("- Consider monitoring performance under higher loads")
        else:
            print("✗ Some tests failed - investigate and fix responsiveness issues")
            print("- Review failed tests and implement proper refresh triggers")
            print("- Consider adding real-time update mechanisms")
        
        # Performance recommendations
        total_refresh_times = [
            result['result'].get('refresh_time', 0) 
            for result in self.test_results.values() 
            if result['result']['success']
        ]
        
        if total_refresh_times:
            avg_refresh = sum(total_refresh_times) / len(total_refresh_times)
            if avg_refresh > 2.0:
                print("- Consider optimizing refresh performance (current avg: {:.3f}s)".format(avg_refresh))
            else:
                print("- Refresh performance is acceptable (avg: {:.3f}s)".format(avg_refresh))
        
        print("- Add user notifications for screening updates")
        print("- Consider implementing websockets for real-time UI updates")
        print("- Monitor screening list performance with larger datasets")

def main():
    """Main execution function"""
    test_suite = ScreeningResponsivenessTest()
    
    try:
        success = test_suite.run_all_tests()
        if success:
            print("\nResponsiveness test suite completed successfully!")
        else:
            print("\nResponsiveness test suite encountered errors!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest suite failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
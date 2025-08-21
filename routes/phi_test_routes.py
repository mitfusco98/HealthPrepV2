"""
PHI Filter Testing Routes
Comprehensive PHI redaction testing interface for HIPAA compliance validation
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
import logging
import re
import json
from datetime import datetime

from ocr.phi_filter import PHIFilter
from models import PHIFilterSettings, db, log_admin_event

logger = logging.getLogger(__name__)

phi_test_bp = Blueprint('phi_test', __name__, url_prefix='/admin/dashboard/phi')

@phi_test_bp.route('/test')
@login_required
def test_interface():
    """Display PHI filter testing interface"""
    if not current_user.is_admin_user():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('ui.dashboard'))
    
    # Get current PHI filter settings
    phi_settings = PHIFilterSettings.query.first()
    if not phi_settings:
        phi_settings = PHIFilterSettings()
        db.session.add(phi_settings)
        db.session.commit()
    
    # Prepare test samples
    test_samples = [
        {
            'name': 'Social Security Numbers',
            'examples': [
                'SSN: 123-45-6789',
                'Social Security Number 987654321',
                'SS# 555-44-3333'
            ]
        },
        {
            'name': 'Names & Personal Info',
            'examples': [
                'Patient Name: Jane Doe',
                'John Smith, age 45',
                'Contact: Mary Johnson'
            ]
        },
        {
            'name': 'Addresses',
            'examples': [
                'Address: 123 Sesame Street, New York, NY 10001',
                'Lives at 456 Oak Avenue, Suite 2B',
                '789 Main St, Anytown, CA 90210'
            ]
        },
        {
            'name': 'Phone Numbers',
            'examples': [
                'Phone: (555) 123-4567',
                'Call 555.987.6543',
                'Mobile: +1-800-555-0199'
            ]
        },
        {
            'name': 'Email Addresses',
            'examples': [
                'Email: patient@example.com',
                'Contact: john.doe@healthcare.org',
                'Send to: info@clinic.net'
            ]
        },
        {
            'name': 'Dates',
            'examples': [
                'Date of Birth: 03/15/1985',
                'Appointment: December 25, 2023',
                'Born on 1985-03-15'
            ]
        },
        {
            'name': 'Medical Record Numbers',
            'examples': [
                'MRN: 12345678',
                'Medical Record #: MR-2023-001',
                'Patient ID: P-987654'
            ]
        }
    ]
    
    return render_template('admin/phi_test.html',
                         phi_settings=phi_settings,
                         test_samples=test_samples)

@phi_test_bp.route('/process', methods=['POST'])
@login_required
def process_test():
    """Process test input through PHI filter and return results"""
    if not current_user.is_admin_user():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        test_input = data.get('input', '')
        
        if not test_input:
            return jsonify({'error': 'No input provided'}), 400
        
        # Get PHI filter settings
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings()
        
        # Create PHI filter instance
        phi_filter = PHIFilter()
        
        # Process the input
        filtered_text = phi_filter.filter_phi(test_input)
        
        # Get detailed analysis
        analysis = analyze_phi_detections(test_input, filtered_text, phi_filter)
        
        # Log the test activity
        log_admin_event(
            'phi_test',
            current_user.id,
            current_user.org_id,
            request.remote_addr,
            data={'input_length': len(test_input), 'redactions': len(analysis['detections'])},
            action_details='PHI filter test performed'
        )
        
        return jsonify({
            'success': True,
            'original': test_input,
            'filtered': filtered_text,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error processing PHI test: {str(e)}")
        return jsonify({'error': str(e)}), 500

@phi_test_bp.route('/batch-test', methods=['POST'])
@login_required
def batch_test():
    """Run batch testing on predefined samples"""
    if not current_user.is_admin_user():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get PHI filter settings
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings()
        
        # Create PHI filter instance
        phi_filter = PHIFilter()
        
        # Predefined test cases
        test_cases = [
            "Patient: John Doe, SSN: 123-45-6789, DOB: 03/15/1985",
            "Address: 123 Main St, Anytown, CA 90210, Phone: (555) 123-4567",
            "Email: patient@example.com, MRN: 12345678",
            "Emergency Contact: Jane Smith, 555-987-6543",
            "Insurance ID: ABC123456789, Group: XYZ-001",
            "Physician: Dr. Sarah Johnson, NPI: 1234567890"
        ]
        
        results = []
        total_detections = 0
        
        for i, test_case in enumerate(test_cases):
            filtered = phi_filter.filter_phi(test_case)
            analysis = analyze_phi_detections(test_case, filtered, phi_filter)
            
            results.append({
                'test_id': i + 1,
                'original': test_case,
                'filtered': filtered,
                'detections': len(analysis['detections']),
                'analysis': analysis
            })
            
            total_detections += len(analysis['detections'])
        
        # Log batch test
        log_admin_event(
            'phi_batch_test',
            current_user.id,
            current_user.org_id,
            request.remote_addr,
            data={'test_cases': len(test_cases), 'total_detections': total_detections},
            action_details='PHI filter batch test completed'
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_tests': len(test_cases),
                'total_detections': total_detections,
                'average_detections': total_detections / len(test_cases)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in batch PHI test: {str(e)}")
        return jsonify({'error': str(e)}), 500

@phi_test_bp.route('/update-settings', methods=['POST'])
@login_required
def update_test_settings():
    """Update PHI filter settings from test interface"""
    if not current_user.is_admin_user():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Get or create PHI settings
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings()
            db.session.add(phi_settings)
        
        # Update settings
        if 'enabled' in data:
            phi_settings.enabled = data['enabled']
        if 'filter_ssn' in data:
            phi_settings.filter_ssn = data['filter_ssn']
        if 'filter_phone' in data:
            phi_settings.filter_phone = data['filter_phone']
        if 'filter_names' in data:
            phi_settings.filter_names = data['filter_names']
        if 'filter_addresses' in data:
            phi_settings.filter_addresses = data['filter_addresses']
        
        db.session.commit()
        
        # Log settings update
        log_admin_event(
            'phi_settings_update',
            current_user.id,
            current_user.org_id,
            request.remote_addr,
            data=data,
            action_details='PHI filter settings updated from test interface'
        )
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating PHI settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

def analyze_phi_detections(original_text: str, filtered_text: str, phi_filter: PHIFilter) -> dict:
    """
    Analyze what PHI was detected and how it was redacted
    """
    analysis = {
        'detections': [],
        'stats': {
            'total_characters': len(original_text),
            'redacted_characters': 0,
            'redaction_percentage': 0
        },
        'patterns_matched': set()
    }
    
    # Find differences between original and filtered text
    i = 0
    j = 0
    
    while i < len(original_text) and j < len(filtered_text):
        if original_text[i] == filtered_text[j]:
            i += 1
            j += 1
        else:
            # Found a redaction
            redaction_start = i
            original_segment = ""
            
            # Find the end of the redacted segment in original text
            while i < len(original_text) and (j >= len(filtered_text) or original_text[i] != filtered_text[j]):
                original_segment += original_text[i]
                i += 1
            
            # Find what it was replaced with
            replacement_start = j
            replacement = ""
            while j < len(filtered_text) and (i >= len(original_text) or filtered_text[j] != original_text[i]):
                replacement += filtered_text[j]
                j += 1
            
            # Determine PHI type
            phi_type = detect_phi_type(original_segment)
            
            analysis['detections'].append({
                'original': original_segment,
                'replacement': replacement,
                'position': redaction_start,
                'length': len(original_segment),
                'phi_type': phi_type
            })
            
            analysis['patterns_matched'].add(phi_type)
            analysis['stats']['redacted_characters'] += len(original_segment)
    
    # Calculate redaction percentage
    if analysis['stats']['total_characters'] > 0:
        analysis['stats']['redaction_percentage'] = round(
            (analysis['stats']['redacted_characters'] / analysis['stats']['total_characters']) * 100, 2
        )
    
    analysis['patterns_matched'] = list(analysis['patterns_matched'])
    
    return analysis

def detect_phi_type(text: str) -> str:
    """Detect the type of PHI based on pattern matching"""
    text = text.strip()
    
    # SSN patterns
    if re.search(r'\d{3}[-\s]?\d{2}[-\s]?\d{4}', text):
        return 'Social Security Number'
    
    # Phone patterns
    if re.search(r'(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', text):
        return 'Phone Number'
    
    # Email patterns
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        return 'Email Address'
    
    # Date patterns
    if re.search(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text) or re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', text):
        return 'Date'
    
    # Address patterns (simple heuristic)
    if any(word in text.lower() for word in ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'lane', 'ln']):
        return 'Address'
    
    # Name patterns (heuristic based on capitalization)
    if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text):
        return 'Name'
    
    # Medical record number patterns
    if re.search(r'\b(MR|MRN|ID)[-#]?\s*[A-Z0-9]+\b', text, re.IGNORECASE):
        return 'Medical Record Number'
    
    return 'Other PHI'
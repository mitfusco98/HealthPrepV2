from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Patient, ScreeningType, Screening, MedicalDocument
from core.engine import ScreeningEngine
from admin.logs import log_admin_action
from app import db
import json
from datetime import datetime

screening_bp = Blueprint('screening', __name__)

@screening_bp.route('/list')
@login_required
def screening_list():
    # Get all patients with their screenings
    patients = Patient.query.all()
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    # Get screening data for display
    screening_data = []
    for patient in patients:
        for screening_type in screening_types:
            # Check if patient is eligible for this screening
            engine = ScreeningEngine()
            if engine.is_eligible(patient, screening_type):
                # Get or create screening record
                screening = Screening.query.filter_by(
                    patient_id=patient.id,
                    screening_type_id=screening_type.id
                ).first()
                
                if not screening:
                    screening = Screening(
                        patient_id=patient.id,
                        screening_type_id=screening_type.id,
                        status='Due'
                    )
                    db.session.add(screening)
                
                screening_data.append({
                    'patient': patient,
                    'screening_type': screening_type,
                    'screening': screening
                })
    
    db.session.commit()
    
    return render_template('screening/screening_list.html',
                         screening_data=screening_data,
                         screening_types=screening_types)

@screening_bp.route('/types')
@login_required
def screening_types():
    types = ScreeningType.query.all()
    return render_template('screening/screening_types.html', screening_types=types)

@screening_bp.route('/add-type', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        keywords = request.form.get('keywords', '').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        
        gender_filter = request.form.get('gender_filter')
        if gender_filter == 'All':
            gender_filter = None
            
        min_age = request.form.get('min_age', type=int)
        max_age = request.form.get('max_age', type=int)
        frequency_value = request.form.get('frequency_value', type=int)
        frequency_unit = request.form.get('frequency_unit')
        
        screening_type = ScreeningType(
            name=name,
            description=description,
            keywords=json.dumps(keywords),
            gender_filter=gender_filter,
            min_age=min_age,
            max_age=max_age,
            frequency_value=frequency_value,
            frequency_unit=frequency_unit
        )
        
        db.session.add(screening_type)
        db.session.commit()
        
        log_admin_action(current_user.id, 'Screening Type Added',
                        f'Added screening type: {name}', request.remote_addr)
        
        flash(f'Screening type "{name}" added successfully', 'success')
        return redirect(url_for('screening.screening_types'))
    
    return render_template('screening/add_screening_type.html')

@screening_bp.route('/refresh')
@login_required
def refresh_screenings():
    """Refresh all screening statuses based on current criteria"""
    engine = ScreeningEngine()
    updated_count = engine.refresh_all_screenings()
    
    log_admin_action(current_user.id, 'Screenings Refreshed',
                    f'Refreshed {updated_count} screening records', request.remote_addr)
    
    flash(f'Successfully refreshed {updated_count} screening records', 'success')
    return redirect(url_for('screening.screening_list'))

@screening_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """API endpoint to get keywords for a screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    try:
        keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
    except (json.JSONDecodeError, TypeError):
        keywords = []
    
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@screening_bp.route('/toggle-status/<int:screening_type_id>', methods=['POST'])
@login_required
def toggle_screening_status(screening_type_id):
    """Toggle active/inactive status of a screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    screening_type.is_active = not screening_type.is_active
    db.session.commit()
    
    status = 'activated' if screening_type.is_active else 'deactivated'
    log_admin_action(current_user.id, 'Screening Type Status Changed',
                    f'{status.title()} screening type: {screening_type.name}', request.remote_addr)
    
    flash(f'Screening type "{screening_type.name}" {status}', 'success')
    return redirect(url_for('screening.screening_types'))

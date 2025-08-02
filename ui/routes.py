"""
Flask routing for user interface
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from models import User
from .views import (
    screening_list, refresh_screenings, generate_prep_sheet,
    manage_screening_types, update_checklist_settings, get_screening_keywords
)

# Create blueprint for UI routes
ui_bp = Blueprint('ui', __name__)

# Authentication routes
@ui_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account has been deactivated', 'error')
                return render_template('auth/login.html')
            
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()
            
            # Redirect to appropriate dashboard based on role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('ui.home'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')

@ui_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('ui.login'))

# Main application routes
@ui_bp.route('/')
@login_required
def home():
    """Home page - redirect to screening list"""
    return redirect(url_for('ui.screening_list'))

@ui_bp.route('/screening')
@login_required
def screening_list_route():
    """Screening list interface"""
    return screening_list()

@ui_bp.route('/screening/refresh', methods=['POST'])
@login_required
def refresh_screenings_route():
    """Refresh screening data"""
    return refresh_screenings()

@ui_bp.route('/prep_sheet')
@login_required
def prep_sheet_route():
    """Generate prep sheet"""
    return generate_prep_sheet()

@ui_bp.route('/screening/types', methods=['GET', 'POST'])
@login_required
def screening_types_route():
    """Manage screening types"""
    return manage_screening_types()

@ui_bp.route('/screening/checklist', methods=['POST'])
@login_required
def checklist_settings_route():
    """Update checklist settings"""
    return update_checklist_settings()

# API routes for AJAX functionality
@ui_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    """Get keywords for a screening type"""
    return get_screening_keywords()

@ui_bp.route('/api/patient-screenings/<int:patient_id>')
@login_required
def api_patient_screenings(patient_id):
    """Get all screenings for a patient"""
    try:
        from models import Screening, ScreeningType
        
        screenings = db.session.query(Screening).join(ScreeningType).filter(
            Screening.patient_id == patient_id,
            ScreeningType.is_active == True
        ).all()
        
        screening_data = []
        for screening in screenings:
            screening_data.append({
                'id': screening.id,
                'screening_type': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed_date.strftime('%m/%d/%Y') if screening.last_completed_date else None,
                'next_due': screening.next_due_date.strftime('%m/%d/%Y') if screening.next_due_date else None
            })
        
        return {'success': True, 'screenings': screening_data}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Error handlers for UI
@ui_bp.errorhandler(404)
def page_not_found(error):
    return render_template('error/404.html'), 404

@ui_bp.errorhandler(403)
def forbidden(error):
    return render_template('error/403.html'), 403

@ui_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error/500.html'), 500


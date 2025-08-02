"""
Flask routes for user interface
"""

from flask import Blueprint
from flask_login import login_required
from .views import UIViews

# Create blueprint
ui_bp = Blueprint('ui', __name__)

# Initialize views
ui_views = UIViews()

# Screening routes
@ui_bp.route('/screening')
@ui_bp.route('/screening/list')
@login_required
def screening_list():
    """Main screening list view with tabs"""
    return ui_views.screening_list()

@ui_bp.route('/screening/refresh', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh all screenings"""
    return ui_views.refresh_screenings()

@ui_bp.route('/screening/refresh/<int:screening_type_id>', methods=['POST'])
@login_required
def refresh_screening_type(screening_type_id):
    """Refresh specific screening type"""
    return ui_views.refresh_screening_type(screening_type_id)

@ui_bp.route('/checklist/settings', methods=['POST'])
@login_required
def update_checklist_settings():
    """Update checklist settings"""
    return ui_views.update_checklist_settings()

# Patient routes
@ui_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail view"""
    return ui_views.patient_detail(patient_id)

@ui_bp.route('/patient/<int:patient_id>/prep-sheet')
@login_required
def prep_sheet_view(patient_id):
    """Standalone prep sheet view"""
    return ui_views.prep_sheet_view(patient_id)

@ui_bp.route('/prep-sheets/batch', methods=['POST'])
@login_required
def batch_prep_sheets():
    """Generate batch prep sheets"""
    return ui_views.batch_prep_sheets()

# Document routes
@ui_bp.route('/document/<int:document_id>')
@login_required
def document_viewer(document_id):
    """Document viewer"""
    return ui_views.document_viewer(document_id)

# API routes
@ui_bp.route('/api/patients/search')
@login_required
def search_patients():
    """Search patients API"""
    return ui_views.search_patients()

@ui_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def screening_keywords_api(screening_type_id):
    """Get screening type keywords API"""
    return ui_views.screening_keywords_api(screening_type_id)

# Auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    from flask import render_template, request, redirect, url_for, flash
    from flask_login import login_user, current_user
    from werkzeug.security import check_password_hash
    from models import User
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to appropriate dashboard
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('ui.screening_list'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    from flask import redirect, url_for, flash
    from flask_login import logout_user, current_user
    
    username = current_user.username
    logout_user()
    flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('auth.login'))

# Register auth blueprint with main app
ui_bp.register_blueprint(auth_bp)


"""
Flask routing for user interface.
Defines URL patterns and connects them to view functions.
"""

from flask import Blueprint, render_template
from flask_login import login_required
from ui.views import UserViews

# Create blueprint for UI routes
ui_bp = Blueprint('ui', __name__)

# Initialize views
views = UserViews()

@ui_bp.route('/')
@ui_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    return views.dashboard()

@ui_bp.route('/screening')
@ui_bp.route('/screening/list')
@login_required
def screening_list():
    """Screening list view"""
    return views.screening_list()

@ui_bp.route('/screening/types')
@login_required
def screening_types():
    """Screening types management"""
    return views.screening_types()

@ui_bp.route('/screening/types/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add new screening type"""
    return views.add_screening_type()

@ui_bp.route('/screening/types/<int:screening_type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(screening_type_id):
    """Edit screening type"""
    return views.edit_screening_type(screening_type_id)

@ui_bp.route('/screening/types/<int:screening_type_id>/delete', methods=['POST'])
@login_required
def delete_screening_type(screening_type_id):
    """Delete screening type"""
    return views.delete_screening_type(screening_type_id)

@ui_bp.route('/screening/refresh', methods=['GET', 'POST'])
@login_required
def refresh_screenings():
    """Refresh screening engine"""
    return views.refresh_screenings()

# Patient routes redirected to screening list (per design intent)
@ui_bp.route('/patients')
@login_required
def patient_list():
    """Redirect patient list to screening list per design intent"""
    from flask import redirect, url_for
    return redirect(url_for('screening.screening_list'))

@ui_bp.route('/patients/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail with prep sheet"""
    return views.patient_detail(patient_id)

@ui_bp.route('/patients/<int:patient_id>/prep-sheet')
@login_required
def prep_sheet(patient_id):
    """Standalone prep sheet"""
    return views.prep_sheet(patient_id)

@ui_bp.route('/documents/<int:document_id>')
@login_required
def document_view(document_id):
    """View document content"""
    return views.document_view(document_id)

# API endpoints
@ui_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    """Get keywords for screening type"""
    return views.api_screening_keywords(screening_type_id)

# Auth routes - redirect to proper auth blueprint
@ui_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Redirect to auth login"""
    from flask import redirect, url_for
    return redirect(url_for('auth.login'))

@ui_bp.route('/logout')
def logout():
    """Redirect to auth logout"""
    from flask import redirect, url_for
    return redirect(url_for('auth.logout'))

@ui_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Redirect to auth register"""
    from flask import redirect, url_for
    return redirect(url_for('auth.register'))

@ui_bp.route('/home')
@login_required
def home():
    """Home page after login"""
    return views.dashboard()

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from models import User, Patient, ScreeningType, Screening, MedicalDocument, AdminLog
from app import db
from datetime import datetime, date
import logging
import os

# Create blueprints
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
api_bp = Blueprint('api', __name__, url_prefix='/api')

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

# Authentication Routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log the login
            log_admin_action('user_login', f'User {username} logged in')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_admin_action('user_logout', f'User {current_user.username} logged out')
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

# Main Routes
@main_bp.route('/')
@login_required
def index():
    """Main dashboard showing recent activity and quick links"""
    recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(10).all()
    screening_stats = get_screening_statistics()
    
    return render_template('screening_list.html', 
                         patients=recent_patients,
                         stats=screening_stats,
                         current_tab='list')

@main_bp.route('/patients')
@login_required
def patients():
    """Patient list view"""
    search = request.args.get('search', '')
    
    query = Patient.query
    if search:
        query = query.filter(
            (Patient.first_name.contains(search)) |
            (Patient.last_name.contains(search)) |
            (Patient.mrn.contains(search))
        )
    
    patients = query.order_by(Patient.last_name, Patient.first_name).all()
    return render_template('patients/list.html', patients=patients, search=search)

@main_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail view with screening information"""
    patient = Patient.query.get_or_404(patient_id)
    screenings = Screening.query.filter_by(patient_id=patient_id).all()
    documents = MedicalDocument.query.filter_by(patient_id=patient_id).order_by(MedicalDocument.document_date.desc()).all()
    
    return render_template('patients/detail.html', 
                         patient=patient, 
                         screenings=screenings,
                         documents=documents)

@main_bp.route('/screenings')
@login_required
def screenings():
    """Screening list view with filtering options"""
    patient_filter = request.args.get('patient', '')
    status_filter = request.args.get('status', '')
    screening_type_filter = request.args.get('screening_type', '')
    
    query = db.session.query(Screening).join(Patient).join(ScreeningType)
    
    if patient_filter:
        query = query.filter(
            (Patient.first_name.contains(patient_filter)) |
            (Patient.last_name.contains(patient_filter)) |
            (Patient.mrn.contains(patient_filter))
        )
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if screening_type_filter:
        query = query.filter(ScreeningType.name.contains(screening_type_filter))
    
    screenings = query.order_by(Patient.last_name, Patient.first_name).all()
    
    # Get filter options
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    screening_types = ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
    status_options = ['Due', 'Due Soon', 'Complete', 'Overdue']
    
    return render_template('screening_list.html',
                         screenings=screenings,
                         patients=patients,
                         screening_types=screening_types,
                         status_options=status_options,
                         current_tab='list')

@main_bp.route('/screening-types')
@login_required
def screening_types():
    """Screening types management view"""
    screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
    return render_template('screening_list.html',
                         screening_types=screening_types,
                         current_tab='types')

@main_bp.route('/prep-sheet/<int:patient_id>')
@login_required
def prep_sheet(patient_id):
    """Generate and display prep sheet for patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate prep sheet data
    from prep_sheet.generator import PrepSheetGenerator
    generator = PrepSheetGenerator()
    prep_data = generator.generate_prep_sheet(patient)
    
    log_admin_action('prep_sheet_generated', f'Prep sheet generated for patient {patient.mrn}')
    
    return render_template('prep_sheet.html', patient=patient, prep_data=prep_data)

# Admin Routes
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard with system statistics"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    
    stats = get_admin_statistics()
    recent_logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(20).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)

@admin_bp.route('/ocr')
@login_required
def ocr_dashboard():
    """OCR processing dashboard"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    
    from ocr.monitor import OCRMonitor
    monitor = OCRMonitor()
    ocr_stats = monitor.get_processing_stats()
    
    return render_template('admin/ocr_dashboard.html', stats=ocr_stats)

@admin_bp.route('/logs')
@login_required
def logs():
    """Admin logs viewer"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = AdminLog.query.order_by(AdminLog.created_at.desc())
    
    # Apply filters
    action_filter = request.args.get('action')
    user_filter = request.args.get('user')
    date_filter = request.args.get('date')
    
    if action_filter:
        query = query.filter(AdminLog.action.contains(action_filter))
    
    if user_filter:
        query = query.join(User).filter(User.username.contains(user_filter))
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(AdminLog.created_at >= filter_date)
        except ValueError:
            pass
    
    logs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/logs.html', logs=logs)

@admin_bp.route('/phi-settings')
@login_required
def phi_settings():
    """PHI filtering settings"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    
    from models import PHIFilterSettings
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('admin/phi_settings.html', settings=settings)

# API Routes
@api_bp.route('/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """Get keywords for a screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    keywords = screening_type.keywords or []
    
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@api_bp.route('/refresh-screenings', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh screening statuses using the screening engine"""
    try:
        from core.engine import ScreeningEngine
        engine = ScreeningEngine()
        
        # Get optional patient filter
        patient_id = request.json.get('patient_id') if request.json else None
        
        if patient_id:
            patient = Patient.query.get(patient_id)
            if patient:
                engine.process_patient_screenings(patient)
        else:
            engine.refresh_all_screenings()
        
        log_admin_action('screenings_refreshed', f'Screenings refreshed by {current_user.username}')
        
        return jsonify({
            'success': True,
            'message': 'Screenings refreshed successfully'
        })
    
    except Exception as e:
        logging.error(f"Error refreshing screenings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper Functions
def log_admin_action(action, description=None):
    """Log an admin action"""
    try:
        log = AdminLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            description=description,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log admin action: {str(e)}")

def get_screening_statistics():
    """Get screening statistics for dashboard"""
    total_screenings = Screening.query.count()
    due_screenings = Screening.query.filter_by(status='Due').count()
    overdue_screenings = Screening.query.filter_by(status='Overdue').count()
    complete_screenings = Screening.query.filter_by(status='Complete').count()
    
    return {
        'total': total_screenings,
        'due': due_screenings,
        'overdue': overdue_screenings,
        'complete': complete_screenings
    }

def get_admin_statistics():
    """Get admin statistics for dashboard"""
    total_patients = Patient.query.count()
    total_documents = MedicalDocument.query.count()
    processed_documents = MedicalDocument.query.filter_by(is_processed=True).count()
    total_users = User.query.count()
    
    return {
        'total_patients': total_patients,
        'total_documents': total_documents,
        'processed_documents': processed_documents,
        'total_users': total_users,
        'processing_rate': (processed_documents / total_documents * 100) if total_documents > 0 else 0
    }

# Error Handlers
@main_bp.app_errorhandler(400)
def bad_request(error):
    return render_template('error/400.html'), 400

@main_bp.app_errorhandler(401)
def unauthorized(error):
    return render_template('error/401.html'), 401

@main_bp.app_errorhandler(403)
def forbidden(error):
    return render_template('error/403.html'), 403

@main_bp.app_errorhandler(404)
def not_found(error):
    return render_template('error/404.html'), 404

@main_bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error/500.html'), 500

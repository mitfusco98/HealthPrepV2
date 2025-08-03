from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import User, Patient, ScreeningType, Screening, Document, AdminLog, ChecklistSettings, PHISettings
from forms import LoginForm, ScreeningTypeForm, PatientForm
from core.engine import ScreeningEngine
from admin.logs import log_admin_action
from admin.analytics import calculate_hours_saved
from utils import require_admin, get_confidence_class
import os
from datetime import datetime, timedelta

@app.route('/')
def index():
    """Landing page - shows login for guests, dashboard for users"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('screening_list'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    return redirect(url_for('index'))

@app.route('/screening/list')
@login_required
def screening_list():
    """Main screening list interface"""
    page = request.args.get('page', 1, type=int)
    patient_filter = request.args.get('patient', '')
    status_filter = request.args.get('status', '')
    screening_type_filter = request.args.get('screening_type', '')
    
    # Build query
    query = db.session.query(Screening).join(Patient).join(ScreeningType)
    
    if patient_filter:
        query = query.filter(
            (Patient.first_name.ilike(f'%{patient_filter}%')) |
            (Patient.last_name.ilike(f'%{patient_filter}%'))
        )
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if screening_type_filter:
        query = query.filter(ScreeningType.id == screening_type_filter)
    
    screenings = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get screening types for filter dropdown
    screening_types = ScreeningType.query.filter_by(status='active').all()
    
    return render_template('screening/list.html', 
                         screenings=screenings,
                         screening_types=screening_types,
                         current_filters={
                             'patient': patient_filter,
                             'status': status_filter,
                             'screening_type': screening_type_filter
                         })

@app.route('/screening/types')
@login_required
def screening_types():
    """Screening types management"""
    screening_types = ScreeningType.query.all()
    return render_template('screening/types.html', screening_types=screening_types)

@app.route('/screening/types/add', methods=['GET', 'POST'])
@login_required
@require_admin
def add_screening_type():
    """Add new screening type"""
    form = ScreeningTypeForm()
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            keywords=form.keywords.data.split(',') if form.keywords.data else [],
            eligibility_criteria={
                'gender': form.gender.data,
                'min_age': form.min_age.data,
                'max_age': form.max_age.data
            },
            frequency_value=form.frequency_value.data,
            frequency_unit=form.frequency_unit.data,
            trigger_conditions=form.trigger_conditions.data.split(',') if form.trigger_conditions.data else []
        )
        
        db.session.add(screening_type)
        db.session.commit()
        
        log_admin_action(current_user.id, 'create', 'screening_type', screening_type.id,
                        {'name': screening_type.name})
        
        flash('Screening type added successfully', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/add_type.html', form=form)

@app.route('/screening/checklist')
@login_required
@require_admin
def checklist_settings():
    """Checklist configuration settings"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('screening/checklist_settings.html', settings=settings)

@app.route('/screening/refresh', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh screening calculations"""
    try:
        engine = ScreeningEngine()
        updated_count = engine.refresh_all_screenings()
        
        log_admin_action(current_user.id, 'refresh', 'screenings', None,
                        {'updated_count': updated_count})
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} screenings',
            'updated_count': updated_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error refreshing screenings: {str(e)}'
        }), 500

@app.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail page"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Get recent screenings
    screenings = Screening.query.filter_by(patient_id=patient_id)\
                              .join(ScreeningType)\
                              .order_by(Screening.updated_at.desc()).all()
    
    # Get recent documents
    documents = Document.query.filter_by(patient_id=patient_id)\
                            .order_by(Document.upload_date.desc()).limit(10).all()
    
    return render_template('patient/detail.html', 
                         patient=patient,
                         screenings=screenings,
                         documents=documents)

@app.route('/prep-sheet/<int:patient_id>')
@login_required
def prep_sheet(patient_id):
    """Generate prep sheet for patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Get screening data
    screenings = Screening.query.filter_by(patient_id=patient_id)\
                              .join(ScreeningType)\
                              .filter(ScreeningType.status == 'active').all()
    
    # Get recent medical data based on checklist settings
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
    
    cutoff_date = datetime.utcnow() - timedelta(days=settings.labs_cutoff_months * 30)
    
    # Get recent documents
    recent_documents = Document.query.filter_by(patient_id=patient_id)\
                                   .filter(Document.document_date >= cutoff_date)\
                                   .order_by(Document.document_date.desc()).all()
    
    return render_template('prep_sheet/template.html',
                         patient=patient,
                         screenings=screenings,
                         documents=recent_documents,
                         prep_date=datetime.utcnow())

# Admin routes
@app.route('/admin/dashboard')
@login_required
@require_admin
def admin_dashboard():
    """Admin dashboard"""
    # Get system statistics
    stats = {
        'total_patients': Patient.query.count(),
        'total_screenings': Screening.query.count(),
        'due_screenings': Screening.query.filter_by(status='due').count(),
        'total_documents': Document.query.count(),
        'ocr_processed': Document.query.filter_by(ocr_processed=True).count(),
        'hours_saved': calculate_hours_saved()
    }
    
    # Get recent activity
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)

@app.route('/admin/ocr')
@login_required
@require_admin
def admin_ocr_dashboard():
    """OCR monitoring dashboard"""
    # Get OCR statistics
    total_docs = Document.query.count()
    processed_docs = Document.query.filter_by(ocr_processed=True).count()
    pending_docs = Document.query.filter_by(ocr_processed=False).count()
    
    # Get confidence distribution
    high_confidence = Document.query.filter(Document.ocr_confidence >= 0.8).count()
    medium_confidence = Document.query.filter(
        Document.ocr_confidence >= 0.6,
        Document.ocr_confidence < 0.8
    ).count()
    low_confidence = Document.query.filter(Document.ocr_confidence < 0.6).count()
    
    stats = {
        'total_documents': total_docs,
        'processed_documents': processed_docs,
        'pending_documents': pending_docs,
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'low_confidence': low_confidence,
        'success_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0
    }
    
    # Get recent OCR activity
    recent_documents = Document.query.filter_by(ocr_processed=True)\
                                   .order_by(Document.upload_date.desc()).limit(20).all()
    
    return render_template('admin/ocr_dashboard.html', 
                         stats=stats, 
                         recent_documents=recent_documents,
                         get_confidence_class=get_confidence_class)

@app.route('/admin/phi')
@login_required
@require_admin
def admin_phi_settings():
    """PHI filtering settings"""
    settings = PHISettings.query.first()
    if not settings:
        settings = PHISettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('admin/phi_settings.html', settings=settings)

@app.route('/admin/logs')
@login_required
@require_admin
def admin_logs():
    """Admin activity logs"""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    
    query = AdminLog.query
    
    if action_filter:
        query = query.filter(AdminLog.action == action_filter)
    
    if user_filter:
        query = query.join(User).filter(User.username.ilike(f'%{user_filter}%'))
    
    logs = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('admin/logs.html', logs=logs, 
                         current_filters={'action': action_filter, 'user': user_filter})

# API endpoints
@app.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    """API endpoint to get screening type keywords"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    return jsonify({
        'success': True,
        'keywords': screening_type.keywords or []
    })

@app.context_processor
def inject_cache_timestamp():
    """Inject cache timestamp for static files"""
    return {'cache_timestamp': int(datetime.utcnow().timestamp())}

@app.template_filter('confidence_class')
def confidence_class_filter(confidence):
    """Template filter for confidence CSS classes"""
    return get_confidence_class(confidence)

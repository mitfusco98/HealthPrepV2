from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta
from models import User, AdminLog, PHIFilterSettings, PrepSheetSettings, MedicalDocument
from admin.logs import log_admin_action
from admin.analytics import get_system_analytics
from app import db
import json

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Get system analytics
    analytics = get_system_analytics()
    
    # Get recent activity (last 10 logs)
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    # Get user count
    user_count = User.query.count()
    
    # Get document processing stats
    total_docs = MedicalDocument.query.count()
    ocr_processed = MedicalDocument.query.filter(MedicalDocument.ocr_text.isnot(None)).count()
    
    return render_template('admin/admin_dashboard.html',
                         analytics=analytics,
                         recent_logs=recent_logs,
                         user_count=user_count,
                         total_docs=total_docs,
                         ocr_processed=ocr_processed)

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filter parameters
    event_type = request.args.get('event_type')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = request.args.get('user_id')
    
    query = AdminLog.query
    
    # Apply filters
    if event_type:
        query = query.filter(AdminLog.action.contains(event_type))
    if date_from:
        query = query.filter(AdminLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(AdminLog.timestamp <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    if user_id:
        query = query.filter(AdminLog.user_id == user_id)
    
    logs = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    # Get all users for filter dropdown
    users = User.query.all()
    
    return render_template('admin/admin_logs.html', logs=logs, users=users)

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    # OCR processing statistics
    total_docs = MedicalDocument.query.count()
    ocr_processed = MedicalDocument.query.filter(MedicalDocument.ocr_text.isnot(None)).count()
    pending_ocr = total_docs - ocr_processed
    
    # Confidence statistics
    high_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence >= 0.8).count()
    medium_confidence = MedicalDocument.query.filter(
        MedicalDocument.ocr_confidence >= 0.5, 
        MedicalDocument.ocr_confidence < 0.8
    ).count()
    low_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence < 0.5).count()
    
    # Recent processing activity
    recent_docs = MedicalDocument.query.filter(
        MedicalDocument.upload_date >= datetime.utcnow() - timedelta(days=7)
    ).order_by(MedicalDocument.upload_date.desc()).limit(20).all()
    
    return render_template('admin/ocr_dashboard.html',
                         total_docs=total_docs,
                         ocr_processed=ocr_processed,
                         pending_ocr=pending_ocr,
                         high_confidence=high_confidence,
                         medium_confidence=medium_confidence,
                         low_confidence=low_confidence,
                         recent_docs=recent_docs)

@admin_bp.route('/phi')
@login_required
@admin_required
def phi_settings():
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('admin/phi_settings.html', settings=settings)

@admin_bp.route('/phi/update', methods=['POST'])
@login_required
@admin_required
def update_phi_settings():
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
    
    settings.filter_enabled = 'filter_enabled' in request.form
    settings.filter_ssn = 'filter_ssn' in request.form
    settings.filter_phone = 'filter_phone' in request.form
    settings.filter_mrn = 'filter_mrn' in request.form
    settings.filter_insurance = 'filter_insurance' in request.form
    settings.filter_addresses = 'filter_addresses' in request.form
    settings.filter_names = 'filter_names' in request.form
    settings.filter_dates = 'filter_dates' in request.form
    settings.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    log_admin_action(current_user.id, 'PHI Settings Update', 
                    'Updated PHI filtering settings', request.remote_addr)
    
    flash('PHI filtering settings updated successfully', 'success')
    return redirect(url_for('admin.phi_settings'))

@admin_bp.route('/export-logs')
@login_required
@admin_required
def export_logs():
    logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).all()
    
    log_data = []
    for log in logs:
        log_data.append({
            'id': log.id,
            'user': log.user.username if log.user else 'System',
            'action': log.action,
            'details': log.details,
            'ip_address': log.ip_address,
            'timestamp': log.timestamp.isoformat()
        })
    
    log_admin_action(current_user.id, 'Log Export', 
                    f'Exported {len(log_data)} admin logs', request.remote_addr)
    
    return jsonify({
        'success': True,
        'data': log_data,
        'count': len(log_data)
    })

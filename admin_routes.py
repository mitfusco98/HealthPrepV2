from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
from app import db
from models import User, AdminLog, OCRProcessingStats, PHIFilterSettings, ChecklistSettings
from admin.logs import AdminLogManager
from admin.analytics import AdminAnalytics
from admin.config import AdminConfig
import logging
import json
from datetime import datetime, timedelta
import io

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin privileges required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    analytics = AdminAnalytics()
    
    # Get recent activity
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    # Get system statistics
    stats = {
        'total_users': User.query.count(),
        'total_patients': db.session.execute(db.text("SELECT COUNT(*) FROM patients")).scalar(),
        'total_documents': db.session.execute(db.text("SELECT COUNT(*) FROM medical_documents")).scalar(),
        'total_screenings': db.session.execute(db.text("SELECT COUNT(*) FROM patient_screenings")).scalar(),
        'due_screenings': db.session.execute(db.text("SELECT COUNT(*) FROM patient_screenings WHERE status = 'due'")).scalar(),
    }
    
    # Get OCR processing stats
    ocr_stats = OCRProcessingStats.query.first()
    if not ocr_stats:
        ocr_stats = OCRProcessingStats()
        db.session.add(ocr_stats)
        db.session.commit()
    
    return render_template('admin/admin_dashboard.html',
                         recent_logs=recent_logs,
                         stats=stats,
                         ocr_stats=ocr_stats,
                         analytics=analytics.get_dashboard_data())

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin logs viewer with filtering"""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AdminLog.query
    
    # Apply filters
    if action_filter:
        query = query.filter(AdminLog.action.ilike(f'%{action_filter}%'))
    
    if user_filter:
        query = query.join(User).filter(User.username.ilike(f'%{user_filter}%'))
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AdminLog.timestamp >= date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AdminLog.timestamp < date_to_dt)
        except ValueError:
            pass
    
    logs = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get unique actions for filter dropdown
    actions = db.session.query(AdminLog.action).distinct().all()
    action_list = [action[0] for action in actions]
    
    return render_template('admin/admin_logs.html',
                         logs=logs,
                         action_filter=action_filter,
                         user_filter=user_filter,
                         date_from=date_from,
                         date_to=date_to,
                         action_list=action_list)

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export admin logs as JSON"""
    logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).all()
    
    log_data = []
    for log in logs:
        log_data.append({
            'id': log.id,
            'user': log.user.username if log.user else 'System',
            'action': log.action,
            'details': log.details,
            'ip_address': log.ip_address,
            'timestamp': log.timestamp.isoformat(),
        })
    
    # Create JSON file in memory
    json_data = json.dumps(log_data, indent=2)
    buffer = io.BytesIO()
    buffer.write(json_data.encode('utf-8'))
    buffer.seek(0)
    
    filename = f"admin_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return send_file(
        buffer,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR processing dashboard"""
    ocr_stats = OCRProcessingStats.query.first()
    if not ocr_stats:
        # Initialize stats if they don't exist
        ocr_stats = OCRProcessingStats()
        db.session.add(ocr_stats)
        db.session.commit()
    
    # Get recent processing activity (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_documents = db.session.execute(
        db.text("SELECT COUNT(*) FROM medical_documents WHERE processed_at >= :date"),
        {"date": seven_days_ago}
    ).scalar()
    
    # Get confidence distribution
    confidence_stats = db.session.execute(
        db.text("""
            SELECT 
                CASE 
                    WHEN ocr_confidence >= 0.9 THEN 'high'
                    WHEN ocr_confidence >= 0.7 THEN 'medium'
                    ELSE 'low'
                END as confidence_level,
                COUNT(*) as count
            FROM medical_documents 
            WHERE ocr_text IS NOT NULL 
            GROUP BY confidence_level
        """)
    ).fetchall()
    
    return render_template('admin/admin_ocr_dashboard.html',
                         ocr_stats=ocr_stats,
                         recent_documents=recent_documents,
                         confidence_stats=confidence_stats)

@admin_bp.route('/phi')
@login_required
@admin_required
def phi_settings():
    """PHI filtering settings"""
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
    """Update PHI filtering settings"""
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
    
    # Update settings from form
    settings.filter_enabled = 'filter_enabled' in request.form
    settings.filter_ssn = 'filter_ssn' in request.form
    settings.filter_phone = 'filter_phone' in request.form
    settings.filter_mrn = 'filter_mrn' in request.form
    settings.filter_insurance = 'filter_insurance' in request.form
    settings.filter_addresses = 'filter_addresses' in request.form
    settings.filter_names = 'filter_names' in request.form
    settings.filter_dates = 'filter_dates' in request.form
    
    confidence_threshold = request.form.get('confidence_threshold')
    if confidence_threshold:
        try:
            settings.confidence_threshold = float(confidence_threshold)
        except ValueError:
            flash('Invalid confidence threshold value', 'error')
            return redirect(url_for('admin.phi_settings'))
    
    db.session.commit()
    
    # Log the change
    log_entry = AdminLog(
        user_id=current_user.id,
        action='phi_settings_update',
        details='PHI filtering settings updated',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash('PHI filtering settings updated successfully', 'success')
    return redirect(url_for('admin.phi_settings'))

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management page"""
    users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/system-info')
@login_required
@admin_required
def system_info():
    """System information and health check"""
    import sys
    import platform
    
    system_info = {
        'python_version': sys.version,
        'platform': platform.platform(),
        'database_url': 'configured' if db.engine.url else 'not configured',
        'upload_folder': current_app.config.get('UPLOAD_FOLDER', 'not configured'),
    }
    
    return render_template('admin/system_info.html', system_info=system_info)

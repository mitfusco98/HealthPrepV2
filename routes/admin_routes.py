"""
Admin dashboard and management routes
Handles administrative functions, logging, and system monitoring
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import User, AdminLog, PHIFilterSettings, OCRProcessingStats
from forms import PHIFilterForm
from routes.auth_routes import admin_required
from admin.logs import AdminLogger
from admin.analytics import AdminAnalytics
from admin.config import AdminConfig
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter
from app import db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)
admin_logger = AdminLogger()

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main admin dashboard"""
    analytics = AdminAnalytics()
    
    # Get dashboard statistics
    stats = analytics.get_dashboard_stats()
    
    # Get recent activity
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    # Get system health info
    health_info = analytics.get_system_health()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_logs=recent_logs,
                         health_info=health_info)

@admin_bp.route('/logs')
@admin_required
def logs():
    """Admin logs viewer"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Filter parameters
    event_type = request.args.get('event_type', '')
    user_id = request.args.get('user_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    query = AdminLog.query
    
    if event_type:
        query = query.filter(AdminLog.action.ilike(f'%{event_type}%'))
    
    if user_id:
        query = query.filter(AdminLog.user_id == int(user_id))
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AdminLog.timestamp >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AdminLog.timestamp < to_date)
        except ValueError:
            pass
    
    # Get paginated results
    logs_pagination = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get filter options
    users = User.query.order_by(User.username).all()
    event_types = db.session.query(AdminLog.action).distinct().all()
    event_types = [et[0] for et in event_types]
    
    # Get statistics
    total_logs = query.count()
    today_logs = query.filter(AdminLog.timestamp >= datetime.now().date()).count()
    
    return render_template('admin/logs.html',
                         logs=logs_pagination.items,
                         pagination=logs_pagination,
                         users=users,
                         event_types=event_types,
                         filters={
                             'event_type': event_type,
                             'user_id': user_id,
                             'date_from': date_from,
                             'date_to': date_to
                         },
                         stats={
                             'total_logs': total_logs,
                             'today_logs': today_logs
                         })

@admin_bp.route('/logs/export')
@admin_required
def export_logs():
    """Export admin logs as JSON"""
    # Filter parameters (same as logs view)
    event_type = request.args.get('event_type', '')
    user_id = request.args.get('user_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    admin_logs = AdminLogger()
    
    try:
        exported_data = admin_logs.export_logs(
            event_type=event_type or None,
            user_id=int(user_id) if user_id else None,
            date_from=date_from or None,
            date_to=date_to or None
        )
        
        # Log the export action
        admin_logger.log_action(
            user_id=current_user.id,
            action='logs_exported',
            resource_type='admin_log',
            details={
                'filters': {
                    'event_type': event_type,
                    'user_id': user_id,
                    'date_from': date_from,
                    'date_to': date_to
                },
                'exported_count': len(exported_data.get('logs', []))
            },
            ip_address=request.remote_addr
        )
        
        return jsonify(exported_data)
        
    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/ocr')
@admin_required
def ocr_dashboard():
    """OCR monitoring dashboard"""
    monitor = OCRMonitor()
    
    # Get comprehensive OCR statistics
    dashboard_stats = monitor.get_dashboard_stats()
    
    # Get low quality documents for review
    low_quality_docs = monitor.get_low_quality_documents(limit=20)
    
    # Get processing trends
    trends = monitor.get_processing_trends(days=30)
    
    # Get document type analysis
    type_analysis = monitor.get_document_type_analysis()
    
    return render_template('admin/ocr_dashboard.html',
                         stats=dashboard_stats,
                         low_quality_docs=low_quality_docs,
                         trends=trends,
                         type_analysis=type_analysis)

@admin_bp.route('/phi')
@admin_required
def phi_settings():
    """PHI filtering settings"""
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = PHIFilterForm(obj=settings)
    
    # Get PHI filtering statistics
    phi_filter = PHIFilter()
    filter_stats = phi_filter.get_filter_statistics()
    
    return render_template('admin/phi_settings.html',
                         form=form,
                         settings=settings,
                         stats=filter_stats)

@admin_bp.route('/phi/update', methods=['POST'])
@admin_required
def update_phi_settings():
    """Update PHI filtering settings"""
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
    
    form = PHIFilterForm()
    
    if form.validate_on_submit():
        # Update settings
        settings.is_enabled = form.is_enabled.data
        settings.filter_ssn = form.filter_ssn.data
        settings.filter_phone = form.filter_phone.data
        settings.filter_mrn = form.filter_mrn.data
        settings.filter_insurance = form.filter_insurance.data
        settings.filter_addresses = form.filter_addresses.data
        settings.filter_names = form.filter_names.data
        settings.filter_dates = form.filter_dates.data
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='phi_settings_updated',
            resource_type='phi_settings',
            resource_id=settings.id,
            details={
                'is_enabled': settings.is_enabled,
                'filter_types': {
                    'ssn': settings.filter_ssn,
                    'phone': settings.filter_phone,
                    'mrn': settings.filter_mrn,
                    'insurance': settings.filter_insurance,
                    'addresses': settings.filter_addresses,
                    'names': settings.filter_names,
                    'dates': settings.filter_dates
                }
            },
            ip_address=request.remote_addr
        )
        
        flash('PHI filtering settings updated successfully!', 'success')
    else:
        flash('Error updating PHI settings. Please check the form.', 'error')
    
    return redirect(url_for('admin.phi_settings'))

@admin_bp.route('/phi/test', methods=['POST'])
@admin_required
def test_phi_filter():
    """Test PHI filtering on sample text"""
    test_text = request.form.get('test_text', '')
    
    if not test_text:
        return jsonify({'error': 'No test text provided'})
    
    phi_filter = PHIFilter()
    
    try:
        result = phi_filter.test_filter(test_text)
        
        # Log the test
        admin_logger.log_action(
            user_id=current_user.id,
            action='phi_filter_tested',
            resource_type='phi_settings',
            details={
                'text_length': len(test_text),
                'items_filtered': result['statistics'].get('total_filtered', 0)
            },
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error testing PHI filter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users')
@admin_required
def users():
    """User management page"""
    users = User.query.order_by(User.username).all()
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_user_admin(user_id):
    """Toggle admin status for a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Cannot modify your own admin status.', 'error')
        return redirect(url_for('admin.users'))
    
    old_status = user.is_admin
    user.is_admin = not user.is_admin
    
    db.session.commit()
    
    # Log the action
    admin_logger.log_action(
        user_id=current_user.id,
        action='user_admin_toggled',
        resource_type='user',
        resource_id=user.id,
        details={
            'username': user.username,
            'old_admin_status': old_status,
            'new_admin_status': user.is_admin
        },
        ip_address=request.remote_addr
    )
    
    status_text = 'granted' if user.is_admin else 'revoked'
    flash(f'Admin privileges {status_text} for user {user.username}.', 'success')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/system-info')
@admin_required
def system_info():
    """System information and diagnostics"""
    analytics = AdminAnalytics()
    config = AdminConfig()
    
    system_info = {
        'database': analytics.get_database_info(),
        'application': config.get_app_info(),
        'performance': analytics.get_performance_metrics(),
        'security': config.get_security_info()
    }
    
    return render_template('admin/system_info.html', system_info=system_info)

# API endpoints for admin dashboard

@admin_bp.route('/api/stats')
@admin_required
def api_dashboard_stats():
    """Get dashboard statistics via API"""
    analytics = AdminAnalytics()
    stats = analytics.get_dashboard_stats()
    
    return jsonify({
        'success': True,
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    })

@admin_bp.route('/api/recent-activity')
@admin_required
def api_recent_activity():
    """Get recent activity via API"""
    limit = request.args.get('limit', 10, type=int)
    
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
    
    activity = []
    for log in recent_logs:
        activity.append({
            'id': log.id,
            'action': log.action,
            'user': log.user.username if log.user else 'System',
            'resource_type': log.resource_type,
            'timestamp': log.timestamp.isoformat(),
            'ip_address': log.ip_address
        })
    
    return jsonify({
        'success': True,
        'activity': activity
    })

@admin_bp.route('/api/health-check')
@admin_required
def api_health_check():
    """System health check API"""
    analytics = AdminAnalytics()
    health = analytics.get_system_health()
    
    return jsonify({
        'success': True,
        'health': health,
        'timestamp': datetime.now().isoformat()
    })

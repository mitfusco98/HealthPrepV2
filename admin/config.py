"""
Admin configuration and management interface.
Handles admin dashboard routes, user management, and system configuration.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
from models import User, PHIFilterConfig, ChecklistSettings, ScreeningType
from admin.logs import log_manager
from admin.analytics import analytics
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter
from presets.loader import PresetLoader
from app import db

logger = logging.getLogger(__name__)

# Create admin blueprint
admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('ui.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system metrics"""
    try:
        # Get system analytics
        roi_metrics = analytics.get_system_roi_metrics(days=30)
        
        # Get recent admin activity
        log_stats = log_manager.get_log_statistics(days=7)
        
        # Get OCR monitoring data
        ocr_monitor = OCRMonitor()
        ocr_stats = ocr_monitor.get_processing_statistics(days=7)
        
        # Get system health indicators
        total_users = User.query.count()
        active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
        
        dashboard_data = {
            'roi_metrics': roi_metrics,
            'log_statistics': log_stats,
            'ocr_statistics': ocr_stats,
            'system_health': {
                'total_users': total_users,
                'active_screening_types': active_screening_types,
                'system_status': 'Operational'
            }
        }
        
        # Log dashboard access
        log_manager.log_activity(
            action='admin_dashboard_viewed',
            details='Admin dashboard accessed',
            user_id=current_user.id
        )
        
        return render_template('admin/dashboard.html', data=dashboard_data)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('admin/dashboard.html', data={})

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin logs view with filtering"""
    try:
        # Get filter parameters
        filters = {
            'user_id': request.args.get('user_id'),
            'action': request.args.get('action'),
            'date_from': request.args.get('date_from'),
            'date_to': request.args.get('date_to'),
            'search': request.args.get('search')
        }
        
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Get logs
        log_data = log_manager.get_logs(filters=filters, page=page, per_page=per_page)
        
        # Get users for filter dropdown
        users = User.query.order_by(User.username).all()
        
        # Get common actions for filter dropdown
        common_actions = [
            'user_login', 'user_logout', 'screening_type_created',
            'screening_type_updated', 'screening_type_deleted',
            'phi_config_changed', 'preset_import', 'ocr_processing'
        ]
        
        return render_template('admin/logs.html',
                             log_data=log_data,
                             users=users,
                             common_actions=common_actions,
                             current_filters=filters)
        
    except Exception as e:
        logger.error(f"Error loading admin logs: {str(e)}")
        flash('Error loading logs', 'error')
        return render_template('admin/logs.html',
                             log_data={'logs': [], 'total': 0},
                             users=[],
                             common_actions=[],
                             current_filters={})

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export admin logs"""
    try:
        # Get same filters as logs view
        filters = {
            'user_id': request.args.get('user_id'),
            'action': request.args.get('action'),
            'date_from': request.args.get('date_from'),
            'date_to': request.args.get('date_to'),
            'search': request.args.get('search')
        }
        filters = {k: v for k, v in filters.items() if v}
        
        format_type = request.args.get('format', 'json')
        
        # Export logs
        export_result = log_manager.export_logs(filters=filters, format=format_type)
        
        if export_result['success']:
            # Log the export activity
            log_manager.log_activity(
                action='logs_exported',
                details=f"Exported {export_result.get('record_count', 0)} logs in {format_type} format",
                user_id=current_user.id
            )
            
            if format_type == 'json':
                return jsonify(export_result['data'])
            else:  # CSV
                from flask import Response
                return Response(
                    export_result['data'],
                    mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=admin_logs_{datetime.now().strftime("%Y%m%d")}.csv'}
                )
        else:
            flash(f"Export failed: {export_result.get('error', 'Unknown error')}", 'error')
            return redirect(url_for('admin.logs'))
            
    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        flash('Error exporting logs', 'error')
        return redirect(url_for('admin.logs'))

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR monitoring dashboard"""
    try:
        ocr_monitor = OCRMonitor()
        
        # Get OCR statistics
        ocr_stats = ocr_monitor.get_processing_statistics(days=30)
        
        # Get low confidence documents
        low_confidence_docs = ocr_monitor.get_low_confidence_documents(threshold=60, limit=20)
        
        # Get processing queue status
        queue_status = ocr_monitor.get_processing_queue_status()
        
        # Get confidence trend
        confidence_trend = ocr_monitor.get_confidence_trend(days=30)
        
        ocr_data = {
            'statistics': ocr_stats,
            'low_confidence_documents': low_confidence_docs,
            'queue_status': queue_status,
            'confidence_trend': confidence_trend
        }
        
        return render_template('admin/ocr_dashboard.html', data=ocr_data)
        
    except Exception as e:
        logger.error(f"Error loading OCR dashboard: {str(e)}")
        flash('Error loading OCR dashboard', 'error')
        return render_template('admin/ocr_dashboard.html', data={})

@admin_bp.route('/phi', methods=['GET', 'POST'])
@login_required
@admin_required
def phi_settings():
    """PHI filtering configuration"""
    try:
        phi_filter = PHIFilter()
        
        if request.method == 'POST':
            # Update PHI filter configuration
            config = PHIFilterConfig.query.first()
            if not config:
                config = PHIFilterConfig()
                db.session.add(config)
            
            # Update configuration based on form data
            config.filter_enabled = request.form.get('filter_enabled') == 'true'
            config.filter_ssn = request.form.get('filter_ssn') == 'true'
            config.filter_phone = request.form.get('filter_phone') == 'true'
            config.filter_mrn = request.form.get('filter_mrn') == 'true'
            config.filter_insurance = request.form.get('filter_insurance') == 'true'
            config.filter_addresses = request.form.get('filter_addresses') == 'true'
            config.filter_names = request.form.get('filter_names') == 'true'
            config.filter_dates = request.form.get('filter_dates') == 'true'
            config.updated_by = current_user.id
            config.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log the configuration change
            log_manager.log_activity(
                action='phi_config_changed',
                details=f"PHI filter configuration updated. Enabled: {config.filter_enabled}",
                user_id=current_user.id
            )
            
            flash('PHI filter configuration updated successfully', 'success')
            return redirect(url_for('admin.phi_settings'))
        
        # GET request - show current configuration
        config = PHIFilterConfig.query.first()
        if not config:
            config = PHIFilterConfig(filter_enabled=True)
        
        # Get PHI statistics
        phi_stats = phi_filter.get_phi_statistics(days=30)
        
        # Test data for demonstration
        test_text = "Patient John Smith (SSN: 123-45-6789) was seen on 01/15/2024. Contact: (555) 123-4567. Glucose: 120 mg/dL, Blood pressure: 130/80 mmHg."
        test_result = phi_filter.test_phi_filter(test_text)
        
        return render_template('admin/phi_settings.html',
                             config=config,
                             phi_stats=phi_stats,
                             test_result=test_result)
        
    except Exception as e:
        logger.error(f"Error in PHI settings: {str(e)}")
        flash('Error loading PHI settings', 'error')
        return render_template('admin/phi_settings.html',
                             config=None,
                             phi_stats={},
                             test_result={})

@admin_bp.route('/users')
@login_required
@admin_required
def user_management():
    """User management interface"""
    try:
        users = User.query.order_by(User.username).all()
        
        return render_template('admin/users.html', users=users)
        
    except Exception as e:
        logger.error(f"Error loading user management: {str(e)}")
        flash('Error loading users', 'error')
        return render_template('admin/users.html', users=[])

@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create new user"""
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('admin.user_management'))
        
        # Check for existing user
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('admin.user_management'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('admin.user_management'))
        
        # Create user
        user = User(
            username=username,
            email=email,
            role=role,
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Log user creation
        log_manager.log_activity(
            action='user_created',
            details=f"User {username} created with role {role}",
            user_id=current_user.id
        )
        
        flash(f'User {username} created successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        db.session.rollback()
        flash('Error creating user', 'error')
    
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/presets')
@login_required
@admin_required
def preset_management():
    """Screening preset management"""
    try:
        preset_loader = PresetLoader()
        
        # Get available presets
        available_presets = preset_loader.get_available_presets()
        
        return render_template('admin/presets.html', presets=available_presets)
        
    except Exception as e:
        logger.error(f"Error loading preset management: {str(e)}")
        flash('Error loading presets', 'error')
        return render_template('admin/presets.html', presets=[])

@admin_bp.route('/presets/import', methods=['POST'])
@login_required
@admin_required
def import_preset():
    """Import screening preset"""
    try:
        filename = request.form.get('filename')
        overwrite = request.form.get('overwrite') == 'true'
        
        if not filename:
            flash('Please select a preset to import', 'error')
            return redirect(url_for('admin.preset_management'))
        
        preset_loader = PresetLoader()
        result = preset_loader.import_preset(
            filename=filename,
            user_id=current_user.id,
            overwrite_existing=overwrite
        )
        
        if result['success']:
            flash(f"Preset imported successfully. "
                  f"Imported: {result['imported_count']}, "
                  f"Updated: {result['updated_count']}, "
                  f"Skipped: {result['skipped_count']}", 'success')
        else:
            flash(f"Preset import failed: {result.get('error', 'Unknown error')}", 'error')
        
    except Exception as e:
        logger.error(f"Error importing preset: {str(e)}")
        flash('Error importing preset', 'error')
    
    return redirect(url_for('admin.preset_management'))

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics_dashboard():
    """Analytics and ROI dashboard"""
    try:
        # Get comprehensive analytics
        roi_metrics = analytics.get_system_roi_metrics(days=30)
        screening_performance = analytics.get_screening_performance_analytics(days=30)
        monthly_trends = analytics.get_monthly_trends(months=12)
        
        analytics_data = {
            'roi_metrics': roi_metrics,
            'screening_performance': screening_performance,
            'monthly_trends': monthly_trends
        }
        
        return render_template('admin/analytics.html', data=analytics_data)
        
    except Exception as e:
        logger.error(f"Error loading analytics dashboard: {str(e)}")
        flash('Error loading analytics', 'error')
        return render_template('admin/analytics.html', data={})

# API endpoints for admin functionality
@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        stats = analytics.get_system_roi_metrics(days=7)
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"Error getting API stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/logs/cleanup', methods=['POST'])
@login_required
@admin_required
def api_cleanup_logs():
    """API endpoint to cleanup old logs"""
    try:
        result = log_manager.cleanup_old_logs()
        
        if result['success']:
            log_manager.log_activity(
                action='logs_cleanup',
                details=f"Cleaned up {result['deleted_count']} old log entries",
                user_id=current_user.id
            )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error cleaning up logs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.errorhandler(403)
def admin_forbidden(e):
    """Handle 403 errors in admin section"""
    return render_template('error/403.html'), 403

@admin_bp.errorhandler(404)
def admin_not_found(e):
    """Handle 404 errors in admin section"""
    return render_template('error/404.html'), 404

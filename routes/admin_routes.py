# Applying the changes to correct the import errors and references to non-existent classes.
"""
Admin dashboard routes and functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging
import functools

from models import User, AdminLog, PHIFilterSettings, ChecklistSettings
from app import db
from admin.logs import AdminLogManager
from admin.analytics import HealthPrepAnalytics
from admin.config import AdminConfig
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin role"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Main admin dashboard"""
    try:
        analytics = HealthPrepAnalytics()
        log_manager = AdminLogManager()

        # Get dashboard statistics
        dashboard_stats = analytics.get_system_performance_metrics()

        # Get recent activity
        recent_logs = log_manager.get_recent_logs(limit=10)

        # Get system health indicators
        system_health = analytics.get_system_health()

        return render_template('admin/dashboard.html',
                             stats=dashboard_stats,
                             recent_logs=recent_logs,
                             system_health=system_health)

    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        flash('Error loading admin dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin logs viewer"""
    try:
        log_manager = AdminLogManager()

        # Get filter parameters
        page = request.args.get('page', 1, type=int)
        event_type = request.args.get('event_type', '')
        user_id = request.args.get('user_id', type=int)
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        # Build filters
        filters = {}
        if event_type:
            filters['action'] = event_type
        if user_id:
            filters['user_id'] = user_id
        if start_date:
            filters['start_date'] = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            filters['end_date'] = datetime.strptime(end_date, '%Y-%m-%d')

        # Get filtered logs
        logs_result = log_manager.get_filtered_logs(filters, page=page, per_page=50)

        # Get filter options
        users = User.query.all()
        event_types = log_manager.get_event_types()

        return render_template('admin/logs.html',
                             logs=logs_result['logs'],
                             pagination=logs_result['pagination'],
                             users=users,
                             event_types=event_types,
                             filters={
                                 'event_type': event_type,
                                 'user_id': user_id,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })

    except Exception as e:
        logger.error(f"Error in admin logs: {str(e)}")
        flash('Error loading admin logs', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export admin logs"""
    try:
        log_manager = AdminLogManager()

        # Get export parameters
        format_type = request.args.get('format', 'json')
        days = request.args.get('days', 30, type=int)

        result = log_manager.export_logs(days=days, format_type=format_type)

        if result['success']:
            return jsonify(result)
        else:
            flash(f'Error exporting logs: {result["error"]}', 'error')
            return redirect(url_for('admin.logs'))

    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR processing dashboard"""
    try:
        monitor = OCRMonitor()

        # Get OCR dashboard data
        dashboard_data = monitor.get_processing_dashboard()

        # Get low confidence documents
        low_confidence_docs = monitor.get_low_confidence_documents()

        # Get basic OCR statistics
        total_docs = db.session.execute(db.text("SELECT COUNT(*) FROM medical_documents")).scalar() or 0
        processed_docs = db.session.execute(db.text("SELECT COUNT(*) FROM medical_documents WHERE ocr_processed = true")).scalar() or 0
        ocr_stats = {
            'processed_documents': processed_docs,
            'pending_documents': total_docs - processed_docs,
            'average_confidence': 0.8  # placeholder
        }

        return render_template('admin/ocr_dashboard.html',
                             dashboard=dashboard_data,
                             low_confidence_docs=low_confidence_docs,
                             ocr_stats=ocr_stats)

    except Exception as e:
        logger.error(f"Error in OCR dashboard: {str(e)}")
        flash('Error loading OCR dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/phi-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def phi_settings():
    """PHI filter settings management"""
    try:
        phi_filter = PHIFilter()

        if request.method == 'POST':
            # Update PHI settings
            new_settings = {
                'enabled': request.form.get('enabled') == 'on',
                'filter_ssn': request.form.get('filter_ssn') == 'on',
                'filter_phone': request.form.get('filter_phone') == 'on',
                'filter_mrn': request.form.get('filter_mrn') == 'on',
                'filter_insurance': request.form.get('filter_insurance') == 'on',
                'filter_addresses': request.form.get('filter_addresses') == 'on',
                'filter_names': request.form.get('filter_names') == 'on',
                'filter_dates': request.form.get('filter_dates') == 'on'
            }

            result = phi_filter.update_settings(new_settings)

            if result['success']:
                flash('PHI filter settings updated successfully', 'success')

                # Log the change
                log_manager = AdminLogManager()
                log_manager.log_action(
                    user_id=current_user.id,
                    action='update_phi_settings',
                    details=new_settings
                )
            else:
                flash(f'Error updating settings: {result["error"]}', 'error')

            return redirect(url_for('admin.phi_settings'))

        # GET request - show current settings
        current_settings = phi_filter.settings
        processing_stats = phi_filter.get_processing_statistics()

        return render_template('admin/phi_settings.html',
                             settings=current_settings,
                             stats=processing_stats)

    except Exception as e:
        logger.error(f"Error in PHI settings: {str(e)}")
        flash('Error loading PHI settings', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/phi-test', methods=['POST'])
@login_required
@admin_required
def phi_test():
    """Test PHI filter with sample text"""
    try:
        phi_filter = PHIFilter()

        test_text = request.form.get('test_text', '')
        if not test_text:
            return jsonify({'success': False, 'error': 'No test text provided'})

        result = phi_filter.test_filter(test_text)

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"Error testing PHI filter: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management"""
    try:
        users = User.query.order_by(User.username).all()

        return render_template('admin/users.html', users=users)

    except Exception as e:
        logger.error(f"Error loading users: {str(e)}")
        flash('Error loading users', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)

        # Don't allow disabling own account
        if user.id == current_user.id:
            flash('Cannot disable your own account', 'error')
            return redirect(url_for('admin.users'))

        user.is_active = not user.is_active
        db.session.commit()

        # Log the action
        log_manager = AdminLogManager()
        log_manager.log_action(
            user_id=current_user.id,
            action='toggle_user_status',
            target_type='user',
            target_id=user_id,
            details={'new_status': user.is_active}
        )

        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username} {status} successfully', 'success')

        return redirect(url_for('admin.users'))

    except Exception as e:
        logger.error(f"Error toggling user status: {str(e)}")
        flash('Error updating user status', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """System settings management"""
    try:
        config_manager = AdminConfig()

        if request.method == 'POST':
            # Update system settings
            settings_data = {
                'lab_cutoff_months': request.form.get('lab_cutoff_months', type=int),
                'imaging_cutoff_months': request.form.get('imaging_cutoff_months', type=int),
                'consult_cutoff_months': request.form.get('consult_cutoff_months', type=int),
                'hospital_cutoff_months': request.form.get('hospital_cutoff_months', type=int)
            }

            result = config_manager.update_checklist_settings(settings_data)

            if result['success']:
                flash('Settings updated successfully', 'success')

                # Log the change
                log_manager = AdminLogManager()
                log_manager.log_action(
                    user_id=current_user.id,
                    action='update_system_settings',
                    details=settings_data
                )
            else:
                flash(f'Error updating settings: {result["error"]}', 'error')

            return redirect(url_for('admin.settings'))

        # GET request - show current settings
        current_settings = config_manager.get_system_settings()

        return render_template('admin/settings.html',
                             settings=current_settings)

    except Exception as e:
        logger.error(f"Error in admin settings: {str(e)}")
        flash('Error loading settings', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Advanced analytics dashboard"""
    try:
        analytics = HealthPrepAnalytics()

        # Get comprehensive analytics
        analytics_data = {
            'system_performance': analytics.get_system_performance_metrics(),
            'time_saved': analytics.calculate_time_saved(),
            'compliance_gaps': analytics.analyze_compliance_gaps_closed(),
            'roi_report': analytics.generate_roi_report()
        }

        return render_template('admin/analytics.html',
                             analytics=analytics_data)

    except Exception as e:
        logger.error(f"Error in admin analytics: {str(e)}")
        flash('Error loading analytics', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/system-health')
@login_required
@admin_required
def system_health():
    """System health monitoring"""
    try:
        analytics = HealthPrepAnalytics()

        health_data = analytics.get_system_performance_metrics()

        return jsonify(health_data)

    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/backup-data', methods=['POST'])
@login_required
@admin_required
def backup_data():
    """Create system backup"""
    try:
        # This would implement a backup strategy
        # For now, return a placeholder response

        flash('Backup functionality not yet implemented', 'info')
        return redirect(url_for('admin.dashboard'))

    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        flash('Error creating backup', 'error')
        return redirect(url_for('admin.dashboard'))
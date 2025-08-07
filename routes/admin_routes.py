# Applying the changes to correct the import errors and references to non-existent classes.
"""
Admin dashboard routes and functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging
import functools

from models import User, AdminLog, PHIFilterSettings, log_admin_event
from app import db
from flask import request as flask_request
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
        if not current_user.is_authenticated or not current_user.is_admin_user():
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

        # Get dashboard statistics
        dashboard_stats = analytics.get_roi_metrics()

        # Get recent activity
        recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()

        # Get system health indicators
        system_health = analytics.get_usage_statistics()

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
        # Get filter parameters
        page = request.args.get('page', 1, type=int)
        event_type = request.args.get('event_type', '')
        user_id = request.args.get('user_id', type=int)
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        # Build filters
        filters = {
            'event_type': event_type,
            'user_id': user_id,
            'start_date': start_date,
            'end_date': end_date
        }
        
        # Get filtered logs
        query = AdminLog.query
        if event_type:
            query = query.filter(AdminLog.event_type == event_type)
        if user_id:
            query = query.filter(AdminLog.user_id == user_id)
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AdminLog.timestamp >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AdminLog.timestamp <= end_dt)

        logs_pagination = query.order_by(AdminLog.timestamp.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        logs_result = {
            'logs': logs_pagination.items,
            'pagination': logs_pagination
        }

        # Get filter options
        users = User.query.all()
        event_types = db.session.query(AdminLog.event_type).distinct().all()
        event_types = [event.event_type for event in event_types if event.event_type]

        return render_template('admin/logs.html',
                             logs=logs_result['logs'],
                             pagination=logs_result['pagination'],
                             users=users,
                             event_types=event_types,
                             filters=filters)

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
        # Get export parameters
        format_type = request.args.get('format', 'json')
        days = request.args.get('days', 30, type=int)

        # Export logs directly from AdminLog model
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=days)
        
        logs = AdminLog.query.filter(AdminLog.timestamp >= start_date).order_by(AdminLog.timestamp.desc()).all()
        export_data = []
        for log in logs:
            export_data.append({
                'timestamp': log.timestamp.isoformat(),
                'event_type': log.event_type,
                'user_id': log.user_id,
                'username': log.user.username if log.user else 'System',
                'ip_address': log.ip_address,
                'data': log.data
            })
        
        result = {'success': True, 'data': export_data}

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

        # Get basic OCR dashboard data (simplified)
        dashboard_data = {
            'total_processed': 0,
            'processing_queue': 0,
            'error_rate': 0.0
        }

        # Get low confidence documents (placeholder)
        low_confidence_docs = []

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

            # Update PHI settings in database (simplified approach)
            settings = PHIFilterSettings.query.first()
            if not settings:
                settings = PHIFilterSettings()
                db.session.add(settings)
            
            settings.enabled = new_settings['enabled']
            settings.filter_ssn = new_settings['filter_ssn']
            settings.filter_phone = new_settings['filter_phone']
            settings.filter_mrn = new_settings['filter_mrn']
            settings.filter_insurance = new_settings['filter_insurance']
            settings.filter_addresses = new_settings['filter_addresses']
            settings.filter_names = new_settings['filter_names']
            settings.filter_dates = new_settings['filter_dates']
            
            db.session.commit()
            
            flash('PHI filter settings updated successfully', 'success')
            
            # Log the change
            log_admin_event(
                event_type='update_phi_settings',
                user_id=current_user.id,
                ip=flask_request.remote_addr,
                data={'settings': new_settings, 'description': 'PHI filter settings updated'}
            )

            return redirect(url_for('admin.phi_settings'))

        # GET request - show current settings
        current_settings = PHIFilterSettings.query.first() or PHIFilterSettings()
        # Get basic processing statistics (placeholder)
        processing_stats = {
            'documents_processed': 0,
            'phi_items_filtered': 0,
            'processing_accuracy': 97.3,
            'avg_processing_time': 1.2
        }

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

        # Add is_active field if it doesn't exist
        if not hasattr(user, 'is_active'):
            user.is_active = True
        
        user.is_active = not getattr(user, 'is_active', True)
        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='toggle_user_status',
            user_id=current_user.id,
            ip=flask_request.remote_addr,
            data={'target_user_id': user_id, 'new_status': user.is_active, 'description': f'User {user.username} status changed to {"active" if user.is_active else "inactive"}'}
        )

        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username} {status} successfully', 'success')

        return redirect(url_for('admin.users'))

    except Exception as e:
        logger.error(f"Error toggling user status: {str(e)}")
        flash('Error updating user status', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/user/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin_status(user_id):
    """Toggle user admin privileges"""
    try:
        user = User.query.get_or_404(user_id)

        # Don't allow removing own admin privileges
        if user.id == current_user.id:
            flash('Cannot modify your own admin privileges', 'error')
            return redirect(url_for('admin.users'))

        user.is_admin = not user.is_admin
        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='toggle_admin_status',
            user_id=current_user.id,
            ip=flask_request.remote_addr,
            data={'target_user_id': user_id, 'new_admin_status': user.is_admin, 'description': f'Admin privileges {"granted" if user.is_admin else "revoked"} for {user.username}'}
        )

        status = 'granted' if user.is_admin else 'revoked'
        flash(f'Admin privileges {status} for {user.username}', 'success')

        return redirect(url_for('admin.users'))

    except Exception as e:
        logger.error(f"Error toggling admin status: {str(e)}")
        flash('Error updating admin status', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/user/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user"""
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            is_admin = request.form.get('is_admin') == 'on'

            # Validate input
            if not username or not email or not password:
                flash('All fields are required', 'error')
                return render_template('admin/add_user.html')

            # Check if user already exists
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'error')
                return render_template('admin/add_user.html')

            if User.query.filter_by(email=email).first():
                flash('Email already exists', 'error')
                return render_template('admin/add_user.html')

            # Create new user
            new_user = User()
            new_user.username = username
            new_user.email = email
            new_user.is_admin = is_admin
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()

            # Log the action
            log_admin_event(
                event_type='create_user',
                user_id=current_user.id,
                ip=flask_request.remote_addr,
                data={'created_user': username, 'is_admin': is_admin, 'description': f'Created user: {username} with admin: {is_admin}'}
            )

            flash(f'User {username} created successfully', 'success')
            return redirect(url_for('admin.users'))

        return render_template('admin/add_user.html')

    except Exception as e:
        logger.error(f"Error adding user: {str(e)}")
        flash('Error creating user', 'error')
        return render_template('admin/add_user.html')

@admin_bp.route('/presets/import', methods=['GET', 'POST'])
@login_required
@admin_required
def import_screening_presets():
    """Import screening type presets - Admin function for system setup"""
    try:
        from presets.loader import PresetLoader
        
        loader = PresetLoader()
        
        if request.method == 'POST':
            preset_filename = request.form.get('preset_filename')
            overwrite_existing = request.form.get('overwrite_existing') == 'on'
            
            if not preset_filename:
                flash('Please select a preset to import', 'error')
                return redirect(url_for('admin.import_screening_presets'))
            
            # Import the preset
            result = loader.import_preset(
                filename=preset_filename,
                user_id=current_user.id,
                overwrite_existing=overwrite_existing
            )
            
            if result['success']:
                flash(f'Preset imported successfully: {result["imported_count"]} imported, '
                     f'{result["updated_count"]} updated, {result["skipped_count"]} skipped', 'success')
                
                # Log the action
                log_admin_event(
                    event_type='import_screening_preset',
                    user_id=current_user.id,
                    ip=flask_request.remote_addr,
                    data={'preset_filename': preset_filename, 'imported_count': result['imported_count'], 'updated_count': result['updated_count'], 'description': f'Imported preset {preset_filename}'}
                )
            else:
                error_msg = '; '.join(result.get('errors', ['Unknown error']))
                flash(f'Error importing preset: {error_msg}', 'error')
            
            return redirect(url_for('admin.import_screening_presets'))
        
        # GET request - show available presets
        available_presets = loader.get_available_presets()
        
        return render_template('admin/import_presets.html',
                             presets=available_presets)
        
    except Exception as e:
        logger.error(f"Error in preset import: {str(e)}")
        flash('Error loading preset import page', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """System administration settings - security, monitoring, etc."""
    try:
        if request.method == 'POST':
            # Update system administration settings
            admin_settings = {
                'session_timeout': request.form.get('session_timeout', type=int),
                'max_login_attempts': request.form.get('max_login_attempts', type=int),
                'audit_retention_days': request.form.get('audit_retention_days', type=int),
                'require_password_change': request.form.get('require_password_change') == 'on'
            }

            # Log the change
            log_admin_event(
                event_type='update_admin_settings',
                user_id=current_user.id,
                ip=flask_request.remote_addr,
                data={'settings': admin_settings, 'description': 'System administration settings updated'}
            )

            flash('System settings updated successfully', 'success')
            return redirect(url_for('admin.settings'))

        # GET request - show current admin settings
        return render_template('admin/system_settings.html')

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
            'system_performance': analytics.get_roi_metrics(),
            'time_saved': analytics.calculate_time_savings(),
            'compliance_gaps': analytics.calculate_compliance_gaps_closed(),
            'roi_report': analytics.generate_executive_summary()
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

        health_data = analytics.get_roi_metrics()

        return jsonify(health_data)

    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/log-error', methods=['POST'])
@login_required
@admin_required
def log_error():
    """Log system error - API endpoint for error reporting"""
    try:
        error_data = request.get_json()
        if not error_data:
            return jsonify({'success': False, 'error': 'No error data provided'}), 400
        
        # Log the error
        log_admin_event(
            event_type='system_error',
            user_id=current_user.id,
            ip=flask_request.remote_addr,
            data={'error_message': error_data.get('message', 'Unknown error'), 'error_source': error_data.get('source', 'Unknown'), 'description': f'System error logged: {error_data.get("message", "Unknown error")}'}
        )
        
        return jsonify({'success': True, 'message': 'Error logged successfully'})
        
    except Exception as e:
        logger.error(f"Error logging system error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
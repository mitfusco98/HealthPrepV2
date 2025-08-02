"""
Administrative routes for system management, monitoring, and configuration.
Handles admin dashboard, user management, OCR monitoring, and system settings.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import logging
from datetime import datetime, timedelta

from models import User, AdminLog, MedicalDocument, Patient, ScreeningType, PHIFilterSettings, db
from admin.logs import AdminLogger
from admin.analytics import SystemAnalytics
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)
admin_logger = AdminLogger()

def admin_required(f):
    """Decorator to require admin privileges."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Administrator privileges required.', 'error')
            return redirect(url_for('screening.screening_list'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Main administrative dashboard."""
    try:
        analytics = SystemAnalytics()
        ocr_monitor = OCRMonitor()
        
        # Get system statistics
        system_stats = analytics.get_system_overview()
        recent_activity = admin_logger.get_recent_activity(limit=10)
        ocr_stats = ocr_monitor.get_processing_statistics(days=7)
        
        # Get user activity summary
        user_stats = analytics.get_user_activity_summary()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_admin_dashboard',
            details='Accessed admin dashboard',
            ip_address=request.remote_addr
        )
        
        return render_template('admin/dashboard.html',
                             system_stats=system_stats,
                             recent_activity=recent_activity,
                             ocr_stats=ocr_stats,
                             user_stats=user_stats)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        flash('Error loading dashboard data', 'error')
        return render_template('admin/dashboard.html',
                             system_stats={},
                             recent_activity=[],
                             ocr_stats={},
                             user_stats={})

@admin_bp.route('/users')
@login_required
@admin_required
def user_management():
    """User management interface."""
    try:
        users = User.query.order_by(User.username).all()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_user_management',
            details='Accessed user management',
            ip_address=request.remote_addr
        )
        
        return render_template('admin/user_management.html', users=users)
        
    except Exception as e:
        logger.error(f"Error loading user management: {e}")
        flash('Error loading user data', 'error')
        return render_template('admin/user_management.html', users=[])

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add a new user."""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            is_admin = request.form.get('is_admin') == 'on'
            
            # Validate required fields
            if not all([username, email, password]):
                flash('All fields are required', 'error')
                return render_template('admin/add_user.html')
            
            # Check for existing user
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                flash('Username or email already exists', 'error')
                return render_template('admin/add_user.html')
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                is_admin=is_admin
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            admin_logger.log_action(
                user_id=current_user.id,
                action='add_user',
                details=f'Created user: {username} (admin: {is_admin})',
                ip_address=request.remote_addr
            )
            
            flash(f'User "{username}" created successfully', 'success')
            return redirect(url_for('admin.user_management'))
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            db.session.rollback()
            flash('Error creating user', 'error')
    
    return render_template('admin/add_user.html')

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit an existing user."""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.is_admin = request.form.get('is_admin') == 'on'
            
            # Update password if provided
            new_password = request.form.get('password')
            if new_password:
                user.set_password(new_password)
            
            db.session.commit()
            
            admin_logger.log_action(
                user_id=current_user.id,
                action='edit_user',
                details=f'Updated user: {user.username}',
                ip_address=request.remote_addr
            )
            
            flash(f'User "{user.username}" updated successfully', 'success')
            return redirect(url_for('admin.user_management'))
            
        except Exception as e:
            logger.error(f"Error editing user: {e}")
            db.session.rollback()
            flash('Error updating user', 'error')
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user."""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting self
        if user.id == current_user.id:
            flash('Cannot delete your own account', 'error')
            return redirect(url_for('admin.user_management'))
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='delete_user',
            details=f'Deleted user: {username}',
            ip_address=request.remote_addr
        )
        
        flash(f'User "{username}" deleted successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        db.session.rollback()
        flash('Error deleting user', 'error')
    
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR processing monitoring dashboard."""
    try:
        ocr_monitor = OCRMonitor()
        
        # Get OCR statistics and monitoring data
        processing_stats = ocr_monitor.get_processing_statistics(days=30)
        low_confidence_docs = ocr_monitor.get_low_confidence_documents(limit=20)
        pending_queue = ocr_monitor.get_pending_processing_queue()
        performance_metrics = ocr_monitor.get_processing_performance()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_ocr_dashboard',
            details='Accessed OCR monitoring dashboard',
            ip_address=request.remote_addr
        )
        
        return render_template('admin/ocr_dashboard.html',
                             processing_stats=processing_stats,
                             low_confidence_docs=low_confidence_docs,
                             pending_queue=pending_queue,
                             performance_metrics=performance_metrics)
        
    except Exception as e:
        logger.error(f"Error loading OCR dashboard: {e}")
        flash('Error loading OCR monitoring data', 'error')
        return render_template('admin/ocr_dashboard.html',
                             processing_stats={},
                             low_confidence_docs=[],
                             pending_queue={},
                             performance_metrics={})

@admin_bp.route('/phi')
@login_required
@admin_required
def phi_settings():
    """PHI filtering settings management."""
    try:
        phi_filter = PHIFilter()
        
        # Get current PHI filter settings
        settings = PHIFilterSettings.query.first()
        if not settings:
            settings = PHIFilterSettings()
            db.session.add(settings)
            db.session.commit()
        
        # Get filter configuration information
        filter_config = phi_filter.get_filter_settings()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_phi_settings',
            details='Accessed PHI filter settings',
            ip_address=request.remote_addr
        )
        
        return render_template('admin/phi_settings.html',
                             settings=settings,
                             filter_config=filter_config)
        
    except Exception as e:
        logger.error(f"Error loading PHI settings: {e}")
        flash('Error loading PHI filter settings', 'error')
        return render_template('admin/phi_settings.html',
                             settings=None,
                             filter_config={})

@admin_bp.route('/phi/update', methods=['POST'])
@login_required
@admin_required
def update_phi_settings():
    """Update PHI filtering settings."""
    try:
        settings = PHIFilterSettings.query.first()
        if not settings:
            settings = PHIFilterSettings()
            db.session.add(settings)
        
        # Update PHI filter settings
        settings.enabled = request.form.get('enabled') == 'on'
        settings.filter_ssn = request.form.get('filter_ssn') == 'on'
        settings.filter_phone = request.form.get('filter_phone') == 'on'
        settings.filter_mrn = request.form.get('filter_mrn') == 'on'
        settings.filter_insurance = request.form.get('filter_insurance') == 'on'
        settings.filter_addresses = request.form.get('filter_addresses') == 'on'
        settings.filter_names = request.form.get('filter_names') == 'on'
        settings.filter_dates = request.form.get('filter_dates') == 'on'
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='update_phi_settings',
            details='Updated PHI filter settings',
            ip_address=request.remote_addr
        )
        
        flash('PHI filter settings updated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error updating PHI settings: {e}")
        db.session.rollback()
        flash('Error updating PHI filter settings', 'error')
    
    return redirect(url_for('admin.phi_settings'))

@admin_bp.route('/phi/test', methods=['POST'])
@login_required
@admin_required
def test_phi_filter():
    """Test PHI filter with sample text."""
    try:
        test_text = request.form.get('test_text', '')
        
        if not test_text:
            return jsonify({'success': False, 'error': 'No test text provided'})
        
        phi_filter = PHIFilter()
        
        # Get current settings
        settings = PHIFilterSettings.query.first()
        filter_settings = {
            'filter_ssn': settings.filter_ssn if settings else True,
            'filter_phone': settings.filter_phone if settings else True,
            'filter_mrn': settings.filter_mrn if settings else True,
            'filter_insurance': settings.filter_insurance if settings else True,
            'filter_addresses': settings.filter_addresses if settings else True,
            'filter_names': settings.filter_names if settings else False,
            'filter_dates': settings.filter_dates if settings else True,
            'filter_emails': True
        }
        
        # Test the filter
        result = phi_filter.filter_text(test_text, filter_settings)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='test_phi_filter',
            details='Tested PHI filter functionality',
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing PHI filter: {e}")
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/logs')
@login_required
@admin_required
def view_logs():
    """View system logs with filtering."""
    try:
        # Get filter parameters
        event_type = request.args.get('event_type')
        user_id = request.args.get('user_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Build query
        query = AdminLog.query
        
        if event_type:
            query = query.filter(AdminLog.action.contains(event_type))
        
        if user_id:
            query = query.filter(AdminLog.user_id == user_id)
        
        if date_from:
            try:
                from dateutil import parser as date_parser
                date_from_obj = date_parser.parse(date_from)
                query = query.filter(AdminLog.timestamp >= date_from_obj)
            except:
                pass
        
        if date_to:
            try:
                from dateutil import parser as date_parser
                date_to_obj = date_parser.parse(date_to)
                query = query.filter(AdminLog.timestamp <= date_to_obj)
            except:
                pass
        
        # Order by most recent first
        query = query.order_by(AdminLog.timestamp.desc())
        
        # Paginate results
        logs = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Get users for filter dropdown
        users = User.query.order_by(User.username).all()
        
        # Get log statistics
        log_stats = admin_logger.get_log_statistics()
        
        return render_template('admin/logs.html',
                             logs=logs,
                             users=users,
                             log_stats=log_stats,
                             filters={
                                 'event_type': event_type,
                                 'user_id': user_id,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
        
    except Exception as e:
        logger.error(f"Error loading admin logs: {e}")
        flash('Error loading system logs', 'error')
        return render_template('admin/logs.html',
                             logs=None,
                             users=[],
                             log_stats={},
                             filters={})

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export system logs to JSON."""
    try:
        # Get filter parameters (same as view_logs)
        event_type = request.args.get('event_type')
        user_id = request.args.get('user_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        result = admin_logger.export_logs(
            event_type=event_type,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to
        )
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='export_logs',
            details=f'Exported {result.get("log_count", 0)} log entries',
            ip_address=request.remote_addr
        )
        
        if result['success']:
            from flask import Response
            import json
            
            response = Response(
                json.dumps(result['logs'], indent=2, default=str),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename=admin_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
            )
            return response
        else:
            flash(f'Error exporting logs: {result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('admin.view_logs'))
        
    except Exception as e:
        logger.error(f"Error exporting logs: {e}")
        flash('Error exporting logs', 'error')
        return redirect(url_for('admin.view_logs'))

@admin_bp.route('/system/cleanup', methods=['POST'])
@login_required
@admin_required
def system_cleanup():
    """Perform system cleanup operations."""
    try:
        cleanup_type = request.form.get('cleanup_type')
        
        if cleanup_type == 'old_logs':
            # Clean up logs older than specified days
            days = request.form.get('days', 90, type=int)
            result = admin_logger.cleanup_old_logs(days)
            
            if result['success']:
                flash(f'Cleaned up {result["deleted_count"]} old log entries', 'success')
            else:
                flash(f'Error cleaning logs: {result.get("error")}', 'error')
        
        elif cleanup_type == 'orphaned_documents':
            # Clean up orphaned document records
            orphaned_count = MedicalDocument.query.filter(
                ~MedicalDocument.patient_id.in_(
                    db.session.query(Patient.id).subquery()
                )
            ).count()
            
            if orphaned_count > 0:
                MedicalDocument.query.filter(
                    ~MedicalDocument.patient_id.in_(
                        db.session.query(Patient.id).subquery()
                    )
                ).delete(synchronize_session=False)
                db.session.commit()
                
                flash(f'Cleaned up {orphaned_count} orphaned document records', 'success')
            else:
                flash('No orphaned documents found', 'info')
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='system_cleanup',
            details=f'Performed {cleanup_type} cleanup',
            ip_address=request.remote_addr
        )
        
    except Exception as e:
        logger.error(f"Error in system cleanup: {e}")
        db.session.rollback()
        flash('Error performing system cleanup', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/api/system-stats')
@login_required
@admin_required
def api_system_stats():
    """API endpoint for real-time system statistics."""
    try:
        analytics = SystemAnalytics()
        stats = analytics.get_realtime_stats()
        
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

"""
Admin dashboard and management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
import logging
from datetime import datetime, timedelta
from models import User, AdminLog, PHIFilterSettings
from admin.logs import admin_logger
from admin.analytics import analytics_manager
from ocr.monitor import ocr_monitor
from ocr.phi_filter import phi_filter

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Main admin dashboard"""
    try:
        # Get recent activity
        recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
        
        # Get analytics data
        analytics_data = analytics_manager.get_dashboard_analytics()
        
        # Get OCR statistics
        ocr_stats = ocr_monitor.get_processing_statistics(days=7)
        
        # Get system statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        
        return render_template('admin/dashboard.html',
                             recent_logs=recent_logs,
                             analytics=analytics_data,
                             ocr_stats=ocr_stats,
                             total_users=total_users,
                             active_users=active_users)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        flash('Error loading dashboard. Please try again.', 'error')
        return render_template('admin/dashboard.html',
                             recent_logs=[],
                             analytics={},
                             ocr_stats={},
                             total_users=0,
                             active_users=0)

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin logs viewer"""
    try:
        # Get filter parameters
        event_type = request.args.get('event_type', '').strip()
        user_filter = request.args.get('user', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Build query
        logs_query = AdminLog.query
        
        if event_type:
            logs_query = logs_query.filter(AdminLog.action.ilike(f'%{event_type}%'))
        
        if user_filter:
            logs_query = logs_query.join(User).filter(
                (User.username.ilike(f'%{user_filter}%')) |
                (User.email.ilike(f'%{user_filter}%'))
            )
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                logs_query = logs_query.filter(AdminLog.timestamp >= from_date)
            except ValueError:
                flash('Invalid from date format. Please use YYYY-MM-DD.', 'error')
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                logs_query = logs_query.filter(AdminLog.timestamp < to_date)
            except ValueError:
                flash('Invalid to date format. Please use YYYY-MM-DD.', 'error')
        
        # Get paginated logs
        logs_pagination = logs_query.order_by(AdminLog.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get log statistics
        log_stats = admin_logger.get_log_statistics(days=30)
        
        return render_template('admin/logs.html',
                             logs=logs_pagination.items,
                             pagination=logs_pagination,
                             stats=log_stats,
                             filters={
                                 'event_type': event_type,
                                 'user': user_filter,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
        
    except Exception as e:
        logger.error(f"Error loading admin logs: {str(e)}")
        flash('Error loading logs. Please try again.', 'error')
        return render_template('admin/logs.html',
                             logs=[],
                             pagination=None,
                             stats={},
                             filters={})

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR monitoring dashboard"""
    try:
        # Get OCR statistics
        stats = ocr_monitor.get_processing_statistics(days=7)
        
        # Get recent activity
        recent_activity = ocr_monitor.get_recent_activity(limit=20)
        
        # Get documents needing review
        review_queue = ocr_monitor.get_documents_needing_review(limit=15)
        
        # Get processing trends
        trends = ocr_monitor.get_processing_trends(days=30)
        
        return render_template('admin/ocr_dashboard.html',
                             stats=stats,
                             recent_activity=recent_activity,
                             review_queue=review_queue,
                             trends=trends)
        
    except Exception as e:
        logger.error(f"Error loading OCR dashboard: {str(e)}")
        flash('Error loading OCR dashboard. Please try again.', 'error')
        return render_template('admin/ocr_dashboard.html',
                             stats={},
                             recent_activity=[],
                             review_queue=[],
                             trends={})

@admin_bp.route('/phi')
@login_required
@admin_required
def phi_settings():
    """PHI filtering settings"""
    try:
        settings = PHIFilterSettings.query.first()
        
        if not settings:
            # Create default settings
            settings = PHIFilterSettings()
            from app import db
            db.session.add(settings)
            db.session.commit()
        
        # Get PHI filter statistics
        phi_stats = phi_filter.get_filter_statistics()
        
        return render_template('admin/phi_settings.html',
                             settings=settings,
                             stats=phi_stats)
        
    except Exception as e:
        logger.error(f"Error loading PHI settings: {str(e)}")
        flash('Error loading PHI settings. Please try again.', 'error')
        return render_template('admin/phi_settings.html',
                             settings=None,
                             stats={})

@admin_bp.route('/phi', methods=['POST'])
@login_required
@admin_required
def update_phi_settings():
    """Update PHI filtering settings"""
    try:
        from app import db
        
        settings = PHIFilterSettings.query.first()
        if not settings:
            settings = PHIFilterSettings()
            db.session.add(settings)
        
        # Update settings
        settings.filter_ssn = bool(request.form.get('filter_ssn'))
        settings.filter_phone = bool(request.form.get('filter_phone'))
        settings.filter_mrn = bool(request.form.get('filter_mrn'))
        settings.filter_addresses = bool(request.form.get('filter_addresses'))
        settings.filter_names = bool(request.form.get('filter_names'))
        settings.filter_dates = bool(request.form.get('filter_dates'))
        settings.preserve_medical_values = bool(request.form.get('preserve_medical_values'))
        
        confidence_threshold = request.form.get('confidence_threshold', type=float)
        if confidence_threshold is not None:
            settings.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='update_phi_settings',
            details='Updated PHI filtering settings',
            ip_address=request.remote_addr
        )
        
        flash('PHI filtering settings updated successfully.', 'success')
        
    except Exception as e:
        logger.error(f"Error updating PHI settings: {str(e)}")
        flash('Error updating PHI settings. Please try again.', 'error')
    
    return redirect(url_for('admin.phi_settings'))

@admin_bp.route('/phi/test', methods=['POST'])
@login_required
@admin_required
def test_phi_filter():
    """Test PHI filtering with sample text"""
    try:
        test_text = request.form.get('test_text', '').strip()
        
        if not test_text:
            return jsonify({'success': False, 'error': 'No test text provided'})
        
        # Test the filter
        result = phi_filter.test_filter(test_text)
        
        # Log the test
        admin_logger.log_action(
            user_id=current_user.id,
            action='test_phi_filter',
            details=f'Tested PHI filter - {result["redactions_count"]} redactions',
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'original_text': result['original_text'],
            'filtered_text': result['filtered_text'],
            'phi_detected': result['phi_detected'],
            'redactions_count': result['redactions_count'],
            'confidence': result['confidence']
        })
        
    except Exception as e:
        logger.error(f"Error testing PHI filter: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        flash('Error loading users. Please try again.', 'error')
        return render_template('admin/users.html', users=[])

@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        from app import db
        
        user = User.query.get_or_404(user_id)
        
        # Prevent disabling the current admin user
        if user.id == current_user.id:
            flash('You cannot disable your own account.', 'error')
            return redirect(url_for('admin.users'))
        
        original_status = user.is_active
        user.is_active = not user.is_active
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='toggle_user_status',
            resource_type='User',
            resource_id=user.id,
            details=f'Changed user {user.username} status from {original_status} to {user.is_active}',
            ip_address=request.remote_addr
        )
        
        status_text = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username} has been {status_text}.', 'success')
        
    except Exception as e:
        logger.error(f"Error toggling user status: {str(e)}")
        flash('Error updating user status. Please try again.', 'error')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Analytics and reporting"""
    try:
        # Get comprehensive analytics
        analytics_data = analytics_manager.get_comprehensive_analytics()
        
        return render_template('admin/analytics.html', analytics=analytics_data)
        
    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}")
        flash('Error loading analytics. Please try again.', 'error')
        return render_template('admin/analytics.html', analytics={})

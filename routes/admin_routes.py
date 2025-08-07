# Comprehensive admin dashboard routes and functionality
"""
Admin dashboard routes and functionality - completely separate from EMR/screening dashboards
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging
import functools
import json
import yaml
import io

from models import User, AdminLog, PHIFilterSettings, PrepSheetSettings, ScreeningPreset, ScreeningType
from app import db
from admin.logs import AdminLogger
from admin.analytics import HealthPrepAnalytics
from admin.config import AdminConfig
from admin.presets import PresetManager
from admin.value_analytics import ValueAnalytics
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter
from forms import PrepSheetSettingsForm

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin role"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_access_admin_dashboard():
            flash('Admin access required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Main admin dashboard - comprehensive system overview"""
    try:
        # Initialize analytics modules
        value_analytics = ValueAnalytics()
        ocr_monitor = OCRMonitor()
        phi_filter = PHIFilter()
        preset_manager = PresetManager()

        # Get comprehensive dashboard data
        value_metrics = value_analytics.calculate_comprehensive_value(30)
        ocr_dashboard = ocr_monitor.get_processing_dashboard()
        phi_stats = phi_filter.get_processing_statistics(30)
        preset_stats = preset_manager.get_preset_statistics()

        # Get recent admin activity
        recent_logs = AdminLogger.get_recent_activity(hours=24, limit=10)

        # User management stats
        config_manager = AdminConfig()
        user_summary = config_manager.get_user_summary()

        # System health
        system_health = config_manager.validate_system_health()

        return render_template('admin/comprehensive_dashboard.html',
                             value_metrics=value_metrics,
                             ocr_dashboard=ocr_dashboard,
                             phi_stats=phi_stats,
                             preset_stats=preset_stats,
                             recent_logs=recent_logs,
                             user_summary=user_summary,
                             system_health=system_health)

    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        flash('Error loading admin dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/activity-monitoring')
@login_required
@admin_required
def activity_monitoring():
    """Activity monitoring with enhanced filters"""
    try:
        # Get filter parameters
        page = request.args.get('page', 1, type=int)
        event_type = request.args.get('event_type', '')
        user_id = request.args.get('user_id', type=int)
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        # Build filters
        query = AdminLog.query
        if event_type:
            query = query.filter(AdminLog.action == event_type)
        if user_id:
            query = query.filter(AdminLog.user_id == user_id)
        if start_date:
            query = query.filter(AdminLog.timestamp >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(AdminLog.timestamp <= datetime.strptime(end_date, '%Y-%m-%d'))

        logs_pagination = query.order_by(AdminLog.timestamp.desc()).paginate(
            page=page, per_page=50, error_out=False
        )

        # Get filter options
        users = User.query.all()
        event_types = db.session.query(AdminLog.action).distinct().all()
        event_types = [event.action for event in event_types]

        # Get activity summary
        activity_summary = AdminLogger.get_activity_summary(7)

        return render_template('admin/activity_monitoring.html',
                             logs=logs_pagination.items,
                             pagination=logs_pagination,
                             users=users,
                             event_types=event_types,
                             activity_summary=activity_summary,
                             filters={
                                 'event_type': event_type,
                                 'user_id': user_id,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })

    except Exception as e:
        logger.error(f"Error in activity monitoring: {str(e)}")
        flash('Error loading activity monitoring', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/user-management')
@login_required
@admin_required
def user_management():
    """User management with roles: admin, nurse, MA"""
    try:
        users = User.query.order_by(User.username).all()
        
        # Get user statistics
        total_users = User.query.count()
        admin_users = User.query.filter_by(is_admin=True).count()
        active_users = User.query.filter_by(is_active=True).count()
        
        role_counts = {}
        for role in ['admin', 'nurse', 'ma']:
            role_counts[role] = User.query.filter_by(role=role).count()

        return render_template('admin/user_management.html', 
                             users=users,
                             total_users=total_users,
                             admin_users=admin_users,
                             active_users=active_users,
                             role_counts=role_counts)

    except Exception as e:
        logger.error(f"Error loading user management: {str(e)}")
        flash('Error loading user management', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/user/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user with role assignment"""
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'nurse')
            is_admin = role == 'admin'

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
            new_user.role = role
            new_user.is_admin = is_admin
            new_user.created_by = current_user.id
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()

            # Log the action with enhanced tracking
            AdminLogger.log(
                user_id=current_user.id,
                action='create_user',
                details=f"Created user: {username}",
                previous_value=None,
                new_value=json.dumps({
                    'username': username,
                    'email': email,
                    'role': role,
                    'is_admin': is_admin
                }),
                resource_type='user',
                resource_id=str(new_user.id)
            )

            flash(f'User {username} created successfully as {role}', 'success')
            return redirect(url_for('admin.user_management'))

        return render_template('admin/add_user.html')

    except Exception as e:
        logger.error(f"Error adding user: {str(e)}")
        flash('Error creating user', 'error')
        return render_template('admin/add_user.html')

@admin_bp.route('/user/<int:user_id>/edit-role', methods=['POST'])
@login_required
@admin_required
def edit_user_role(user_id):
    """Edit user role"""
    try:
        user = User.query.get_or_404(user_id)
        new_role = request.form.get('role')
        
        if new_role not in ['admin', 'nurse', 'ma']:
            flash('Invalid role specified', 'error')
            return redirect(url_for('admin.user_management'))
        
        # Don't allow changing own role
        if user.id == current_user.id:
            flash('Cannot modify your own role', 'error')
            return redirect(url_for('admin.user_management'))

        old_role = user.role
        user.role = new_role
        user.is_admin = (new_role == 'admin')
        user.updated_at = datetime.utcnow()
        
        db.session.commit()

        # Enhanced logging with previous/new values
        AdminLogger.log(
            user_id=current_user.id,
            action='update_user_role',
            details=f"Changed user {user.username} role from {old_role} to {new_role}",
            previous_value=old_role,
            new_value=new_role,
            resource_type='user',
            resource_id=str(user_id)
        )

        flash(f'User {user.username} role updated to {new_role}', 'success')
        return redirect(url_for('admin.user_management'))

    except Exception as e:
        logger.error(f"Error editing user role: {str(e)}")
        flash('Error updating user role', 'error')
        return redirect(url_for('admin.user_management'))

@admin_bp.route('/preset-management')
@login_required
@admin_required
def preset_management():
    """Screening type preset management"""
    try:
        preset_manager = PresetManager()
        presets = preset_manager.get_all_presets()
        preset_stats = preset_manager.get_preset_statistics()

        return render_template('admin/preset_management.html',
                             presets=presets,
                             preset_stats=preset_stats)

    except Exception as e:
        logger.error(f"Error loading preset management: {str(e)}")
        flash('Error loading preset management', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/preset/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_preset():
    """Create new screening preset"""
    try:
        if request.method == 'POST':
            preset_manager = PresetManager()
            
            name = request.form.get('name')
            description = request.form.get('description', '')
            specialty = request.form.get('specialty', 'general')
            
            # Generate preset from current screening types
            result = preset_manager.generate_preset_from_current(
                name, description, specialty, current_user.id
            )
            
            if result['success']:
                AdminLogger.log(
                    user_id=current_user.id,
                    action='create_preset',
                    details=f"Created preset: {name}",
                    resource_type='preset',
                    resource_id=str(result['preset_id'])
                )
                flash(f'Preset "{name}" created successfully', 'success')
                return redirect(url_for('admin.preset_management'))
            else:
                flash(f'Error creating preset: {result["error"]}', 'error')

        return render_template('admin/create_preset.html')

    except Exception as e:
        logger.error(f"Error creating preset: {str(e)}")
        flash('Error creating preset', 'error')
        return render_template('admin/create_preset.html')

@admin_bp.route('/preset/<int:preset_id>/export')
@login_required
@admin_required
def export_preset(preset_id):
    """Export preset as JSON"""
    try:
        preset_manager = PresetManager()
        result = preset_manager.export_preset_json(preset_id)
        
        if result['success']:
            # Create downloadable file
            preset_data = json.dumps(result['data'], indent=2)
            
            output = io.StringIO()
            output.write(preset_data)
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='application/json',
                as_attachment=True,
                download_name=f"preset_{result['data']['name'].replace(' ', '_')}.json"
            )
        else:
            flash(f'Error exporting preset: {result["error"]}', 'error')
            return redirect(url_for('admin.preset_management'))

    except Exception as e:
        logger.error(f"Error exporting preset: {str(e)}")
        flash('Error exporting preset', 'error')
        return redirect(url_for('admin.preset_management'))

@admin_bp.route('/preset/import', methods=['POST'])
@login_required
@admin_required
def import_preset():
    """Import preset from JSON/YAML file"""
    try:
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('admin.preset_management'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('admin.preset_management'))

        # Read and parse file
        content = file.read().decode('utf-8')
        filename = file.filename or ''
        
        if filename.endswith('.json'):
            data = json.loads(content)
        elif filename.endswith('.yaml') or filename.endswith('.yml'):
            data = yaml.safe_load(content)
        else:
            flash('Only JSON and YAML files are supported', 'error')
            return redirect(url_for('admin.preset_management'))

        # Import preset
        preset_manager = PresetManager()
        result = preset_manager.import_preset_from_data(data, current_user.id)
        
        if result['success']:
            AdminLogger.log(
                user_id=current_user.id,
                action='import_preset',
                details=f"Imported preset from file: {file.filename}",
                resource_type='preset',
                resource_id=str(result['preset_id'])
            )
            flash('Preset imported successfully', 'success')
        else:
            flash(f'Error importing preset: {result["error"]}', 'error')

        return redirect(url_for('admin.preset_management'))

    except Exception as e:
        logger.error(f"Error importing preset: {str(e)}")
        flash('Error importing preset', 'error')
        return redirect(url_for('admin.preset_management'))

@admin_bp.route('/phi-monitoring')
@login_required
@admin_required
def phi_monitoring():
    """PHI statistics and monitoring dashboard"""
    try:
        phi_filter = PHIFilter()
        
        # Get PHI statistics
        phi_stats = phi_filter.get_processing_statistics(30)
        
        # Get current settings
        phi_settings = phi_filter._get_filter_settings()
        
        return render_template('admin/phi_monitoring.html',
                             phi_stats=phi_stats,
                             phi_settings=phi_settings)

    except Exception as e:
        logger.error(f"Error loading PHI monitoring: {str(e)}")
        flash('Error loading PHI monitoring', 'error')
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
        return jsonify({'success': True, 'result': result})

    except Exception as e:
        logger.error(f"Error testing PHI filter: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/value-analytics')
@login_required
@admin_required
def value_analytics():
    """Customer value analytics dashboard"""
    try:
        value_analytics = ValueAnalytics()
        
        # Get comprehensive value data
        value_data = value_analytics.calculate_comprehensive_value(30)
        
        # Get ROI report
        roi_report = value_analytics.generate_roi_report(30)
        
        # Get trend analysis
        trends = value_analytics.get_trend_analysis(4)
        
        return render_template('admin/value_analytics.html',
                             value_data=value_data,
                             roi_report=roi_report,
                             trends=trends)

    except Exception as e:
        logger.error(f"Error loading value analytics: {str(e)}")
        flash('Error loading value analytics', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/export-logs')
@login_required
@admin_required
def export_logs():
    """Export admin logs with enhanced tracking data"""
    try:
        format_type = request.args.get('format', 'json')
        days = request.args.get('days', 30, type=int)

        start_date = datetime.utcnow() - timedelta(days=days)
        export_data = AdminLogger.export_logs(start_date=start_date)

        if format_type == 'json':
            output = json.dumps(export_data, indent=2)
            mimetype = 'application/json'
            filename = f'admin_logs_{start_date.strftime("%Y%m%d")}.json'
        else:
            # CSV format
            import csv
            output = io.StringIO()
            if export_data:
                writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
                writer.writeheader()
                writer.writerows(export_data)
            output.seek(0)
            output = output.getvalue()
            mimetype = 'text/csv'
            filename = f'admin_logs_{start_date.strftime("%Y%m%d")}.csv'

        return send_file(
            io.BytesIO(output.encode()),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        flash('Error exporting logs', 'error')
        return redirect(url_for('admin.activity_monitoring'))

# API endpoints for dashboard updates
@admin_bp.route('/api/dashboard-metrics')
@login_required
@admin_required
def dashboard_metrics_api():
    """API endpoint for real-time dashboard metrics"""
    try:
        value_analytics = ValueAnalytics()
        ocr_monitor = OCRMonitor()
        
        metrics = {
            'value_metrics': value_analytics.calculate_comprehensive_value(1),  # Last 24 hours
            'ocr_metrics': ocr_monitor.get_processing_dashboard(),
            'user_count': User.query.filter_by(is_active=True).count(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify({'success': True, 'metrics': metrics})

    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/api/system-health')
@login_required
@admin_required
def system_health_api():
    """API endpoint for system health monitoring"""
    try:
        config_manager = AdminConfig()
        health_data = config_manager.validate_system_health()
        return jsonify(health_data)

    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return jsonify({'error': str(e)}), 500
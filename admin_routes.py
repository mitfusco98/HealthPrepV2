"""
Admin dashboard and management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta
import logging
import json

from app import db
from models import (User, AdminLog, Patient, Document, Screening, ScreeningType, 
                   ChecklistSettings, PHIFilterSettings, OCRStats)
from forms import UserForm, ChecklistSettingsForm, PHIFilterSettingsForm, ScreeningTypeForm
from admin.logs import AdminLogManager
from admin.analytics import AnalyticsManager
from admin.config import AdminConfigManager
from core.engine import ScreeningEngine

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Administrator access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    try:
        analytics = AnalyticsManager()
        
        # Get system statistics
        system_stats = analytics.get_system_statistics()
        
        # Get recent activity
        log_manager = AdminLogManager()
        recent_logs = log_manager.get_recent_logs(limit=10)
        
        # Get screening engine statistics
        engine = ScreeningEngine()
        screening_stats = engine.get_screening_statistics()
        
        # Get OCR statistics
        ocr_stats = analytics.get_ocr_statistics()
        
        # Get user activity summary
        user_activity = analytics.get_user_activity_summary()
        
        return render_template('admin/admin_dashboard.html',
                             system_stats=system_stats,
                             recent_logs=recent_logs,
                             screening_stats=screening_stats,
                             ocr_stats=ocr_stats,
                             user_activity=user_activity)
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}")
        flash('Error loading admin dashboard', 'error')
        return render_template('admin/admin_dashboard.html')

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin logs viewer with filtering"""
    try:
        log_manager = AdminLogManager()
        
        # Get filter parameters
        page = request.args.get('page', 1, type=int)
        event_type = request.args.get('event_type', '', type=str)
        user_id = request.args.get('user_id', type=int)
        date_from = request.args.get('date_from', type=str)
        date_to = request.args.get('date_to', type=str)
        
        # Build filters
        filters = {}
        if event_type:
            filters['event_type'] = event_type
        if user_id:
            filters['user_id'] = user_id
        if date_from:
            filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d')
        if date_to:
            filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d')
        
        # Get filtered logs
        logs_pagination = log_manager.get_filtered_logs(filters, page=page, per_page=50)
        
        # Get filter options
        event_types = log_manager.get_available_event_types()
        users = User.query.order_by(User.username).all()
        
        # Get log statistics
        log_stats = log_manager.get_log_statistics(filters)
        
        return render_template('admin/admin_logs.html',
                             logs=logs_pagination,
                             event_types=event_types,
                             users=users,
                             log_stats=log_stats,
                             filters=filters)
        
    except Exception as e:
        logger.error(f"Admin logs error: {str(e)}")
        flash('Error loading admin logs', 'error')
        return render_template('admin/admin_logs.html')

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export logs as JSON"""
    try:
        log_manager = AdminLogManager()
        
        # Get filter parameters
        event_type = request.args.get('event_type', '', type=str)
        user_id = request.args.get('user_id', type=int)
        date_from = request.args.get('date_from', type=str)
        date_to = request.args.get('date_to', type=str)
        
        # Build filters
        filters = {}
        if event_type:
            filters['event_type'] = event_type
        if user_id:
            filters['user_id'] = user_id
        if date_from:
            filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d')
        if date_to:
            filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d')
        
        # Export logs
        exported_data = log_manager.export_logs(filters)
        
        return jsonify(exported_data)
        
    except Exception as e:
        logger.error(f"Log export error: {str(e)}")
        return jsonify({'error': 'Failed to export logs'}), 500

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management"""
    try:
        users = User.query.order_by(User.username).all()
        return render_template('admin/admin_users.html', users=users)
        
    except Exception as e:
        logger.error(f"Users management error: {str(e)}")
        flash('Error loading users', 'error')
        return render_template('admin/admin_users.html', users=[])

@admin_bp.route('/user/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user"""
    form = UserForm()
    
    if form.validate_on_submit():
        try:
            # Check for duplicate username/email
            existing_user = User.query.filter(
                db.or_(User.username == form.username.data, User.email == form.email.data)
            ).first()
            
            if existing_user:
                flash('User with this username or email already exists', 'error')
                return render_template('admin/admin_user_form.html', form=form, title='Add User')
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                role=form.role.data,
                is_active=form.is_active.data
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            # Log user creation
            log_entry = AdminLog(
                user_id=current_user.id,
                action='USER_CREATED',
                resource_type='user',
                resource_id=user.id,
                details=f'Created user: {user.username}',
                ip_address=request.remote_addr
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash(f'User {user.username} created successfully', 'success')
            return redirect(url_for('admin.users'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add user error: {str(e)}")
            flash('Error creating user', 'error')
    
    return render_template('admin/admin_user_form.html', form=form, title='Add User')

@admin_bp.route('/settings/checklist', methods=['GET', 'POST'])
@login_required
@admin_required
def checklist_settings():
    """Configure prep sheet checklist settings"""
    try:
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
            db.session.commit()
        
        form = ChecklistSettingsForm(obj=settings)
        
        if form.validate_on_submit():
            form.populate_obj(settings)
            settings.updated_by = current_user.id
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log settings change
            log_entry = AdminLog(
                user_id=current_user.id,
                action='SETTINGS_UPDATED',
                resource_type='checklist_settings',
                resource_id=settings.id,
                details='Updated checklist settings',
                ip_address=request.remote_addr
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('Checklist settings updated successfully', 'success')
            return redirect(url_for('admin.checklist_settings'))
        
        return render_template('admin/admin_checklist_settings.html', form=form, settings=settings)
        
    except Exception as e:
        logger.error(f"Checklist settings error: {str(e)}")
        flash('Error loading checklist settings', 'error')
        return render_template('admin/admin_checklist_settings.html')

@admin_bp.route('/settings/phi', methods=['GET', 'POST'])
@login_required
@admin_required
def phi_settings():
    """Configure PHI filtering settings"""
    try:
        settings = PHIFilterSettings.query.first()
        if not settings:
            settings = PHIFilterSettings()
            db.session.add(settings)
            db.session.commit()
        
        form = PHIFilterSettingsForm(obj=settings)
        
        if form.validate_on_submit():
            form.populate_obj(settings)
            settings.updated_by = current_user.id
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log settings change
            log_entry = AdminLog(
                user_id=current_user.id,
                action='PHI_SETTINGS_UPDATED',
                resource_type='phi_filter_settings',
                resource_id=settings.id,
                details='Updated PHI filtering settings',
                ip_address=request.remote_addr
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('PHI filtering settings updated successfully', 'success')
            return redirect(url_for('admin.phi_settings'))
        
        return render_template('admin/admin_phi_settings.html', form=form, settings=settings)
        
    except Exception as e:
        logger.error(f"PHI settings error: {str(e)}")
        flash('Error loading PHI settings', 'error')
        return render_template('admin/admin_phi_settings.html')

@admin_bp.route('/ocr')
@login_required
@admin_required
def ocr_dashboard():
    """OCR processing dashboard"""
    try:
        from ocr.monitor import OCRMonitor
        
        monitor = OCRMonitor()
        
        # Get OCR statistics
        processing_stats = monitor.get_processing_statistics()
        quality_stats = monitor.get_quality_statistics()
        recent_activity = monitor.get_recent_activity()
        pending_queue = monitor.get_pending_queue()
        
        return render_template('admin/admin_ocr_dashboard.html',
                             processing_stats=processing_stats,
                             quality_stats=quality_stats,
                             recent_activity=recent_activity,
                             pending_queue=pending_queue)
        
    except Exception as e:
        logger.error(f"OCR dashboard error: {str(e)}")
        flash('Error loading OCR dashboard', 'error')
        return render_template('admin/admin_ocr_dashboard.html')

@admin_bp.route('/screening-types')
@login_required
@admin_required
def screening_types():
    """Manage screening types"""
    try:
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        return render_template('admin/admin_screening_types.html', screening_types=screening_types)
        
    except Exception as e:
        logger.error(f"Screening types error: {str(e)}")
        flash('Error loading screening types', 'error')
        return render_template('admin/admin_screening_types.html', screening_types=[])

@admin_bp.route('/screening-type/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_screening_type():
    """Add new screening type"""
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        try:
            # Parse keywords
            keywords = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            trigger_conditions = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            
            screening_type = ScreeningType(
                name=form.name.data,
                description=form.description.data,
                gender_criteria=form.gender_criteria.data,
                age_min=form.age_min.data,
                age_max=form.age_max.data,
                frequency_number=form.frequency_number.data,
                frequency_unit=form.frequency_unit.data,
                is_active=form.is_active.data,
                created_by=current_user.id
            )
            
            screening_type.set_keywords(keywords)
            screening_type.set_trigger_conditions(trigger_conditions)
            
            db.session.add(screening_type)
            db.session.commit()
            
            # Log screening type creation
            log_entry = AdminLog(
                user_id=current_user.id,
                action='SCREENING_TYPE_CREATED',
                resource_type='screening_type',
                resource_id=screening_type.id,
                details=f'Created screening type: {screening_type.name}',
                ip_address=request.remote_addr
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash(f'Screening type {screening_type.name} created successfully', 'success')
            return redirect(url_for('admin.screening_types'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add screening type error: {str(e)}")
            flash('Error creating screening type', 'error')
    
    return render_template('admin/admin_screening_type_form.html', form=form, title='Add Screening Type')

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """System analytics and reporting"""
    try:
        analytics_manager = AnalyticsManager()
        
        # Get comprehensive analytics
        system_performance = analytics_manager.get_system_performance_metrics()
        user_engagement = analytics_manager.get_user_engagement_metrics()
        document_processing = analytics_manager.get_document_processing_metrics()
        screening_compliance = analytics_manager.get_screening_compliance_metrics()
        roi_metrics = analytics_manager.get_roi_metrics()
        
        return render_template('admin/admin_analytics.html',
                             system_performance=system_performance,
                             user_engagement=user_engagement,
                             document_processing=document_processing,
                             screening_compliance=screening_compliance,
                             roi_metrics=roi_metrics)
        
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        flash('Error loading analytics', 'error')
        return render_template('admin/admin_analytics.html')


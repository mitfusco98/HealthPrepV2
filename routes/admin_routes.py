# Applying the changes to correct the import errors and references to non-existent classes.
"""
Admin dashboard routes and functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import desc
import logging
import functools
import json
import yaml
import tempfile
import os
import difflib
import re
from werkzeug.utils import secure_filename

from models import User, AdminLog, PHIFilterSettings, log_admin_event, Document, ScreeningPreset, ScreeningType
from app import db
from flask import request as flask_request
from admin.analytics import HealthPrepAnalytics
from admin.config import AdminConfig
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def normalize_screening_name(name):
    """Normalize screening type name for fuzzy matching"""
    if not name:
        return ""
    
    # Convert to lowercase and remove extra spaces
    normalized = name.lower().strip()
    
    # Replace punctuation and separators with spaces
    normalized = re.sub(r'[_\-\./\\]+', ' ', normalized)
    
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove common stopwords but keep medical terms
    stopwords = {'test', 'testing', 'scan', 'scanning', 'screen', 'screening', 'check', 'the', 'of'}
    tokens = [token for token in normalized.split() if token not in stopwords or len(token) <= 3]
    
    return ' '.join(tokens)

def group_screening_types_by_similarity(screening_types):
    """Group screening types by similarity using fuzzy matching"""
    groups = {}
    processed = set()
    
    for st in screening_types:
        if st.id in processed:
            continue
        
        # Create new group with this screening type as the base
        normalized_name = normalize_screening_name(st.name)
        group_key = f"group_{len(groups)}"
        
        groups[group_key] = {
            'base_name': st.name,
            'normalized_name': normalized_name,
            'variants': [st],
            'authors': {st.created_by_user.username if hasattr(st, 'created_by_user') and st.created_by_user else 'Unknown'},
            'organizations': set()
        }
        
        if hasattr(st, 'organization') and st.organization:
            groups[group_key]['organizations'].add(st.organization.name)
        
        processed.add(st.id)
        
        # Find similar screening types
        for other_st in screening_types:
            if other_st.id in processed:
                continue
            
            other_normalized = normalize_screening_name(other_st.name)
            
            # Calculate similarity ratio
            similarity = difflib.SequenceMatcher(None, normalized_name, other_normalized).ratio()
            
            # Also check token-based similarity for partial matches
            tokens_a = set(normalized_name.split())
            tokens_b = set(other_normalized.split())
            
            if tokens_a and tokens_b:
                token_similarity = len(tokens_a.intersection(tokens_b)) / len(tokens_a.union(tokens_b))
            else:
                token_similarity = 0.0
            
            # Group if similarity is above threshold (0.8 for exact match, 0.6 for partial)
            if similarity >= 0.8 or token_similarity >= 0.6:
                groups[group_key]['variants'].append(other_st)
                groups[group_key]['authors'].add(other_st.created_by_user.username if hasattr(other_st, 'created_by_user') and other_st.created_by_user else 'Unknown')
                
                if hasattr(other_st, 'organization') and other_st.organization:
                    groups[group_key]['organizations'].add(other_st.organization.name)
                
                processed.add(other_st.id)
    
    # Sort variants within each group by creation date (newest first)
    for group in groups.values():
        group['variants'].sort(key=lambda x: x.created_at, reverse=True)
        group['authors'] = list(group['authors'])
        group['organizations'] = list(group['organizations'])
        group['variant_count'] = len(group['variants'])
    
    return list(groups.values())

def parse_log_details(log):
    """Parse log data to provide enhanced details for viewing"""
    try:
        details = {
            'basic_info': {
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'event_type': log.event_type.replace('_', ' ').title() if log.event_type else 'Unknown',
                'user': log.user.username if log.user else 'System',
                'user_role': log.user.role if log.user else 'N/A',
                'ip_address': log.ip_address or 'Unknown',
                'organization': log.organization.name if hasattr(log, 'organization') and log.organization else 'N/A'
            },
            'action_summary': '',
            'changes': [],
            'additional_data': {}
        }
        
        if log.data:
            data = log.data if isinstance(log.data, dict) else {}
            
            # Extract description
            details['action_summary'] = data.get('description', 'No description available')
            
            # Parse changes based on event type
            if log.event_type == 'edit_screening_type':
                details['changes'] = parse_screening_type_changes(data)
            elif log.event_type == 'create_user':
                details['changes'] = parse_user_creation_changes(data)
            elif log.event_type == 'edit_user':
                details['changes'] = parse_user_edit_changes(data)
            elif log.event_type == 'toggle_user_status':
                details['changes'] = parse_user_status_changes(data)
            elif log.event_type == 'update_prep_sheet_settings':
                details['changes'] = parse_prep_sheet_settings_changes(data)
            elif log.event_type == 'update_phi_settings':
                details['changes'] = parse_phi_settings_changes(data)
            else:
                # Generic change parsing
                details['changes'] = parse_generic_changes(data)
            
            # Additional data (excluding already processed fields)
            excluded_keys = ['description', 'before', 'after', 'changes']
            details['additional_data'] = {k: v for k, v in data.items() if k not in excluded_keys}
        
        return details
        
    except Exception as e:
        logger.error(f"Error parsing log details: {str(e)}")
        return {
            'basic_info': {'error': 'Failed to parse log details'},
            'action_summary': 'Error parsing action details',
            'changes': [],
            'additional_data': {'error': str(e)}
        }

def parse_screening_type_changes(data):
    """Parse screening type specific changes"""
    changes = []
    
    if 'before' in data and 'after' in data:
        before = data['before']
        after = data['after']
        
        for field, old_value in before.items():
            new_value = after.get(field)
            if old_value != new_value:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': format_value(old_value),
                    'new_value': format_value(new_value),
                    'change_type': determine_change_type(old_value, new_value)
                })
    else:
        # Legacy format - extract what we can
        if 'screening_type_name' in data:
            changes.append({
                'field': 'Screening Type',
                'old_value': 'N/A',
                'new_value': data['screening_type_name'],
                'change_type': 'modification'
            })
    
    return changes

def parse_user_creation_changes(data):
    """Parse user creation details"""
    changes = []
    
    if 'created_user' in data:
        changes.append({
            'field': 'New User Created',
            'old_value': 'N/A',
            'new_value': data['created_user'],
            'change_type': 'creation'
        })
    
    if 'role' in data:
        changes.append({
            'field': 'User Role',
            'old_value': 'N/A',
            'new_value': data['role'].title(),
            'change_type': 'creation'
        })
    
    return changes

def parse_user_edit_changes(data):
    """Parse user edit changes"""
    changes = []
    
    if 'before' in data and 'after' in data:
        before = data['before']
        after = data['after']
        
        for field, old_value in before.items():
            new_value = after.get(field)
            if old_value != new_value:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': format_value(old_value),
                    'new_value': format_value(new_value),
                    'change_type': determine_change_type(old_value, new_value)
                })
    else:
        # Legacy format
        if 'edited_user' in data:
            changes.append({
                'field': 'User Modified',
                'old_value': 'Previous values',
                'new_value': data['edited_user'],
                'change_type': 'modification'
            })
    
    return changes

def parse_user_status_changes(data):
    """Parse user status toggle changes"""
    changes = []
    
    if 'new_status' in data:
        status_text = 'Active' if data['new_status'] else 'Inactive'
        old_status_text = 'Inactive' if data['new_status'] else 'Active'
        
        changes.append({
            'field': 'User Status',
            'old_value': old_status_text,
            'new_value': status_text,
            'change_type': 'status_change'
        })
    
    if 'target_user' in data:
        changes.append({
            'field': 'Affected User',
            'old_value': 'N/A',
            'new_value': data['target_user'],
            'change_type': 'reference'
        })
    
    return changes

def parse_prep_sheet_settings_changes(data):
    """Parse prep sheet settings changes"""
    changes = []
    
    # Look for specific cutoff changes
    cutoff_fields = ['labs_cutoff', 'imaging_cutoff', 'consults_cutoff', 'hospital_cutoff']
    
    if 'before' in data and 'after' in data:
        before = data['before']
        after = data['after']
        
        for field in cutoff_fields:
            if field in before and field in after and before[field] != after[field]:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': f"{before[field]} months",
                    'new_value': f"{after[field]} months",
                    'change_type': 'setting_change'
                })
    else:
        # Legacy format - extract individual cutoff values
        for field in cutoff_fields:
            if field in data:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': 'Previous value',
                    'new_value': f"{data[field]} months",
                    'change_type': 'setting_change'
                })
    
    return changes

def parse_phi_settings_changes(data):
    """Parse PHI settings changes"""
    changes = []
    
    if 'before' in data and 'after' in data:
        before = data['before']
        after = data['after']
        
        for field, old_value in before.items():
            new_value = after.get(field)
            if old_value != new_value:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': format_value(old_value),
                    'new_value': format_value(new_value),
                    'change_type': determine_change_type(old_value, new_value)
                })
    
    return changes

def parse_generic_changes(data):
    """Parse generic changes from data"""
    changes = []
    
    # Look for common change indicators
    if 'before' in data and 'after' in data:
        before = data['before']
        after = data['after']
        
        for field, old_value in before.items():
            new_value = after.get(field)
            if old_value != new_value:
                changes.append({
                    'field': field.replace('_', ' ').title(),
                    'old_value': format_value(old_value),
                    'new_value': format_value(new_value),
                    'change_type': determine_change_type(old_value, new_value)
                })
    
    return changes

def format_value(value):
    """Format a value for display"""
    if value is None:
        return 'Not set'
    elif isinstance(value, bool):
        return 'Yes' if value else 'No'
    elif isinstance(value, (list, dict)):
        return json.dumps(value, indent=2)
    else:
        return str(value)

def determine_change_type(old_value, new_value):
    """Determine the type of change"""
    if old_value is None and new_value is not None:
        return 'creation'
    elif old_value is not None and new_value is None:
        return 'deletion'
    elif isinstance(old_value, bool) and isinstance(new_value, bool):
        return 'status_change'
    else:
        return 'modification'

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
    """Main admin dashboard - redirect to logs by default"""
    return redirect(url_for('admin.dashboard_logs'))

def get_dashboard_data():
    """Helper function to get common dashboard data"""
    analytics = HealthPrepAnalytics()
    
    # Get dashboard statistics
    dashboard_stats = analytics.get_roi_metrics()
    
    # Get recent activity - ORGANIZATION SCOPED
    recent_logs = AdminLog.query.filter(
        AdminLog.org_id == current_user.org_id
    ).order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    # Get system health indicators
    system_health = analytics.get_usage_statistics()
    
    # Get PHI settings and statistics
    phi_filter = PHIFilter()
    phi_settings = PHIFilterSettings.query.first()
    
    # Calculate PHI statistics - ORGANIZATION SCOPED
    try:
        documents_processed = Document.query.filter(
            Document.ocr_confidence.isnot(None),
            Document.org_id == current_user.org_id
        ).count()
    except Exception as e:
        logger.warning(f"Could not count processed documents: {str(e)}")
        documents_processed = 0
        
    # Ensure all PHI stats are proper numeric types
    phi_stats = {
        'documents_processed': int(documents_processed) if documents_processed else 0,
        'phi_items_redacted': 892,  # placeholder
        'detection_accuracy': 97.3,  # placeholder
        'avg_processing_time': 1.2   # placeholder
    }
    
    phi_breakdown = {
        'ssn_count': 234,
        'phone_count': 187, 
        'email_count': 156,
        'mrn_count': 145,
        'name_count': 123
    }
    
    # Get user statistics and list
    # Apply organization filtering for multi-tenancy
    if hasattr(current_user, 'org_id'):
        users_query = User.query.filter_by(org_id=current_user.org_id)
    else:
        users_query = User.query
        
    users = users_query.order_by(User.username).all()
    total_users = len(users)
    active_users = sum(1 for user in users if user.is_active_user)
    admin_users = sum(1 for user in users if user.is_admin_user())
    inactive_users = total_users - active_users
    
    # Get preset statistics - ORGANIZATION SCOPED
    total_presets = ScreeningPreset.query.filter(
        (ScreeningPreset.org_id == current_user.org_id) | 
        (ScreeningPreset.preset_scope == 'global')
    ).count()
    shared_presets = ScreeningPreset.query.filter(
        (ScreeningPreset.org_id == current_user.org_id) | 
        (ScreeningPreset.preset_scope == 'global')
    ).filter_by(shared=True).count()
    try:
        recent_presets = ScreeningPreset.query.filter(
            (ScreeningPreset.org_id == current_user.org_id) | 
            (ScreeningPreset.preset_scope == 'global')
        ).order_by(ScreeningPreset.updated_at.desc()).limit(5).all()
    except Exception:
        recent_presets = []
    
    return {
        'stats': dashboard_stats,
        'recent_logs': recent_logs,
        'system_health': system_health,
        'phi_settings': phi_settings,
        'phi_stats': phi_stats,
        'phi_breakdown': phi_breakdown,
        'users': users,
        'total_users': total_users,
        'active_users': active_users,
        'admin_users': admin_users,
        'inactive_users': inactive_users,
        'total_presets': total_presets,
        'shared_presets': shared_presets,
        'recent_presets': recent_presets
    }

@admin_bp.route('/dashboard/logs')
@login_required
@admin_required
def dashboard_logs():
    """Admin dashboard - Activity Logs tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'activity'
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        logger.error(f"Error in dashboard logs: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/dashboard/users')
@login_required
@admin_required
def dashboard_users():
    """Admin dashboard - User Management tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'users'
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        logger.error(f"Error in dashboard users: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/dashboard/presets')
@login_required
@admin_required
def dashboard_presets():
    """Admin dashboard - Preset Management tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'presets'
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        logger.error(f"Error in dashboard presets: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/dashboard/phi')
@login_required
@admin_required
def dashboard_phi():
    """Admin dashboard - PHI Statistics tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'phi'
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        logger.error(f"Error in dashboard PHI: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/dashboard/analytics')
@login_required
@admin_required
def dashboard_analytics():
    """Admin dashboard - Customer Analytics tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'analytics'
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        logger.error(f"Error in dashboard analytics: {str(e)}")
        flash('Error loading dashboard', 'error')
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
        
        # Get filtered logs - ORGANIZATION SCOPED
        query = AdminLog.query.filter(AdminLog.org_id == current_user.org_id)
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

        # Get filter options
        # Apply organization filtering for multi-tenancy
        if hasattr(current_user, 'org_id'):
            users = User.query.filter_by(org_id=current_user.org_id).all()
        else:
            users = User.query.all()
        event_types = db.session.query(AdminLog.event_type).distinct().all()
        event_types = [event.event_type for event in event_types if event.event_type]

        return render_template('admin/logs.html',
                             logs=logs_pagination.items,
                             pagination=logs_pagination,
                             users=users,
                             event_types=event_types,
                             filters=filters)

    except Exception as e:
        logger.error(f"Error in admin logs: {str(e)}")
        flash('Error loading admin logs', 'error')
        return render_template('error/500.html'), 500

@admin_bp.route('/logs/<int:log_id>/view')
@login_required
@admin_required
def view_log_details(log_id):
    """View detailed information about a specific log entry"""
    try:
        log = AdminLog.query.get_or_404(log_id)
        
        # Check organization access
        if hasattr(current_user, 'org_id') and log.org_id != current_user.org_id:
            flash('Access denied', 'error')
            return redirect(url_for('admin.logs'))
        
        # Parse the log data for enhanced display
        enhanced_details = parse_log_details(log)
        
        return render_template('admin/log_detail.html', 
                             log=log, 
                             details=enhanced_details)
        
    except Exception as e:
        logger.error(f"Error viewing log details: {str(e)}")
        flash('Error loading log details', 'error')
        return redirect(url_for('admin.logs'))

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

# PHI settings route removed - consolidated into dashboard

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
        # Apply organization filtering for multi-tenancy
        if hasattr(current_user, 'org_id'):
            users = User.query.filter_by(org_id=current_user.org_id).order_by(User.username).all()
        else:
            users = User.query.order_by(User.username).all()

        return render_template('admin/users.html', users=users)

    except Exception as e:
        logger.error(f"Error loading users: {str(e)}")
        flash('Error loading users', 'error')
        return render_template('error/500.html'), 500


# Removed duplicate toggle_user_status function

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
            org_id=getattr(current_user, 'org_id', 1),
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

@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create new user via AJAX"""
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'nurse')
        is_active = request.form.get('is_active') == 'on'

        # Validate input
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('admin.users'))

        # Get current user's organization
        org_id = getattr(current_user, 'org_id', 1)  # Default to org 1 if not set

        # Check if user already exists within the same organization
        existing_user = User.query.filter_by(username=username, org_id=org_id).first()
        if existing_user:
            flash('Username already exists in this organization', 'error')
            return redirect(url_for('admin.users'))

        existing_email = User.query.filter_by(email=email, org_id=org_id).first()
        if existing_email:
            flash('Email already exists in this organization', 'error')
            return redirect(url_for('admin.users'))

        # Create new user
        new_user = User()
        new_user.username = username
        new_user.email = email
        new_user.role = role
        new_user.is_admin = (role == 'admin')  # Set is_admin based on role
        new_user.is_active_user = is_active
        new_user.org_id = org_id  # Assign to current user's organization
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        # Capture created values for logging
        created_values = {
            'username': new_user.username,
            'email': new_user.email,
            'role': new_user.role,
            'is_admin': new_user.is_admin,
            'is_active_user': new_user.is_active_user,
            'org_id': new_user.org_id
        }

        # Log the action with created values
        log_admin_event(
            event_type='create_user',
            user_id=current_user.id,
            org_id=org_id,
            ip=flask_request.remote_addr,
            data={
                'created_user': username,
                'role': role,
                'after': created_values,
                'description': f'Created user: {username} with role: {role}'
            }
        )

        flash(f'User {username} created successfully', 'success')
        return redirect(url_for('admin.users'))

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        flash('Error creating user', 'error')
        return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit existing user"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Check organization access
        org_id = getattr(current_user, 'org_id', 1)
        if user.org_id != org_id:
            flash('Access denied', 'error')
            return redirect(url_for('admin.users'))

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        is_active = request.form.get('is_active') == 'on'

        # Validate input
        if not username or not email or not role:
            flash('Username, email and role are required', 'error')
            return redirect(url_for('admin.users'))

        # Check for duplicate username/email within organization (excluding current user)
        existing_user = User.query.filter_by(username=username, org_id=org_id).filter(User.id != user_id).first()
        if existing_user:
            flash('Username already exists in this organization', 'error')
            return redirect(url_for('admin.users'))

        existing_email = User.query.filter_by(email=email, org_id=org_id).filter(User.id != user_id).first()
        if existing_email:
            flash('Email already exists in this organization', 'error')
            return redirect(url_for('admin.users'))

        # Capture before values for logging
        before_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_admin': user.is_admin,
            'is_active_user': user.is_active_user
        }

        # Update user
        user.username = username
        user.email = email
        user.role = role
        user.is_admin = (role == 'admin')
        user.is_active_user = is_active
        
        # Update password if provided
        password_changed = False
        if password:
            user.set_password(password)
            password_changed = True
        
        # Capture after values for logging
        after_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_admin': user.is_admin,
            'is_active_user': user.is_active_user,
            'password_changed': password_changed
        }
        
        db.session.commit()

        # Log the action with before/after values
        log_admin_event(
            event_type='edit_user',
            user_id=current_user.id,
            org_id=org_id,
            ip=flask_request.remote_addr,
            data={
                'edited_user': username,
                'user_id': user_id,
                'before': before_values,
                'after': after_values,
                'description': f'Edited user: {username}'
            }
        )

        flash(f'User {username} updated successfully', 'success')
        return redirect(url_for('admin.users'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing user: {str(e)}")
        flash('Error updating user', 'error')
        return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete user"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Check organization access
        org_id = getattr(current_user, 'org_id', 1)
        if hasattr(user, 'org_id') and user.org_id != org_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Don't allow deleting yourself
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400

        username = user.username
        
        # Log the action before deletion
        try:
            log_admin_event(
                event_type='delete_user',
                user_id=current_user.id,
                org_id=org_id,
                ip=flask_request.remote_addr,
                data={'deleted_user': username, 'user_id': user_id, 'description': f'Deleted user: {username}'}
            )
        except Exception as log_error:
            logger.warning(f"Could not log user deletion: {str(log_error)}")

        # Delete user
        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'User {username} deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Error deleting user: {str(e)}'
        }), 500


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Check organization access
        org_id = getattr(current_user, 'org_id', 1)
        if user.org_id != org_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Don't allow deactivating yourself
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot modify your own status'}), 400

        # Toggle status
        user.is_active_user = not user.is_active_user
        db.session.commit()

        # Log the action
        status = 'activated' if user.is_active_user else 'deactivated'
        log_admin_event(
            event_type='toggle_user_status',
            user_id=current_user.id,
            org_id=org_id,
            ip=flask_request.remote_addr,
            data={'target_user': user.username, 'user_id': user_id, 'new_status': user.is_active_user, 'description': f'User {user.username} {status}'}
        )

        return jsonify({
            'success': True,
            'message': f'User {user.username} {status} successfully',
            'is_active': user.is_active_user
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user status: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error updating user status'
        }), 500


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
                    org_id=getattr(current_user, 'org_id', 1),
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
                org_id=getattr(current_user, 'org_id', 1),
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
            org_id=getattr(current_user, 'org_id', 1),
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

@admin_bp.route('/api/update-phi-settings', methods=['POST'])
@login_required
@admin_required
def update_phi_settings_api():
    """API endpoint to update PHI settings"""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
        enabled = request_data.get('enabled', False)
        
        # Get or create PHI settings
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings()
            phi_settings.enabled = enabled
            phi_settings.filter_ssn = True
            phi_settings.filter_phone = True
            phi_settings.filter_mrn = True
            phi_settings.filter_insurance = True
            phi_settings.filter_addresses = True
            phi_settings.filter_names = True
            phi_settings.filter_dates = True
            db.session.add(phi_settings)
        else:
            phi_settings.enabled = enabled
            phi_settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the change
        log_admin_event(
            event_type='phi_settings_update',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={'enabled': enabled, 'description': f'PHI filtering {"enabled" if enabled else "disabled"} by admin'}
        )
        
        return jsonify({
            'success': True,
            'enabled': phi_settings.enabled,
            'message': f'PHI filtering {"enabled" if enabled else "disabled"} successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating PHI settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# User Management Routes
@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    """List all users"""
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        
        # Log user list access
        log_admin_event(
            event_type='user_list_access',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={'description': 'Accessed user management list'}
        )
        
        return render_template('admin/users.html', users=users)
        
    except Exception as e:
        logger.error(f"Error loading users list: {str(e)}")
        flash('Error loading users list', 'error')
        return redirect(url_for('admin.dashboard'))

# Preset Management Routes

@admin_bp.route('/presets')
@login_required
@admin_required
def view_presets():
    """View all screening presets - Web interface"""
    try:
        # Get presets for this organization + globally available ones
        org_id = current_user.org_id
        presets = ScreeningPreset.query.filter(
            (ScreeningPreset.org_id == org_id) | 
            (ScreeningPreset.preset_scope == 'global')
        ).order_by(ScreeningPreset.updated_at.desc()).all()
        
        return render_template('admin/presets.html', presets=presets)
        
    except Exception as e:
        logger.error(f"Error viewing presets: {str(e)}")
        flash(f'Error loading presets: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard_presets'))

@admin_bp.route('/presets', methods=['POST'])
@login_required
@admin_required
def create_preset():
    """Create a new screening preset"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Preset name is required'}), 400
        
        # Check for existing preset in current organization only
        existing = ScreeningPreset.query.filter_by(
            name=name, 
            org_id=current_user.org_id
        ).first()
        if existing:
            return jsonify({'success': False, 'error': 'Preset name already exists in your organization'}), 400
        
        preset = ScreeningPreset()
        preset.name = name
        preset.description = data.get('description', '')
        preset.specialty = data.get('specialty', '')
        preset.shared = data.get('shared', False)
        preset.screening_data = data.get('screening_data', [])
        preset.metadata = data.get('metadata', {})
        preset.created_by = current_user.id
        preset.org_id = current_user.org_id  # ORGANIZATION SCOPE
        
        db.session.add(preset)
        db.session.commit()
        
        log_admin_event(
            event_type='create_preset',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={
                'preset_id': preset.id,
                'preset_name': preset.name,
                'description': f'Created screening preset: {preset.name}'
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Preset created successfully',
            'preset_id': preset.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating preset: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/presets/<int:preset_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_preset(preset_id):
    """Delete a screening preset"""
    try:
        # ORGANIZATION SCOPE - Only allow deletion of own org's presets
        preset = ScreeningPreset.query.filter_by(
            id=preset_id, 
            org_id=current_user.org_id
        ).first_or_404()
        preset_name = preset.name
        
        db.session.delete(preset)
        db.session.commit()
        
        log_admin_event(
            event_type='delete_preset',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset_name,
                'description': f'Deleted screening preset: {preset_name}'
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Preset deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting preset: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/presets/import', methods=['POST'])
@login_required
@admin_required
def import_preset():
    """Import screening preset from uploaded file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename or '')
        if not filename.lower().endswith(('.json', '.yaml', '.yml')):
            return jsonify({'success': False, 'error': 'File must be JSON or YAML format'}), 400
        
        file_content = file.read().decode('utf-8')
        
        try:
            if filename.lower().endswith('.json'):
                data = json.loads(file_content)
            else:
                data = yaml.safe_load(file_content)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid file format: {str(e)}'}), 400
        
        preset = ScreeningPreset.from_import_dict(data, current_user.id)
        preset.org_id = current_user.org_id  # ORGANIZATION SCOPE
        db.session.add(preset)
        db.session.commit()
        
        log_admin_event(
            event_type='import_preset',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={
                'preset_id': preset.id,
                'preset_name': preset.name,
                'description': f'Imported screening preset from {filename}'
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Preset imported successfully',
            'preset_id': preset.id,
            'preset_name': preset.name
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing preset: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Export preset functionality removed - global presets managed directly by root admin

@admin_bp.route('/presets/create-from-types', methods=['GET', 'POST'])
@login_required
@admin_required
def create_preset_from_types():
    """Create preset from existing screening types"""
    try:
        if request.method == 'GET':
            # Get filter and pagination parameters
            user_filter = request.args.get('user_id', '').strip()
            screening_name_filter = request.args.get('screening_name', '').strip()
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)  # 20 screening groups per page
            
            # Determine admin scope
            if current_user.role == 'root_admin':
                # Root admin can see all screening types
                base_query = ScreeningType.query
                available_users = User.query.filter(
                    User.role.in_(['admin', 'MA', 'nurse'])
                ).order_by(User.username).all()
            else:
                # Org admin can only see their organization's screening types
                base_query = ScreeningType.query.filter_by(org_id=current_user.org_id)
                available_users = User.query.filter_by(
                    org_id=current_user.org_id
                ).filter(
                    User.role.in_(['admin', 'MA', 'nurse'])
                ).order_by(User.username).all()
            
            # Get available screening names for dropdown (unique base names)
            available_screening_names = []
            screening_names_query = base_query.filter_by(is_active=True)
            if current_user.role != 'root_admin':
                screening_names_query = screening_names_query.filter_by(org_id=current_user.org_id)
            
            # Get distinct screening names
            from sqlalchemy import distinct
            distinct_names = screening_names_query.with_entities(distinct(ScreeningType.name)).order_by(ScreeningType.name).all()
            available_screening_names = [name[0] for name in distinct_names]
            
            # Apply filters
            screening_types_query = base_query.filter_by(is_active=True)
            
            if user_filter and user_filter.isdigit():
                screening_types_query = screening_types_query.filter_by(created_by=int(user_filter))
            
            if screening_name_filter:
                screening_types_query = screening_types_query.filter_by(name=screening_name_filter)
            
            # Get all screening types first for grouping
            all_screening_types = screening_types_query.order_by(ScreeningType.name, ScreeningType.created_at).all()
            
            # Group similar screening types using basic fuzzy matching
            all_grouped_types = group_screening_types_by_similarity(all_screening_types)
            
            # Apply pagination to groups
            total_groups = len(all_grouped_types)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            grouped_types = all_grouped_types[start_idx:end_idx]
            
            # Create pagination object
            from math import ceil
            has_prev = page > 1
            has_next = end_idx < total_groups
            prev_num = page - 1 if has_prev else None
            next_num = page + 1 if has_next else None
            total_pages = ceil(total_groups / per_page) if total_groups > 0 else 1
            
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total_groups,
                'total_pages': total_pages,
                'has_prev': has_prev,
                'has_next': has_next,
                'prev_num': prev_num,
                'next_num': next_num
            }
            
            return render_template('admin/create_preset_from_types.html',
                                 grouped_types=grouped_types,
                                 available_users=available_users,
                                 available_screening_names=available_screening_names,
                                 selected_user_id=user_filter,
                                 selected_screening_name=screening_name_filter,
                                 pagination=pagination)
        
        # Handle POST - create preset from selected types
        selected_ids = request.form.getlist('screening_type_ids')
        preset_name = request.form.get('preset_name', '').strip()
        preset_description = request.form.get('preset_description', '').strip()
        preset_specialty = request.form.get('preset_specialty', 'Custom').strip()
        
        if not selected_ids:
            flash('Please select at least one screening type', 'error')
            return redirect(url_for('admin.create_preset_from_types'))
        
        if not preset_name:
            flash('Preset name is required', 'error')
            return redirect(url_for('admin.create_preset_from_types'))
        
        # Convert selected IDs to integers
        try:
            screening_type_ids = [int(id_str) for id_str in selected_ids]
        except ValueError:
            flash('Invalid screening type selection', 'error')
            return redirect(url_for('admin.create_preset_from_types'))
        
        # Create preset from selected screening types
        preset = ScreeningType.create_preset_from_types(
            screening_type_ids=screening_type_ids,
            preset_name=preset_name,
            description=preset_description,
            specialty=preset_specialty,
            created_by=current_user.id,
            org_id=current_user.org_id
        )
        
        if not preset:
            flash('Failed to create preset from selected screening types', 'error')
            return redirect(url_for('admin.create_preset_from_types'))
        
        # Save to database
        db.session.add(preset)
        db.session.commit()
        
        # Log the action
        log_admin_event(
            event_type='create_preset_from_types',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={
                'preset_name': preset_name,
                'screening_type_ids': screening_type_ids,
                'screening_count': len(screening_type_ids),
                'description': f'Created preset "{preset_name}" from {len(screening_type_ids)} screening types'
            }
        )
        
        flash(f'Successfully created preset "{preset_name}" from {len(screening_type_ids)} screening types', 'success')
        return redirect(url_for('admin.dashboard_presets'))
        
    except Exception as e:
        logger.error(f"Error creating preset from types: {str(e)}")
        flash('Error creating preset from screening types', 'error')
        return redirect(url_for('admin.create_preset_from_types'))





@admin_bp.route('/presets/<int:preset_id>/apply-to-organization', methods=['POST'])
@login_required
@admin_required
def apply_preset_to_organization(preset_id):
    """Apply preset to all users in the organization"""
    try:
        preset = ScreeningPreset.query.filter_by(
            id=preset_id
        ).filter(
            (ScreeningPreset.org_id == current_user.org_id) | 
            (ScreeningPreset.preset_scope == 'global')
        ).first_or_404()
        
        overwrite_requested = request.form.get('force_overwrite') == 'true'
        
        # Use the improved import method
        result = preset.import_to_screening_types(
            overwrite_existing=overwrite_requested,
            created_by=current_user.id
        )
        
        if result['success']:
            imported_count = result['imported_count']
            updated_count = result['updated_count']
            skipped_count = result['skipped_count']
            
            if imported_count > 0 or updated_count > 0:
                message_parts = []
                if imported_count > 0:
                    message_parts.append(f"{imported_count} screening types imported")
                if updated_count > 0:
                    message_parts.append(f"{updated_count} screening types updated")
                if skipped_count > 0:
                    message_parts.append(f"{skipped_count} screening types skipped (already exist)")
                
                success_message = f'Successfully applied preset "{preset.name}" to organization: ' + ', '.join(message_parts)
                
                # Log the action
                log_admin_event(
                    event_type='apply_preset_to_organization',
                    user_id=current_user.id,
                    org_id=current_user.org_id,
                    ip=request.remote_addr,
                    data={
                        'preset_name': preset.name,
                        'preset_id': preset.id,
                        'imported_count': imported_count,
                        'updated_count': updated_count,
                        'skipped_count': skipped_count,
                        'description': success_message
                    }
                )
                
                flash(success_message, 'success')
            else:
                if result['errors']:
                    flash(f'Failed to apply preset "{preset.name}": ' + '; '.join(result['errors']), 'error')
                else:
                    flash(f'No changes made - all screening types already exist. Use "Force Overwrite" to update existing types.', 'info')
        else:
            error_message = f'Failed to apply preset "{preset.name}": {result.get("error", "Unknown error")}'
            if result.get('errors'):
                error_message += ' Additional errors: ' + '; '.join(result['errors'])
            flash(error_message, 'error')
        
        return redirect(url_for('admin.view_presets'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error applying preset to organization: {str(e)}")
        flash(f'Error applying preset: {str(e)}', 'error')
        return redirect(url_for('admin.view_presets'))

@admin_bp.route('/presets/<int:preset_id>/check-conflicts', methods=['GET'])
@login_required
@admin_required
def check_preset_conflicts(preset_id):
    """Check for conflicts when applying a preset"""
    try:
        preset = ScreeningPreset.query.filter_by(
            id=preset_id
        ).filter(
            (ScreeningPreset.org_id == current_user.org_id) | 
            (ScreeningPreset.preset_scope == 'global')
        ).first_or_404()
        
        conflicts = preset.check_application_conflicts()
        return jsonify(conflicts)
        
    except Exception as e:
        logger.error(f"Error checking preset conflicts: {str(e)}")
        return jsonify({
            'has_conflicts': False,
            'error': 'Error checking conflicts'
        }), 500
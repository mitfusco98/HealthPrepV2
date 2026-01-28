# Applying the changes to correct the import errors and references to non-existent classes.
"""
Admin dashboard routes and functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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

from models import User, AdminLog, PHIFilterSettings, log_admin_event, Document, ScreeningPreset, ScreeningType, Provider, UserProviderAssignment, Organization, FHIRDocument
from app import db
from services.stripe_service import StripeService
from flask import request as flask_request
from admin.analytics import HealthPrepAnalytics
from admin.config import AdminConfig
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter

logger = logging.getLogger(__name__)


def _get_oversized_document_stats():
    """
    Get statistics about oversized documents that were skipped due to cost control.
    
    Returns summary of documents exceeding MAX_DOCUMENT_PAGES limit, useful for 
    monitoring cost savings and identifying if the limit is too restrictive.
    """
    try:
        from sqlalchemy import func
        
        # Count documents skipped due to size
        total_skipped = FHIRDocument.query.filter(
            FHIRDocument.skipped_oversized == True
        ).count()
        
        # Get page count distribution for skipped documents
        page_stats = db.session.query(
            func.min(FHIRDocument.page_count).label('min_pages'),
            func.max(FHIRDocument.page_count).label('max_pages'),
            func.avg(FHIRDocument.page_count).label('avg_pages')
        ).filter(
            FHIRDocument.skipped_oversized == True,
            FHIRDocument.page_count.isnot(None)
        ).first()
        
        # Recent skipped documents (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_skipped = FHIRDocument.query.filter(
            FHIRDocument.skipped_oversized == True,
            FHIRDocument.updated_at >= week_ago
        ).count()
        
        return {
            'total_skipped': total_skipped,
            'recent_skipped_7d': recent_skipped,
            'page_count_stats': {
                'min': page_stats.min_pages if page_stats else None,
                'max': page_stats.max_pages if page_stats else None,
                'avg': round(float(page_stats.avg_pages), 1) if page_stats and page_stats.avg_pages else None
            } if page_stats else None
        }
    except Exception as e:
        logger.warning(f"Error getting oversized document stats: {e}")
        return {
            'total_skipped': 0,
            'recent_skipped_7d': 0,
            'page_count_stats': None,
            'error': str(e)
        }

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
    """Group screening types by similarity with enhanced base/variant detection"""
    groups = {}
    processed = set()
    
    # First pass: Group by exact base name matching (for dash-separated variants)
    base_groups = {}
    standalone_types = []
    
    for st in screening_types:
        if ' - ' in st.name:
            # This is likely a variant
            base_name = st.name.split(' - ')[0].strip()
            if base_name not in base_groups:
                base_groups[base_name] = []
            base_groups[base_name].append(st)
        else:
            # Check if this could be a base type for existing variants
            matching_variants = [v for variants in base_groups.values() for v in variants if v.name.startswith(st.name + ' - ')]
            if matching_variants:
                if st.name not in base_groups:
                    base_groups[st.name] = []
                base_groups[st.name].append(st)
            else:
                standalone_types.append(st)
    
    # Create groups from base name groups
    for base_name, variants in base_groups.items():
        group_key = f"group_{len(groups)}"
        
        # Find the actual base type (without dash) or use first variant as representative
        base_type = next((v for v in variants if v.name == base_name), variants[0])
        
        # Separate base types from variants and categorize by screening category
        base_types = [v for v in variants if v.name == base_name]
        variant_types = [v for v in variants if v.name != base_name]
        
        # Sort variants by category: general first, then conditional/risk_based
        variant_types.sort(key=lambda x: (
            getattr(x, 'screening_category', 'general') != 'general',
            x.name
        ))
        
        all_variants = base_types + variant_types
        
        groups[group_key] = {
            'base_name': base_name,
            'normalized_name': normalize_screening_name(base_name),
            'variants': all_variants,
            'authors': set(),
            'organizations': set(),
            'has_base_type': len(base_types) > 0,
            'has_conditional_variants': any(getattr(v, 'screening_category', 'general') == 'conditional' for v in variant_types),
            'has_general_variants': any(getattr(v, 'screening_category', 'general') == 'general' for v in variant_types)
        }
        
        # Collect authors and organizations
        for variant in all_variants:
            if hasattr(variant, 'created_by_user') and variant.created_by_user:
                groups[group_key]['authors'].add(variant.created_by_user.username)
            else:
                groups[group_key]['authors'].add('Unknown')
                
            if hasattr(variant, 'organization') and variant.organization:
                groups[group_key]['organizations'].add(variant.organization.name)
        
        # Mark all as processed
        for variant in all_variants:
            processed.add(variant.id)
    
    # Second pass: Group remaining standalone types using fuzzy matching
    for st in standalone_types:
        if st.id in processed:
            continue
        
        # Create new group with this screening type as the base
        normalized_name = normalize_screening_name(st.name)
        group_key = f"group_{len(groups)}"
        
        groups[group_key] = {
            'base_name': st.name,
            'normalized_name': normalized_name,
            'variants': [st],
            'authors': set(),
            'organizations': set(),
            'has_base_type': True,
            'has_conditional_variants': getattr(st, 'screening_category', 'general') == 'conditional',
            'has_general_variants': getattr(st, 'screening_category', 'general') == 'general'
        }
        
        if hasattr(st, 'created_by_user') and st.created_by_user:
            groups[group_key]['authors'].add(st.created_by_user.username)
        else:
            groups[group_key]['authors'].add('Unknown')
            
        if hasattr(st, 'organization') and st.organization:
            groups[group_key]['organizations'].add(st.organization.name)
        
        processed.add(st.id)
        
        # Find similar screening types using fuzzy matching
        for other_st in standalone_types:
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
                
                if hasattr(other_st, 'created_by_user') and other_st.created_by_user:
                    groups[group_key]['authors'].add(other_st.created_by_user.username)
                else:
                    groups[group_key]['authors'].add('Unknown')
                    
                if hasattr(other_st, 'organization') and other_st.organization:
                    groups[group_key]['organizations'].add(other_st.organization.name)
                
                # Update group flags
                other_category = getattr(other_st, 'screening_category', 'general')
                if other_category == 'conditional':
                    groups[group_key]['has_conditional_variants'] = True
                else:
                    groups[group_key]['has_general_variants'] = True
                
                processed.add(other_st.id)
    
    # Finalize all groups
    for group in groups.values():
        # Sort variants: base types first, then general, then conditional
        group['variants'].sort(key=lambda x: (
            ' - ' in x.name,  # Base types first (no dash)
            getattr(x, 'screening_category', 'general') == 'conditional',  # General before conditional
            x.name
        ))
        
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
    response = make_response(redirect(url_for('admin.dashboard_logs')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@admin_bp.route('/payment-setup')
@login_required
@admin_required
def payment_setup():
    """Create Stripe Checkout session for payment setup"""
    from models import Organization
    from services.stripe_service import StripeService
    
    try:
        # Get current organization
        org = Organization.query.get(current_user.org_id)
        
        if not org:
            flash('Organization not found', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # If already has payment info, redirect to billing portal
        if org.stripe_customer_id:
            return redirect(url_for('admin.billing_portal'))
        
        # Create Stripe Checkout session
        success_url = url_for('admin.payment_success', _external=True)
        cancel_url = url_for('admin.dashboard', _external=True)
        
        checkout_url = StripeService.create_checkout_session(
            org,
            success_url,
            cancel_url
        )
        
        if checkout_url:
            return redirect(checkout_url)
        else:
            flash('Unable to create payment session. Please try again.', 'error')
            return redirect(url_for('admin.dashboard'))
            
    except Exception as e:
        logger.error(f"Error creating payment setup session: {str(e)}")
        flash('Error setting up payment', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/payment-success')
@login_required
@admin_required
def payment_success():
    """Handle successful payment setup"""
    flash('Payment information added successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/billing-portal')
@login_required
@admin_required
def billing_portal():
    """Redirect to Stripe Customer Portal for billing management or payment setup"""
    from models import Organization
    from services.stripe_service import StripeService
    
    try:
        # Get current organization
        org = Organization.query.get(current_user.org_id)
        
        if not org:
            flash('Organization not found', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # Check if this is a manually-created organization without Stripe setup
        # Allow manual orgs to set up payment if they don't have a customer ID yet
        if org.creation_method == 'manual' and not org.stripe_customer_id:
            return redirect(url_for('admin.payment_setup'))
        
        # If no payment method, redirect to payment setup
        if not org.stripe_customer_id:
            return redirect(url_for('admin.payment_setup'))
        
        # Create billing portal session
        return_url = url_for('admin.dashboard', _external=True)
        portal_url = StripeService.create_billing_portal_session(
            org.stripe_customer_id,
            return_url
        )
        
        if portal_url:
            return redirect(portal_url)
        else:
            flash('Unable to access billing portal. Please contact support.', 'error')
            return redirect(url_for('admin.dashboard'))
            
    except Exception as e:
        logger.error(f"Error accessing billing portal: {str(e)}")
        flash('Error accessing billing portal', 'error')
        return redirect(url_for('admin.dashboard'))

def get_dashboard_data():
    """Helper function to get common dashboard data"""
    analytics = HealthPrepAnalytics()
    
    # Get dashboard statistics
    dashboard_stats = analytics.get_roi_metrics()
    
    # Get recent activity - ORGANIZATION SCOPED
    # Exclude system logs (org_id=0) and only show current org's logs
    recent_logs_raw = AdminLog.query.filter(
        AdminLog.org_id == current_user.org_id,
        AdminLog.org_id > 0  # Exclude system org logs
    ).order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    # Convert timestamps to org's local timezone
    org_timezone = getattr(current_user.organization, 'timezone', None) if current_user.organization else None
    try:
        tz = ZoneInfo(org_timezone) if org_timezone else ZoneInfo('UTC')
    except Exception:
        tz = ZoneInfo('UTC')
    
    recent_logs = []
    for log in recent_logs_raw:
        if log.timestamp:
            # Handle both naive (assume UTC) and aware timestamps
            if log.timestamp.tzinfo is None:
                utc_ts = log.timestamp.replace(tzinfo=ZoneInfo('UTC'))
            else:
                utc_ts = log.timestamp.astimezone(ZoneInfo('UTC'))
            local_ts = utc_ts.astimezone(tz)
        else:
            local_ts = None
        recent_logs.append({
            'log': log,
            'local_timestamp': local_ts
        })
    
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
        
        # Count documents that have been PHI filtered
        phi_filtered_docs = Document.query.filter(
            Document.phi_filtered == True,
            Document.org_id == current_user.org_id
        ).count()
    except Exception as e:
        logger.warning(f"Could not count processed documents: {str(e)}")
        documents_processed = 0
        phi_filtered_docs = 0
        
    # Get actual redaction statistics from admin_logs
    try:
        from sqlalchemy import Text
        
        # Count document processing events with PHI filtering
        log_phi_count = AdminLog.query.filter(
            AdminLog.org_id == current_user.org_id,
            AdminLog.event_type.in_(['document_processing_complete', 'phi_filtered'])
        ).count()
        
        # Count successful document processing events (where PHI was filtered)
        # Query JSON data field using text cast for compatibility
        successful_processing = db.session.query(AdminLog).filter(
            AdminLog.org_id == current_user.org_id,
            AdminLog.event_type == 'document_processing_complete',
            AdminLog.data.cast(Text).contains('"phi_filtered": true')
        ).count()
    except Exception as e:
        logger.warning(f"Could not query log-based PHI stats: {str(e)}")
        log_phi_count = 0
        successful_processing = 0
    
    # Document processing statistics (actual counts from logs and documents)
    phi_stats = {
        'documents_processed': int(documents_processed) if documents_processed else 0,
        'phi_filtered_docs': phi_filtered_docs,
        'processing_rate': round((phi_filtered_docs / documents_processed * 100), 1) if documents_processed > 0 else 0,
        'log_events_count': log_phi_count,
        'successful_phi_filter_count': successful_processing,
    }
    
    # PHI processing summary - based on actual data (no estimated breakdowns)
    phi_breakdown = {
        'total_protected': phi_filtered_docs,
        'ocr_processed': documents_processed,
        'pending': max(0, documents_processed - phi_filtered_docs),
        'log_events': log_phi_count,
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
        # Fix: Use same query as root admin to show all global presets - removed limit(5)
        recent_presets = ScreeningPreset.query.filter(
            (ScreeningPreset.org_id == current_user.org_id) | 
            (ScreeningPreset.preset_scope == 'global') |
            (ScreeningPreset.shared == True)
        ).order_by(desc(ScreeningPreset.updated_at)).all()  # type: ignore
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

@admin_bp.route('/dashboard/analytics')
@login_required
@admin_required
def dashboard_analytics():
    """Admin dashboard - Customer Analytics tab"""
    try:
        data = get_dashboard_data()
        data['active_tab'] = 'analytics'
        return render_template('admin/analytics.html', **data)
    except Exception as e:
        import traceback
        logger.error(f"Error in dashboard analytics: {str(e)}\n{traceback.format_exc()}")
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
        # Exclude system logs (org_id=0) and only show current org's logs
        # Include document_processing_complete events (consolidated audit trail)
        query = AdminLog.query.filter(
            AdminLog.org_id == current_user.org_id,
            AdminLog.org_id > 0  # Exclude system org logs
        )
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

        # Get organization timezone for timestamp display
        org = Organization.query.get(current_user.org_id) if current_user.org_id else None
        org_timezone = getattr(org, 'timezone', None) or 'UTC'
        
        # Convert log timestamps to org's local timezone
        try:
            tz = ZoneInfo(org_timezone)
        except Exception:
            tz = ZoneInfo('UTC')
        
        # Create log entries with local timestamps
        logs_with_local_time = []
        for log in logs_pagination.items:
            # Convert UTC timestamp to local
            if log.timestamp:
                # Handle both naive (assume UTC) and aware timestamps
                if log.timestamp.tzinfo is None:
                    utc_ts = log.timestamp.replace(tzinfo=ZoneInfo('UTC'))
                else:
                    utc_ts = log.timestamp.astimezone(ZoneInfo('UTC'))
                local_ts = utc_ts.astimezone(tz)
            else:
                local_ts = None
            logs_with_local_time.append({
                'log': log,
                'local_timestamp': local_ts
            })

        # Get filter options
        # Apply organization filtering for multi-tenancy
        if hasattr(current_user, 'org_id'):
            users = User.query.filter_by(org_id=current_user.org_id).all()
        else:
            users = User.query.all()
        event_types = db.session.query(AdminLog.event_type).distinct().all()
        event_types = [event.event_type for event in event_types if event.event_type]
        
        # Event type display name mapping - consolidates legacy names
        event_type_display = {
            # Document Processing (consolidated from PHI filtering)
            'document_processing_complete': 'Document Processing',
            'document_processing_started': 'Document Processing',
            'document_processed': 'Document Processing',
            'document_processing_failed': 'Document Processing Failed',
            'phi_filtered': 'Document Processing',
            'phi_redacted': 'Document Processing',
            'phi_filter_failed': 'PHI Redaction Failed',
            'ocr_completed': 'OCR Processing',
            'file_secure_deleted': 'Secure File Deletion',
            # User Management
            'login': 'User Login',
            'logout': 'User Logout',
            'login_failed': 'Login Failed',
            'create_user': 'User Created',
            'edit_user': 'User Modified',
            'delete_user': 'User Deleted',
            'password_change': 'Password Changed',
            # Security Events
            'account_lockout': 'Account Lockout',
            'brute_force_detected': 'Brute Force Detected',
            'security_lockout': 'Security Lockout',
            'password_spray_detected': 'Password Spray Detected',
            'concurrent_session': 'Concurrent Session',
            'unusual_login_hours': 'Unusual Login Hours',
            'document_integrity_violation': 'Integrity Violation',
            # Admin Actions
            'admin_action': 'Admin Action',
            'settings_updated': 'Settings Updated',
            'epic_connection': 'Epic Connection',
            'epic_sync': 'Epic Sync',
            'prep_sheet_generated': 'Prep Sheet Generated',
        }

        return render_template('admin/logs.html',
                             logs=logs_with_local_time,
                             pagination=logs_pagination,
                             users=users,
                             event_types=event_types,
                             event_type_display=event_type_display,
                             filters=filters,
                             org_timezone=org_timezone)

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
    """Export admin logs as CSV with PHI redaction for compliance"""
    try:
        import csv
        from io import StringIO
        import hashlib
        
        def sanitize_csv_cell(value):
            """Prevent CSV formula injection by prefixing dangerous characters"""
            if value and isinstance(value, str) and value[0] in ('=', '+', '-', '@', '\t', '\r'):
                return "'" + value
            return value
        
        # Get export parameters
        days = request.args.get('days', 30, type=int)
        event_type = request.args.get('event_type', '')
        include_phi = request.args.get('include_phi', 'false').lower() == 'true'

        # Export logs directly from AdminLog model - ORGANIZATION SCOPED
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = AdminLog.query.filter(
            AdminLog.timestamp >= start_date,
            AdminLog.org_id == current_user.org_id
        )
        
        if event_type:
            query = query.filter(AdminLog.event_type == event_type)
        
        logs = query.order_by(AdminLog.timestamp.desc()).all()
        
        # Create CSV in memory
        si = StringIO()
        writer = csv.writer(si)
        
        # Write header with integrity hash column
        writer.writerow([
            'Timestamp',
            'Event Type',
            'User ID',
            'Username',
            'IP Address',
            'Patient ID (Redacted)' if not include_phi else 'Patient ID',
            'Resource Type',
            'Resource ID',
            'Action Details',
            'Data (PHI Stripped)',
            'Row Hash'  # Integrity verification
        ])
        
        # PHI fields to redact from data
        phi_fields = {'patient_name', 'patient_email', 'patient_phone', 'patient_address', 
                      'patient_dob', 'date_of_birth', 'ssn', 'social_security', 'email', 
                      'phone', 'address', 'name', 'first_name', 'last_name'}
        
        def redact_phi_from_data(data_dict):
            """Recursively redact PHI fields from data dictionary"""
            if not isinstance(data_dict, dict):
                return data_dict
            
            redacted = {}
            for key, value in data_dict.items():
                if key.lower() in phi_fields:
                    redacted[key] = '[REDACTED]'
                elif isinstance(value, dict):
                    redacted[key] = redact_phi_from_data(value)
                elif isinstance(value, list):
                    redacted[key] = [redact_phi_from_data(item) if isinstance(item, dict) else item for item in value]
                else:
                    redacted[key] = value
            return redacted
        
        def compute_row_hash(row_data):
            """Compute SHA-256 hash for row integrity verification"""
            row_str = '|'.join(str(field) for field in row_data)
            return hashlib.sha256(row_str.encode()).hexdigest()[:16]
        
        # Write data rows
        for log in logs:
            # Redact patient ID if PHI not included
            patient_id_display = log.patient_id if include_phi else (f'P{hash(log.patient_id) % 10000:04d}' if log.patient_id else '')
            
            # Redact PHI from data field
            data_display = ''
            if log.data:
                if include_phi:
                    data_display = str(log.data)
                else:
                    redacted_data = redact_phi_from_data(log.data if isinstance(log.data, dict) else {})
                    data_display = str(redacted_data)
            
            row_data = [
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.event_type or '',
                str(log.user_id) if log.user_id else '',
                log.user.username if log.user else 'System',
                log.ip_address or '',
                str(patient_id_display),
                log.resource_type or '',
                str(log.resource_id) if log.resource_id else '',
                log.action_details or '',
                data_display
            ]
            
            # Sanitize all cells to prevent formula injection BEFORE computing hash
            sanitized_row = [sanitize_csv_cell(str(cell)) for cell in row_data]
            
            # Add row hash for integrity verification (computed on sanitized data)
            row_hash = compute_row_hash(sanitized_row)
            sanitized_row.append(row_hash)
            
            writer.writerow(sanitized_row)
        
        # Prepare response
        output = si.getvalue()
        si.close()
        
        # Generate filename with timestamp and PHI indicator
        phi_marker = 'with_phi' if include_phi else 'phi_redacted'
        filename = f"admin_logs_{phi_marker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Log the export for audit trail
        log_admin_event(
            event_type='audit_log_export',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={
                'days_exported': days,
                'event_type_filter': event_type or 'all',
                'include_phi': include_phi,
                'record_count': len(logs),
                'description': f'Audit log exported by {current_user.username} ({phi_marker})'
            }
        )
        
        response = make_response(output)
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        return response

    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        flash('Error exporting logs', 'error')
        return redirect(url_for('admin.logs'))

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


@admin_bp.route('/queue-monitor')
@login_required
@admin_required
def queue_monitor():
    """
    Queue monitoring dashboard for OCR processing.
    Shows queue depth, worker status, and processing metrics for scaling decisions.
    """
    try:
        from redis import Redis
        from rq import Queue
        from rq.worker import Worker
        from rq.job import Job
        import os
        
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        
        try:
            conn = Redis.from_url(redis_url)
            conn.ping()
            redis_connected = True
        except Exception as e:
            logger.warning(f"Redis not available: {str(e)}")
            redis_connected = False
            return render_template('admin/queue_monitor.html',
                                 redis_connected=False,
                                 error="Redis is not available. Queue monitoring requires Redis.")
        
        queue_names = ['fhir_priority', 'fhir_processing']
        queues_data = []
        
        for name in queue_names:
            queue = Queue(name, connection=conn)
            
            jobs_in_queue = []
            for job in queue.jobs[:10]:
                jobs_in_queue.append({
                    'id': job.id,
                    'func_name': job.func_name if hasattr(job, 'func_name') else 'unknown',
                    'enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
                    'status': job.get_status()
                })
            
            queues_data.append({
                'name': name,
                'count': queue.count,
                'failed_count': queue.failed_job_registry.count,
                'scheduled_count': queue.scheduled_job_registry.count,
                'started_count': queue.started_job_registry.count,
                'finished_count': queue.finished_job_registry.count,
                'jobs': jobs_in_queue
            })
        
        workers = Worker.all(connection=conn)
        workers_data = []
        for worker in workers:
            current_job = worker.get_current_job()
            workers_data.append({
                'name': worker.name,
                'state': worker.get_state(),
                'queues': [q.name for q in worker.queues],
                'current_job_id': current_job.id if current_job else None,
                'successful_job_count': worker.successful_job_count,
                'failed_job_count': worker.failed_job_count,
                'total_working_time': str(worker.total_working_time) if hasattr(worker, 'total_working_time') else 'N/A'
            })
        
        from ocr.processor import get_ocr_max_workers
        ocr_config = {
            'max_workers': get_ocr_max_workers(),
            'env_setting': os.environ.get('OCR_MAX_WORKERS', 'auto-detect')
        }
        
        return render_template('admin/queue_monitor.html',
                             redis_connected=True,
                             queues=queues_data,
                             workers=workers_data,
                             ocr_config=ocr_config)
        
    except Exception as e:
        logger.error(f"Error in queue monitor: {str(e)}")
        flash('Error loading queue monitor', 'error')
        return render_template('error/500.html'), 500


@admin_bp.route('/api/queue-status')
@login_required
@admin_required
def queue_status_api():
    """
    JSON API for queue status - useful for auto-scaling triggers and monitoring.
    """
    try:
        from redis import Redis
        from rq import Queue
        from rq.worker import Worker
        import os
        from datetime import datetime
        
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        
        try:
            conn = Redis.from_url(redis_url)
            conn.ping()
        except Exception:
            return jsonify({
                'error': 'Redis not available',
                'timestamp': datetime.utcnow().isoformat()
            }), 503
        
        queue_names = ['fhir_priority', 'fhir_processing']
        queues_status = {}
        total_pending = 0
        
        for name in queue_names:
            queue = Queue(name, connection=conn)
            count = queue.count
            total_pending += count
            queues_status[name] = {
                'pending': count,
                'failed': queue.failed_job_registry.count,
                'started': queue.started_job_registry.count
            }
        
        workers = Worker.all(connection=conn)
        active_workers = sum(1 for w in workers if w.get_state() == 'busy')
        idle_workers = sum(1 for w in workers if w.get_state() == 'idle')
        
        from ocr.processor import get_ocr_max_workers
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'queues': queues_status,
            'total_pending': total_pending,
            'workers': {
                'total': len(workers),
                'active': active_workers,
                'idle': idle_workers
            },
            'ocr_max_workers': get_ocr_max_workers(),
            'scaling_recommendation': 'scale_up' if total_pending > 50 and idle_workers == 0 else 'stable'
        })
        
    except Exception as e:
        logger.error(f"Error in queue status API: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/performance-metrics')
@login_required
@admin_required
def performance_metrics_api():
    """
    JSON API for comprehensive performance metrics.
    
    Returns system resource usage, throughput metrics, queue status,
    scaling recommendations, and cost control stats for capacity planning.
    """
    try:
        from utils.performance import PerformanceMonitor, get_ocr_max_workers_recommendation
        from ocr.document_processor import get_max_document_pages
        from datetime import datetime
        
        monitor = PerformanceMonitor()
        
        # Get cost control stats for oversized documents
        oversized_stats = _get_oversized_document_stats()
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': monitor.get_system_metrics(),
            'queue': monitor.get_queue_metrics(),
            'throughput': {
                '1min': monitor.get_throughput_metrics(60),
                '5min': monitor.get_throughput_metrics(300)
            },
            'scaling': monitor.get_scaling_recommendations(),
            'worker_recommendations': get_ocr_max_workers_recommendation(),
            'cost_control': {
                'max_document_pages': get_max_document_pages(),
                'env_setting': os.environ.get('MAX_DOCUMENT_PAGES', 'default (20)'),
                'oversized_documents': oversized_stats
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in performance metrics API: {str(e)}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@admin_bp.route('/api/performance-report')
@login_required
@admin_required
def performance_report_api():
    """
    JSON API for full performance report.
    
    Returns comprehensive performance data including historical metrics
    and SLA compliance analysis.
    """
    try:
        from utils.performance import PerformanceMonitor
        from datetime import datetime
        
        monitor = PerformanceMonitor()
        report = monitor.get_full_report()
        
        # Add SLA compliance summary
        throughput_1min = report.get('throughput_1min', {})
        avg_job_time = throughput_1min.get('avg_job_time', 0)
        
        report['sla_compliance'] = {
            'target_seconds': 10,
            'current_avg': avg_job_time,
            'meets_sla': avg_job_time <= 10 or throughput_1min.get('jobs_completed', 0) == 0,
            'status': 'healthy' if avg_job_time <= 10 else 'at_risk'
        }
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Error in performance report API: {str(e)}")
        return jsonify({'error': str(e)}), 500


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
        org_id = getattr(current_user, 'org_id', 1)
        if hasattr(current_user, 'org_id'):
            users = User.query.filter_by(org_id=current_user.org_id).order_by(User.username).all()
        else:
            users = User.query.order_by(User.username).all()
        
        # Get active providers for subuser assignment dropdown
        providers = Provider.query.filter_by(org_id=org_id, is_active=True).order_by(Provider.name).all()

        return render_template('admin/users.html', users=users, providers=providers)

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
    """Create new user with automated onboarding via email"""
    try:
        from services.email_service import EmailService
        from models import Organization
        import re
        import secrets
        
        email = request.form.get('email')
        role = request.form.get('role', 'nurse')
        admin_type = request.form.get('admin_type', 'business_admin')  # For admin role: 'provider' or 'business_admin'
        is_active = request.form.get('is_active') == 'on'
        provider_id = request.form.get('provider_id', type=int)  # For subusers (nurse/MA)

        # Validate input
        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('admin.users'))
        
        # Subusers (nurse/MA) MUST be assigned to exactly one provider
        # This prevents EMR sync conflicts, criteria conflicts, and refresh conflicts
        is_subuser = role in ['nurse', 'MA']
        if is_subuser and not provider_id:
            flash('Subusers (nurses/MAs) must be assigned to exactly one provider', 'error')
            return redirect(url_for('admin.users'))
        
        # Validate admin_type if role is admin
        if role == 'admin' and admin_type not in ('provider', 'business_admin'):
            admin_type = 'business_admin'  # Default to business_admin

        # Auto-generate username from email (part before @)
        username = email.split('@')[0].lower()
        # Replace common separators with dots for consistency
        username = re.sub(r'[._-]+', '.', username)
        
        # Get current user's organization
        org_id = getattr(current_user, 'org_id', 1)  # Default to org 1 if not set
        
        # Get organization name for email
        org = Organization.query.get(org_id)
        org_name = org.name if org else 'HealthPrep'
        
        # Validate provider exists and belongs to org (for subusers)
        if is_subuser:
            provider = Provider.query.filter_by(id=provider_id, org_id=org_id, is_active=True).first()
            if not provider:
                flash('Selected provider not found or inactive', 'error')
                return redirect(url_for('admin.users'))

        # Check if username already exists - if so, append a number
        base_username = username
        counter = 1
        while User.query.filter_by(username=username, org_id=org_id).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Check if email already exists within the same organization
        existing_email = User.query.filter_by(email=email, org_id=org_id).first()
        if existing_email:
            flash('Email already exists in this organization', 'error')
            return redirect(url_for('admin.users'))

        # Generate a secure random temporary password
        temp_password = secrets.token_urlsafe(16)

        # Create new user with temporary password flag
        new_user = User()
        new_user.username = username
        new_user.email = email
        new_user.role = role
        new_user.is_admin = (role == 'admin')  # Set is_admin based on role
        new_user.admin_type = admin_type if role == 'admin' else None  # Only set for admin users
        new_user.is_active_user = is_active
        new_user.org_id = org_id  # Assign to current user's organization
        new_user.set_password(temp_password)
        new_user.is_temp_password = True  # Flag for password reset on first login
        
        db.session.add(new_user)
        db.session.commit()

        # Provider assignment based on role
        if is_subuser:
            # Subusers get assigned to exactly ONE provider (selected in form)
            assignment = UserProviderAssignment(
                user_id=new_user.id,
                provider_id=provider_id,
                org_id=org_id,
                can_view_patients=True,
                can_edit_screenings=True,
                can_generate_prep_sheets=True,
                can_sync_epic=False  # Subusers cannot sync Epic
            )
            db.session.add(assignment)
        else:
            # Admins get assigned to ALL active providers in the organization
            org_providers = Provider.query.filter_by(org_id=org_id, is_active=True).all()
            for provider in org_providers:
                assignment = UserProviderAssignment(
                    user_id=new_user.id,
                    provider_id=provider.id,
                    org_id=org_id,
                    can_view_patients=True,
                    can_edit_screenings=True,
                    can_generate_prep_sheets=True,
                    can_sync_epic=(role == 'admin')
                )
                db.session.add(assignment)
        db.session.commit()

        # Log user creation immediately after commit (for HIPAA audit trail)
        created_values = {
            'username': new_user.username,
            'email': new_user.email,
            'role': new_user.role,
            'admin_type': new_user.admin_type,
            'is_admin': new_user.is_admin,
            'is_active_user': new_user.is_active_user,
            'org_id': new_user.org_id
        }
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

        # Send welcome email with temporary password
        try:
            email_sent = EmailService.send_welcome_email(new_user.email, new_user.username, temp_password, org_name)
            if email_sent:
                logger.info(f"Welcome email sent to {new_user.email}")
                flash(f'User {username} created successfully! A welcome email with password setup instructions has been sent to {email}.', 'success')
            else:
                logger.warning(f"Welcome email failed to send to {new_user.email} (returned False)")
                flash(f'User created successfully, but welcome email could not be sent. Please share credentials manually: Username: {new_user.username}, Password: {temp_password}', 'warning')
        except Exception as email_error:
            logger.error(f"Failed to send welcome email to {new_user.email}: {str(email_error)}")
            flash(f'User created successfully, but failed to send welcome email. Please share credentials manually: Username: {new_user.username}, Password: {temp_password}', 'warning')

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

        role = request.form.get('role')
        admin_type = request.form.get('admin_type', 'business_admin')  # For admin role
        # Note: is_active is no longer managed by org admins - removed from edit form

        # Validate input (email cannot be changed after account creation)
        if not role:
            flash('Role is required', 'error')
            return redirect(url_for('admin.users'))
        
        # Validate admin_type if role is admin
        if role == 'admin' and admin_type not in ('provider', 'business_admin'):
            admin_type = 'business_admin'

        # Capture before values for logging
        before_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'admin_type': user.admin_type,
            'is_admin': user.is_admin
        }
        
        # Role escalation prevention: nurses/MAs cannot be promoted to admin
        original_role = user.role
        if original_role in ('nurse', 'MA') and role == 'admin':
            flash('Nurses and Medical Assistants cannot be promoted to Administrator. The user must be deleted and re-registered.', 'error')
            return redirect(url_for('admin.users'))
        
        # For admin users, only allow admin_type changes (provider <-> business_admin)
        # Cannot change admin back to nurse/MA
        if original_role == 'admin' and role in ('nurse', 'MA'):
            flash('Administrators cannot be demoted to Nurse or Medical Assistant. The user must be deleted and re-registered.', 'error')
            return redirect(url_for('admin.users'))

        # Update user (username and email cannot be changed after account creation)
        user.role = role
        user.is_admin = (role == 'admin')
        user.admin_type = admin_type if role == 'admin' else None
        # Note: is_active_user is NOT updated here - managed by root admin only
        
        # Capture after values for logging
        after_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'admin_type': user.admin_type,
            'is_admin': user.is_admin
        }
        
        db.session.commit()

        # Log the action with before/after values
        username = user.username
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
        
        # Reassign any global presets created by this user to root admin
        # This ensures global presets persist when their creator is deleted
        from utils.seed_global_presets import reassign_user_global_presets
        from models import ScreeningPreset, User as UserModel
        root_admin = UserModel.query.filter_by(is_root_admin=True).first()
        if root_admin and root_admin.id != user.id:
            reassigned_count = reassign_user_global_presets(db, ScreeningPreset, user.id, root_admin.id)
            if reassigned_count > 0:
                logger.info(f"Reassigned {reassigned_count} global presets from user {user.id} to root admin before deletion")
        
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
    """Toggle user active status - DEPRECATED for org admins
    
    Org admins can no longer activate/deactivate users directly.
    - Security lockouts can only be cleared by root admin
    - User activation status is managed by root admin
    """
    return jsonify({
        'success': False, 
        'error': 'User activation/deactivation is restricted. Please contact your system administrator.'
    }), 403


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
    """API endpoint to update PHI filter type settings (PHI filtering is always enabled)"""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        # Get or create PHI settings - PHI filtering is always enabled
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings()
            phi_settings.enabled = True  # Always enabled
            phi_settings.filter_ssn = True
            phi_settings.filter_phone = True
            phi_settings.filter_mrn = True
            phi_settings.filter_insurance = True
            phi_settings.filter_addresses = True
            phi_settings.filter_names = True
            phi_settings.filter_dates = True
            db.session.add(phi_settings)
        
        # Update individual filter types if provided (but never allow disabling main filter)
        if 'filter_ssn' in request_data:
            phi_settings.filter_ssn = request_data['filter_ssn']
        if 'filter_phone' in request_data:
            phi_settings.filter_phone = request_data['filter_phone']
        if 'filter_mrn' in request_data:
            phi_settings.filter_mrn = request_data['filter_mrn']
        if 'filter_insurance' in request_data:
            phi_settings.filter_insurance = request_data['filter_insurance']
        if 'filter_addresses' in request_data:
            phi_settings.filter_addresses = request_data['filter_addresses']
        if 'filter_names' in request_data:
            phi_settings.filter_names = request_data['filter_names']
        if 'filter_dates' in request_data:
            phi_settings.filter_dates = request_data['filter_dates']
        
        phi_settings.enabled = True  # Always ensure enabled
        phi_settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the change
        log_admin_event(
            event_type='phi_settings_update',
            user_id=current_user.id,
            org_id=getattr(current_user, 'org_id', 1),
            ip=request.remote_addr,
            data={'description': 'PHI filter settings updated (PHI filtering always enabled for HIPAA compliance)'}
        )
        
        return jsonify({
            'success': True,
            'enabled': True,
            'message': 'PHI filter settings updated (PHI filtering is always enabled for HIPAA compliance)'
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
        ).order_by(desc(ScreeningPreset.updated_at)).all()  # type: ignore
        
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
        replace_entire_set = request.form.get('replace_entire_set') == 'true'
        
        # Check how many screening types currently exist in the organization
        existing_count = ScreeningType.query.filter_by(org_id=current_user.org_id).count()
        preset_count = len(preset.get_screening_types())
        
        # Use the improved import method with replacement option
        result = preset.import_to_screening_types(
            overwrite_existing=overwrite_requested,
            replace_entire_set=replace_entire_set,
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
                
                # Special message for empty organizations
                if existing_count == 0 and imported_count > 0:
                    success_message = f'Successfully populated your organization with {imported_count} screening types from preset "{preset.name}". Your organization is now ready to use!'
                
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
                        'was_empty_org': existing_count == 0,
                        'description': success_message
                    }
                )
                
                # Trigger screening refresh to create screening items for new/updated screening types
                logger.info(f"Preset {preset.name} applied - triggering screening refresh to create screening items")
                from services.screening_refresh_service import ScreeningRefreshService
                refresh_service = ScreeningRefreshService(current_user.org_id)
                
                # Force refresh for all screening types (since preset was just applied)
                refresh_options = {
                    'force_refresh': True
                }
                
                refresh_results = refresh_service.refresh_screenings(refresh_options=refresh_options)
                
                if refresh_results.get('success'):
                    stats = refresh_results.get('stats', {})
                    screenings_created = stats.get('screenings_updated', 0)
                    
                    if screenings_created > 0:
                        success_message += f'. {screenings_created} screening items created for eligible patients'
                
                flash(success_message, 'success')
            else:
                if result['errors']:
                    flash(f'Failed to apply preset "{preset.name}": ' + '; '.join(result['errors']), 'error')
                else:
                    if existing_count == 0:
                        flash(f'Warning: No screening types were imported from preset "{preset.name}". This may indicate a data format issue.', 'warning')
                    else:
                        flash(f'No changes made - all screening types already exist. Use "Force Overwrite" to update existing types.', 'info')
        else:
            error_message = f'Failed to apply preset "{preset.name}": {result.get("error", "Unknown error")}'
            if result.get('errors'):
                error_message += ' Details: ' + '; '.join(result['errors'])
            flash(error_message, 'error')
        
        return redirect(url_for('admin.view_presets'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error applying preset to organization: {str(e)}")
        flash(f'Error applying preset: {str(e)}', 'error')
        return redirect(url_for('admin.view_presets'))


# Dashboard apply route removed - consolidating apply functionality to /admin/presets only

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
        
        # Add summary information for the UI
        total_types = len(preset.get_screening_types())
        existing_count = len(conflicts.get('existing_types', []))
        missing_count = len(conflicts.get('missing_types', []))
        modified_count = len(conflicts.get('modified_types', []))
        
        conflicts['summary'] = {
            'total_types': total_types,
            'existing_count': existing_count,
            'missing_count': missing_count,
            'modified_count': modified_count,
            'will_add': missing_count,
            'will_update': modified_count if conflicts.get('has_conflicts') else 0,
            'will_skip': existing_count - modified_count
        }
        
        return jsonify(conflicts)
        
    except Exception as e:
        logger.error(f"Error checking preset conflicts: {str(e)}")
        return jsonify({
            'has_conflicts': False,
            'existing_types': [],
            'modified_types': [],
            'missing_types': [],
            'error': 'Error checking conflicts',
            'summary': {
                'total_types': 0,
                'existing_count': 0,
                'missing_count': 0,
                'modified_count': 0,
                'will_add': 0,
                'will_update': 0,
                'will_skip': 0
            }
        }), 500

@admin_bp.route('/documents')
@login_required
@admin_required
def admin_documents():
    """Admin documents page - Show per-patient document inventory including FHIR documents and immunizations"""
    try:
        # Get all patients in the current organization
        from models import Patient, Document, FHIRDocument, PatientCondition, FHIRImmunization
        from datetime import date
        from core.matcher import DocumentMatcher
        
        # Get filter and pagination parameters
        patient_search = request.args.get('patient_search', '').strip()
        has_matches_filter = request.args.get('has_matches', '').strip()
        has_dismissed_filter = request.args.get('has_dismissed', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Build patient query with search filter
        patients_query = Patient.query.filter_by(org_id=current_user.org_id)
        
        if patient_search:
            # Case-insensitive patient name search
            from sqlalchemy import func
            patients_query = patients_query.filter(
                func.lower(Patient.name).like(f'%{patient_search.lower()}%')
            )
        
        # Order by name for consistent pagination
        patients_query = patients_query.order_by(Patient.name)
        
        # Get total count before pagination
        total_patients = patients_query.count()
        
        # Apply pagination
        patients = patients_query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Calculate pagination info
        total_pages = (total_patients + per_page - 1) // per_page  # Ceiling division
        
        matcher = DocumentMatcher()
        
        # BATCH OPTIMIZATION: Collect all documents for all patients first
        all_documents = []
        patient_docs_map = {}  # Map patient_id -> {'manual': [], 'fhir': [], 'immunizations': []}
        
        for patient in patients:
            # Get manual documents
            manual_documents = Document.query.filter_by(patient_id=patient.id).all()
            
            # Get FHIR documents (exclude HealthPrep-generated and superseded prep sheets)
            fhir_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id,
                is_healthprep_generated=False,
                is_superseded=False
            ).all()
            
            # Get immunizations
            immunizations = FHIRImmunization.query.filter_by(patient_id=patient.id).order_by(FHIRImmunization.administration_date.desc()).all()
            
            patient_docs_map[patient.id] = {
                'manual': manual_documents,
                'fhir': fhir_documents,
                'immunizations': immunizations
            }
            
            all_documents.extend(manual_documents)
            all_documents.extend(fhir_documents)
        
        # BATCH LOAD: Get all match details in 1-2 queries instead of N queries
        batch_match_results = matcher.get_batch_document_match_details(all_documents, include_dismissed=True)
        
        # Build patient document data using batch results
        patient_data = []
        for patient in patients:
            # Get patient conditions
            conditions = PatientCondition.query.filter_by(
                patient_id=patient.id,
                is_active=True
            ).all()
            condition_names = [condition.condition_name for condition in conditions]
            
            manual_documents = patient_docs_map[patient.id]['manual']
            fhir_documents = patient_docs_map[patient.id]['fhir']
            immunizations = patient_docs_map[patient.id]['immunizations']
            
            # Combine documents with source markers and match details from batch results
            combined_documents = []
            
            # Add manual documents
            for doc in manual_documents:
                # Use composite key to prevent ID collision with FHIRDocument table
                composite_key = f"manual_{doc.id}"
                match_data = batch_match_results.get(composite_key, {'active': [], 'dismissed': []})
                active_matches = match_data['active']
                dismissed_matches = match_data['dismissed']
                
                combined_documents.append({
                    'id': doc.id,
                    'source': 'Manual',
                    'source_badge': 'primary',
                    'title': doc.filename or 'Untitled',
                    'document_type': doc.document_type or 'Unknown',
                    'ocr_text': doc.ocr_text,
                    'document_date': doc.document_date,
                    'created_at': doc.created_at,
                    'raw_object': doc,
                    'active_matches': active_matches,
                    'dismissed_matches': dismissed_matches
                })
            
            # Add FHIR documents
            for doc in fhir_documents:
                # Use composite key to prevent ID collision with Document table
                composite_key = f"fhir_{doc.id}"
                match_data = batch_match_results.get(composite_key, {'active': [], 'dismissed': []})
                active_matches = match_data['active']
                dismissed_matches = match_data['dismissed']
                
                combined_documents.append({
                    'id': doc.id,
                    'source': 'Epic FHIR',
                    'source_badge': 'success',
                    'title': getattr(doc, 'title', '') or 'Untitled',
                    'document_type': doc.document_type_display or 'Unknown',
                    'ocr_text': doc.ocr_text,
                    'document_date': doc.document_date,
                    'created_at': doc.created_at,
                    'epic_id': doc.epic_document_id,
                    'raw_object': doc,
                    'active_matches': active_matches,
                    'dismissed_matches': dismissed_matches
                })
            
            # Apply "has active matches" filter at DOCUMENT level
            if has_matches_filter:
                # Filter out documents without active matches
                combined_documents = [doc for doc in combined_documents if doc['active_matches']]
                
                # Skip patient if no documents remain after filtering
                if not combined_documents:
                    continue
            
            # Apply "has dismissed matches" filter at DOCUMENT level
            if has_dismissed_filter:
                # Filter out documents without dismissed matches
                combined_documents = [doc for doc in combined_documents if doc['dismissed_matches']]
                
                # Skip patient if no documents remain after filtering
                if not combined_documents:
                    continue
            
            # Count documents by type and source
            doc_counts = {}
            doc_with_ocr = 0
            total_docs = len(combined_documents)
            source_counts = {'Manual': len([d for d in combined_documents if d['source'] == 'Manual']), 
                           'Epic FHIR': len([d for d in combined_documents if d['source'] == 'Epic FHIR'])}
            
            for doc in combined_documents:
                doc_type = doc['document_type']
                doc_counts[doc_type] = doc_counts.get(doc_type, 0) + 1
                if doc['ocr_text']:
                    doc_with_ocr += 1
            
            # Format immunizations for display
            formatted_immunizations = []
            for imm in immunizations:
                formatted_immunizations.append({
                    'id': imm.id,
                    'vaccine_name': imm.vaccine_name,
                    'vaccine_group': imm.vaccine_group,
                    'cvx_code': imm.cvx_code,
                    'administration_date': imm.administration_date,
                    'status': imm.status,
                    'is_sample_data': imm.is_sample_data,
                    'source': 'Sample' if imm.is_sample_data else 'Epic FHIR'
                })
            
            patient_data.append({
                'patient': patient,
                'documents': combined_documents,
                'immunizations': formatted_immunizations,
                'total_documents': total_docs,
                'total_immunizations': len(formatted_immunizations),
                'documents_with_ocr': doc_with_ocr,
                'document_counts': doc_counts,
                'source_counts': source_counts,
                'conditions': condition_names
            })
        
        # Document processing audit events:
        # - document_processing_complete: Consolidated event with sub-actions (new format)
        # - phi_filtered: PHI filtering events from model setters
        DOCUMENT_PROCESSING_EVENTS = [
            'document_processing_complete',  # Consolidated event with success/fail status
            'phi_filtered'  # PHI filtering events
        ]
        processing_audit_logs = AdminLog.query.filter(
            AdminLog.org_id == current_user.org_id,
            AdminLog.event_type.in_(DOCUMENT_PROCESSING_EVENTS)
        ).order_by(AdminLog.timestamp.desc()).limit(50).all()
        
        from services.security_alerts import SecurityAlertService
        unacknowledged_alerts = SecurityAlertService.get_unacknowledged_alerts(current_user.org_id, limit=5)
        
        return render_template('admin/documents.html', 
                             patient_data=patient_data,
                             total_patients=total_patients,
                             current_date=date.today(),
                             page=page,
                             total_pages=total_pages,
                             per_page=per_page,
                             processing_audit_logs=processing_audit_logs,
                             unacknowledged_alerts=unacknowledged_alerts)
        
    except Exception as e:
        logger.error(f"Error in admin documents: {str(e)}")
        flash('Error loading document inventory', 'error')
        return render_template('error/500.html'), 500


@admin_bp.route('/documents/dismiss-match', methods=['POST'])
@login_required
@admin_required
def dismiss_document_match():
    """Dismiss a false positive document-screening match"""
    try:
        from models import DismissedDocumentMatch, Screening, Document, FHIRDocument
        
        # Get parameters
        document_id = request.form.get('document_id', type=int)
        fhir_document_id = request.form.get('fhir_document_id', type=int)
        screening_id = request.form.get('screening_id', type=int)
        reason = request.form.get('reason', '').strip()
        
        # Validate inputs
        if not screening_id:
            return jsonify({'success': False, 'error': 'Screening ID required'}), 400
        
        # Ensure exactly ONE of document_id or fhir_document_id is provided
        if (document_id and fhir_document_id) or (not document_id and not fhir_document_id):
            return jsonify({'success': False, 'error': 'Provide exactly one of document_id or fhir_document_id'}), 400
        
        # Verify screening exists and belongs to user's org
        screening = Screening.query.get(screening_id)
        if not screening or screening.patient.org_id != current_user.org_id:
            return jsonify({'success': False, 'error': 'Screening not found'}), 404
        
        # Verify document belongs to same patient and org as screening
        if document_id:
            document = Document.query.get(document_id)
            if not document:
                return jsonify({'success': False, 'error': 'Document not found'}), 404
            if document.patient_id != screening.patient_id:
                return jsonify({'success': False, 'error': 'Document does not belong to screening patient'}), 403
            if document.org_id != current_user.org_id:
                return jsonify({'success': False, 'error': 'Document does not belong to your organization'}), 403
        else:
            fhir_document = FHIRDocument.query.get(fhir_document_id)
            if not fhir_document:
                return jsonify({'success': False, 'error': 'FHIR Document not found'}), 404
            if fhir_document.patient_id != screening.patient_id:
                return jsonify({'success': False, 'error': 'FHIR Document does not belong to screening patient'}), 403
            if fhir_document.org_id != current_user.org_id:
                return jsonify({'success': False, 'error': 'FHIR Document does not belong to your organization'}), 403
        
        # Check if already dismissed
        existing = DismissedDocumentMatch.query.filter_by(
            document_id=document_id,
            fhir_document_id=fhir_document_id,
            screening_id=screening_id,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'error': 'Match already dismissed'}), 400
        
        # Create dismissal record
        dismissal = DismissedDocumentMatch()  # type: ignore
        dismissal.document_id = document_id
        dismissal.fhir_document_id = fhir_document_id
        dismissal.screening_id = screening_id
        dismissal.org_id = current_user.org_id
        dismissal.dismissed_by = current_user.id
        dismissal.dismissal_reason = reason or None
        
        db.session.add(dismissal)
        db.session.commit()
        
        # Audit log for document match dismissal (security compliance)
        log_admin_event(
            event_type='document_match_dismissed',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={
                'document_id': document_id,
                'fhir_document_id': fhir_document_id,
                'screening_id': screening_id,
                'dismissal_id': dismissal.id,
                'reason': reason or 'Not specified',
                'patient_id': screening.patient_id,
                'description': f'Document match dismissed by {current_user.username}'
            }
        )
        
        logger.info(f"User {current_user.id} dismissed document match: Doc={document_id or fhir_document_id} -> Screening={screening_id}")
        
        # Refresh screening status to reflect dismissed match
        from services.screening_refresh_service import ScreeningRefreshService
        refresh_service = ScreeningRefreshService(organization_id=current_user.org_id)
        refresh_service._update_screening_status_with_current_criteria(screening)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Match dismissed successfully',
            'dismissal_id': dismissal.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error dismissing match: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/documents/restore-match', methods=['POST'])
@login_required
@admin_required
def restore_document_match():
    """Restore a previously dismissed document-screening match"""
    try:
        from models import DismissedDocumentMatch, Screening
        
        dismissal_id = request.form.get('dismissal_id', type=int)
        
        if not dismissal_id:
            return jsonify({'success': False, 'error': 'Dismissal ID required'}), 400
        
        # Get dismissal record with org validation
        dismissal = DismissedDocumentMatch.query.get(dismissal_id)
        
        if not dismissal or dismissal.org_id != current_user.org_id:
            return jsonify({'success': False, 'error': 'Dismissal not found'}), 404
        
        # Verify screening still belongs to user's org
        screening = Screening.query.get(dismissal.screening_id)
        if not screening or screening.patient.org_id != current_user.org_id:
            return jsonify({'success': False, 'error': 'Screening access denied'}), 403
        
        if not dismissal.is_active:
            return jsonify({'success': False, 'error': 'Match already restored'}), 400
        
        # Restore the match
        dismissal.is_active = False
        dismissal.restored_by = current_user.id
        dismissal.restored_at = datetime.utcnow()
        
        db.session.commit()
        
        # Audit log for document match restoration (security compliance)
        log_admin_event(
            event_type='document_match_restored',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={
                'dismissal_id': dismissal_id,
                'document_id': dismissal.document_id,
                'fhir_document_id': dismissal.fhir_document_id,
                'screening_id': dismissal.screening_id,
                'patient_id': screening.patient_id,
                'description': f'Document match restored by {current_user.username}'
            }
        )
        
        logger.info(f"User {current_user.id} restored document match: Dismissal={dismissal_id}")
        
        # Refresh screening status to reflect restored match
        from services.screening_refresh_service import ScreeningRefreshService
        refresh_service = ScreeningRefreshService(organization_id=current_user.org_id)
        refresh_service._update_screening_status_with_current_criteria(screening)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Match restored successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error restoring match: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Provider Management Routes
# ============================================

@admin_bp.route('/providers')
@login_required
@admin_required
def provider_list():
    """List all providers for the organization"""
    try:
        providers = Provider.query.filter_by(
            org_id=current_user.org_id
        ).order_by(Provider.name).all()
        
        provider_stats = []
        for provider in providers:
            patient_count = provider.patients.count() if hasattr(provider, 'patients') else 0
            assignment_count = UserProviderAssignment.query.filter_by(provider_id=provider.id).count()
            
            provider_stats.append({
                'provider': provider,
                'patient_count': patient_count,
                'user_count': assignment_count,
                'is_epic_connected': provider.is_epic_connected,
                'last_sync': provider.last_epic_sync
            })
        
        return render_template('admin/providers/list.html',
                             providers=provider_stats,
                             total_providers=len(providers))
    except Exception as e:
        logger.error(f"Error loading providers: {str(e)}")
        flash('Error loading providers', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/providers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_provider():
    """Add a new provider to the organization"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            specialty = request.form.get('specialty', '').strip()
            npi = request.form.get('npi', '').strip()
            
            if not name:
                flash('Provider name is required', 'error')
                return redirect(url_for('admin.add_provider'))
            
            existing = Provider.query.filter_by(
                name=name,
                org_id=current_user.org_id
            ).first()
            
            if existing:
                flash('A provider with this name already exists', 'error')
                return redirect(url_for('admin.add_provider'))
            
            provider = Provider(
                name=name,
                specialty=specialty,
                npi=npi or None,
                org_id=current_user.org_id,
                is_active=True,
                created_by=current_user.id
            )
            
            db.session.add(provider)
            db.session.commit()
            
            org = Organization.query.get(current_user.org_id)
            if org and org.stripe_subscription_id:
                StripeService.on_provider_added(org, provider)
            
            log_admin_event(
                current_user.id,
                'PROVIDER_CREATED',
                f'Created provider: {name}',
                resource_type='provider',
                resource_id=provider.id,
                org_id=current_user.org_id
            )
            
            flash(f'Provider "{name}" added successfully', 'success')
            return redirect(url_for('admin.provider_list'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding provider: {str(e)}")
            flash('Error adding provider', 'error')
            return redirect(url_for('admin.add_provider'))
    
    specialties = [
        'Primary Care', 'Family Medicine', 'Internal Medicine',
        'Cardiology', 'Dermatology', 'Endocrinology',
        'Gastroenterology', 'Neurology', 'Oncology',
        'Orthopedics', 'Pediatrics', 'Psychiatry',
        'Pulmonology', 'Rheumatology', 'Urology'
    ]
    
    return render_template('admin/providers/add.html', specialties=specialties)


@admin_bp.route('/providers/<int:provider_id>')
@login_required
@admin_required
def provider_detail(provider_id):
    """View provider details and settings"""
    try:
        provider = Provider.query.filter_by(
            id=provider_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        assignments = UserProviderAssignment.query.filter_by(
            provider_id=provider_id
        ).all()
        
        assigned_users = [a.user for a in assignments]
        
        available_users = User.query.filter_by(
            org_id=current_user.org_id,
            is_active_user=True
        ).filter(
            ~User.id.in_([u.id for u in assigned_users])
        ).all()
        
        return render_template('admin/providers/detail.html',
                             provider=provider,
                             assigned_users=assigned_users,
                             available_users=available_users,
                             assignments=assignments)
    except Exception as e:
        logger.error(f"Error loading provider: {str(e)}")
        flash('Error loading provider', 'error')
        return redirect(url_for('admin.provider_list'))


@admin_bp.route('/providers/<int:provider_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_provider(provider_id):
    """Edit provider settings"""
    try:
        provider = Provider.query.filter_by(
            id=provider_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            specialty = request.form.get('specialty', '').strip()
            npi = request.form.get('npi', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Provider name is required', 'error')
                return redirect(url_for('admin.edit_provider', provider_id=provider_id))
            
            existing = Provider.query.filter_by(
                name=name,
                org_id=current_user.org_id
            ).filter(Provider.id != provider_id).first()
            
            if existing:
                flash('A provider with this name already exists', 'error')
                return redirect(url_for('admin.edit_provider', provider_id=provider_id))
            
            was_active = provider.is_active
            provider.name = name
            provider.specialty = specialty
            provider.npi = npi or None
            provider.is_active = is_active
            
            db.session.commit()
            
            if was_active != is_active:
                org = Organization.query.get(current_user.org_id)
                if org and org.stripe_subscription_id:
                    if is_active:
                        StripeService.on_provider_added(org, provider)
                    else:
                        StripeService.on_provider_removed(org, provider)
            
            log_admin_event(
                current_user.id,
                'PROVIDER_UPDATED',
                f'Updated provider: {name}',
                resource_type='provider',
                resource_id=provider.id,
                org_id=current_user.org_id
            )
            
            flash('Provider updated successfully', 'success')
            return redirect(url_for('admin.provider_detail', provider_id=provider_id))
            
        specialties = [
            'Primary Care', 'Family Medicine', 'Internal Medicine',
            'Cardiology', 'Dermatology', 'Endocrinology',
            'Gastroenterology', 'Neurology', 'Oncology',
            'Orthopedics', 'Pediatrics', 'Psychiatry',
            'Pulmonology', 'Rheumatology', 'Urology'
        ]
        
        return render_template('admin/providers/edit.html',
                             provider=provider,
                             specialties=specialties)
    except Exception as e:
        logger.error(f"Error editing provider: {str(e)}")
        flash('Error editing provider', 'error')
        return redirect(url_for('admin.provider_list'))


@admin_bp.route('/providers/<int:provider_id>/assign-user', methods=['POST'])
@login_required
@admin_required
def assign_user_to_provider(provider_id):
    """Assign a user to a provider"""
    try:
        provider = Provider.query.filter_by(
            id=provider_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        user_id = request.form.get('user_id', type=int)
        if not user_id:
            flash('User is required', 'error')
            return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
        user = User.query.filter_by(
            id=user_id,
            org_id=current_user.org_id
        ).first()
        
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
        # Check if user is a subuser (nurse/MA) - they can only belong to ONE provider
        is_subuser = user.role in ['nurse', 'MA']
        if is_subuser:
            existing_assignments = UserProviderAssignment.query.filter_by(user_id=user_id).count()
            if existing_assignments > 0:
                flash(f'Subusers (nurses/MAs) can only be assigned to one provider. {user.username} is already assigned to another provider.', 'error')
                return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
        existing = UserProviderAssignment.query.filter_by(
            user_id=user_id,
            provider_id=provider_id
        ).first()
        
        if existing:
            flash('User is already assigned to this provider', 'warning')
            return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
        assignment = UserProviderAssignment(
            user_id=user_id,
            provider_id=provider_id,
            org_id=current_user.org_id,
            assigned_by=current_user.id,
            can_view_patients=True,
            can_edit_screenings=True,
            can_generate_prep_sheets=True,
            can_sync_epic=(user.role == 'admin')  # Only admins can sync Epic
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        log_admin_event(
            current_user.id,
            'USER_ASSIGNED_TO_PROVIDER',
            f'Assigned {user.username} to provider {provider.name}',
            resource_type='user_provider_assignment',
            resource_id=assignment.id,
            org_id=current_user.org_id
        )
        
        flash(f'{user.username} assigned to {provider.name}', 'success')
        return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error assigning user to provider: {str(e)}")
        flash('Error assigning user to provider', 'error')
        return redirect(url_for('admin.provider_detail', provider_id=provider_id))


@admin_bp.route('/providers/<int:provider_id>/remove-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def remove_user_from_provider(provider_id, user_id):
    """Remove a user from a provider"""
    try:
        provider = Provider.query.filter_by(
            id=provider_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        assignment = UserProviderAssignment.query.filter_by(
            user_id=user_id,
            provider_id=provider_id
        ).first()
        
        if not assignment:
            flash('Assignment not found', 'error')
            return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
        user = User.query.get(user_id)
        username = user.username if user else 'Unknown'
        
        db.session.delete(assignment)
        db.session.commit()
        
        log_admin_event(
            current_user.id,
            'USER_REMOVED_FROM_PROVIDER',
            f'Removed {username} from provider {provider.name}',
            resource_type='user_provider_assignment',
            org_id=current_user.org_id
        )
        
        flash(f'{username} removed from {provider.name}', 'success')
        return redirect(url_for('admin.provider_detail', provider_id=provider_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing user from provider: {str(e)}")
        flash('Error removing user from provider', 'error')
        return redirect(url_for('admin.provider_detail', provider_id=provider_id))


"""
Epic Session Cleanup Service
Handles Epic OAuth browser session conflicts and scope changes
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from flask import session, current_app
from models import db, Organization, EpicCredentials

logger = logging.getLogger(__name__)


class EpicSessionCleanupService:
    """
    Service to handle Epic OAuth session conflicts and cleanup
    
    Epic's sandbox has strict session management that rejects multiple
    concurrent OAuth flows in the same browser. This service provides
    methods to detect and resolve these conflicts.
    """
    
    @staticmethod
    def clear_all_epic_sessions(org_id: int = None) -> Dict[str, any]:
        """
        Clear all Epic-related session data and stored tokens
        
        Args:
            org_id: Optional organization ID to limit cleanup scope
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            logger.info(f"Starting Epic session cleanup for org_id: {org_id}")
            
            results = {
                'session_keys_cleared': [],
                'database_tokens_cleared': False,
                'organization_status_reset': False,
                'conflicts_resolved': 0,
                'success': True,
                'message': 'Epic sessions cleared successfully'
            }
            
            # Clear Flask session Epic data
            epic_session_keys = [
                'epic_access_token',
                'epic_refresh_token', 
                'epic_token_expires',
                'epic_token_scopes',
                'epic_patient_id',
                'epic_org_id',
                'epic_oauth_state',
                'epic_auth_timestamp',
                'epic_launch_context',
                'epic_scope_requested',
                'epic_last_auth_attempt'
            ]
            
            for key in epic_session_keys:
                if key in session:
                    session.pop(key, None)
                    results['session_keys_cleared'].append(key)
            
            # Clear database tokens if org_id provided
            if org_id:
                epic_creds = EpicCredentials.query.filter_by(org_id=org_id).first()
                if epic_creds:
                    # Clear tokens but preserve configuration
                    epic_creds.access_token = None
                    epic_creds.refresh_token = None
                    epic_creds.token_expires_at = None
                    epic_creds.token_scope = None
                    epic_creds.updated_at = datetime.now()
                    results['database_tokens_cleared'] = True
                
                # Reset organization connection status
                org = Organization.query.get(org_id)
                if org:
                    org.is_epic_connected = False
                    org.epic_token_expiry = None
                    org.last_epic_error = "Session cleared - re-authentication required"
                    org.connection_retry_count = 0
                    results['organization_status_reset'] = True
                
                db.session.commit()
                results['conflicts_resolved'] = 1
            
            logger.info(f"Epic session cleanup completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error during Epic session cleanup: {str(e)}")
            return {
                'success': False,
                'message': f'Session cleanup failed: {str(e)}',
                'session_keys_cleared': [],
                'database_tokens_cleared': False,
                'organization_status_reset': False,
                'conflicts_resolved': 0
            }
    
    @staticmethod
    def detect_scope_changes(org_id: int, requested_scopes: List[str]) -> Tuple[bool, List[str], List[str]]:
        """
        Detect if OAuth scope changes require session cleanup
        
        Args:
            org_id: Organization ID
            requested_scopes: List of scopes being requested
            
        Returns:
            Tuple of (scope_changed, added_scopes, removed_scopes)
        """
        try:
            epic_creds = EpicCredentials.query.filter_by(org_id=org_id).first()
            
            if not epic_creds or not epic_creds.token_scope:
                # No existing scopes, any request is a change
                return True, requested_scopes, []
            
            current_scopes = set(epic_creds.token_scope.split())
            requested_scopes_set = set(requested_scopes)
            
            added_scopes = list(requested_scopes_set - current_scopes)
            removed_scopes = list(current_scopes - requested_scopes_set)
            scope_changed = bool(added_scopes or removed_scopes)
            
            if scope_changed:
                logger.info(f"Scope changes detected for org {org_id}:")
                logger.info(f"  Added scopes: {added_scopes}")
                logger.info(f"  Removed scopes: {removed_scopes}")
            
            return scope_changed, added_scopes, removed_scopes
            
        except Exception as e:
            logger.error(f"Error detecting scope changes: {str(e)}")
            # On error, assume scope change to be safe
            return True, requested_scopes, []
    
    @staticmethod
    def is_epic_session_conflict_error(error: str, error_description: str = None) -> bool:
        """
        Detect if error indicates Epic session conflict
        
        Args:
            error: OAuth error code
            error_description: OAuth error description
            
        Returns:
            True if this is a session conflict error
        """
        # Only match specific Epic session conflict messages to avoid over-broad detection
        specific_conflict_indicators = [
            'another process already logged in on the same browser',
            'cannot authenticate while there is another process',
            'multiple authentication sessions detected',
            'browser session conflict',
            'concurrent epic authentication'
        ]
        
        # Only check error_description for specific messages, not generic "server_error"
        error_text = (error_description or '').lower()
        
        # Additional check: server_error + specific Epic session messages
        if error == 'server_error' and error_description:
            for indicator in specific_conflict_indicators:
                if indicator in error_text:
                    logger.info(f"Epic session conflict detected: {error} - {error_description}")
                    return True
        
        # Direct match on known conflict descriptions
        for indicator in specific_conflict_indicators:
            if indicator in error_text:
                logger.info(f"Epic session conflict detected: {error_description}")
                return True
        
        # Log non-matching errors for analysis and refinement
        if error == 'server_error':
            logger.info(f"Epic server_error (not classified as session conflict): {error} - {error_description}")
        
        return False
    
    @staticmethod
    def prepare_for_scope_change(org_id: int, new_scopes: List[str]) -> Dict[str, any]:
        """
        Prepare Epic session for scope changes
        
        Args:
            org_id: Organization ID
            new_scopes: New scopes to be requested
            
        Returns:
            Preparation results
        """
        try:
            logger.info(f"Preparing for scope change - org: {org_id}, scopes: {new_scopes}")
            
            # Check if scope change is needed
            scope_changed, added, removed = EpicSessionCleanupService.detect_scope_changes(
                org_id, new_scopes
            )
            
            if not scope_changed:
                return {
                    'success': True,
                    'scope_changed': False,
                    'message': 'No scope changes detected',
                    'cleanup_performed': False
                }
            
            # Perform session cleanup for scope changes
            cleanup_results = EpicSessionCleanupService.clear_all_epic_sessions(org_id)
            
            # Store new scope request in session for tracking
            session['epic_scope_requested'] = ' '.join(new_scopes)
            session['epic_scope_change_timestamp'] = datetime.now().isoformat()
            
            return {
                'success': True,
                'scope_changed': True,
                'added_scopes': added,
                'removed_scopes': removed,
                'cleanup_performed': cleanup_results['success'],
                'message': 'Session prepared for scope change',
                'cleanup_details': cleanup_results
            }
            
        except Exception as e:
            logger.error(f"Error preparing for scope change: {str(e)}")
            return {
                'success': False,
                'scope_changed': True,
                'message': f'Scope change preparation failed: {str(e)}',
                'cleanup_performed': False
            }
    
    @staticmethod
    def handle_oauth_conflict_error(org_id: int, error: str, error_description: str = None) -> Dict[str, any]:
        """
        Handle Epic OAuth conflict errors with automatic resolution
        
        Args:
            org_id: Organization ID
            error: OAuth error code
            error_description: OAuth error description
            
        Returns:
            Conflict resolution results
        """
        try:
            logger.warning(f"Handling Epic OAuth conflict for org {org_id}: {error} - {error_description}")
            
            if not EpicSessionCleanupService.is_epic_session_conflict_error(error, error_description):
                return {
                    'success': False,
                    'is_conflict': False,
                    'message': 'Not a session conflict error',
                    'resolution_attempted': False
                }
            
            # Perform comprehensive session cleanup
            cleanup_results = EpicSessionCleanupService.clear_all_epic_sessions(org_id)
            
            # Wait a moment for Epic to process the cleanup
            from time import sleep
            sleep(1)
            
            return {
                'success': cleanup_results['success'],
                'is_conflict': True,
                'resolution_attempted': True,
                'message': 'Session conflict resolved - please retry authentication',
                'cleanup_details': cleanup_results,
                'retry_recommended': True,
                'wait_seconds': 5  # Recommend waiting before retry
            }
            
        except Exception as e:
            logger.error(f"Error handling OAuth conflict: {str(e)}")
            return {
                'success': False,
                'is_conflict': True,
                'resolution_attempted': False,
                'message': f'Conflict resolution failed: {str(e)}',
                'retry_recommended': False
            }
    
    @staticmethod
    def get_session_cleanup_status(org_id: int = None) -> Dict[str, any]:
        """
        Get current Epic session status and cleanup recommendations
        
        Args:
            org_id: Optional organization ID for specific status
            
        Returns:
            Session status information
        """
        try:
            status = {
                'has_active_session': False,
                'has_valid_tokens': False,
                'session_age_minutes': 0,
                'token_expires_in_minutes': 0,
                'cleanup_recommended': False,
                'cleanup_reason': None,
                'epic_connected': False
            }
            
            # Check Flask session
            if 'epic_access_token' in session:
                status['has_active_session'] = True
                
                # Calculate session age
                if 'epic_auth_timestamp' in session:
                    try:
                        auth_time = datetime.fromisoformat(session['epic_auth_timestamp'])
                        age = datetime.now() - auth_time
                        status['session_age_minutes'] = int(age.total_seconds() / 60)
                    except:
                        pass
                
                # Check token expiry
                if 'epic_token_expires' in session:
                    try:
                        expires_time = datetime.fromisoformat(session['epic_token_expires'])
                        time_left = expires_time - datetime.now()
                        status['token_expires_in_minutes'] = int(time_left.total_seconds() / 60)
                        status['has_valid_tokens'] = time_left.total_seconds() > 0
                    except:
                        pass
            
            # Check database tokens if org_id provided
            if org_id:
                epic_creds = EpicCredentials.query.filter_by(org_id=org_id).first()
                org = Organization.query.get(org_id)
                
                if org:
                    status['epic_connected'] = org.is_epic_connected
                
                if epic_creds and epic_creds.access_token:
                    if epic_creds.token_expires_at:
                        time_left = epic_creds.token_expires_at - datetime.now()
                        status['token_expires_in_minutes'] = max(
                            status['token_expires_in_minutes'],
                            int(time_left.total_seconds() / 60)
                        )
                        status['has_valid_tokens'] = time_left.total_seconds() > 0
            
            # Recommend cleanup if session is old or tokens expired
            if status['session_age_minutes'] > 60:  # 1 hour
                status['cleanup_recommended'] = True
                status['cleanup_reason'] = 'Session is over 1 hour old'
            elif not status['has_valid_tokens'] and status['has_active_session']:
                status['cleanup_recommended'] = True
                status['cleanup_reason'] = 'Session has expired tokens'
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting session cleanup status: {str(e)}")
            return {
                'has_active_session': False,
                'has_valid_tokens': False,
                'session_age_minutes': 0,
                'token_expires_in_minutes': 0,
                'cleanup_recommended': True,
                'cleanup_reason': f'Status check failed: {str(e)}',
                'epic_connected': False
            }
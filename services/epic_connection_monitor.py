"""
Epic Connection Status Monitor
Implements background token checking and notification system per blueprint
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from flask import current_app

from models import Organization, db
from emr.fhir_client import FHIRClient

logger = logging.getLogger(__name__)

class EpicConnectionMonitor:
    """
    Background service for monitoring Epic connection health
    Implements blueprint suggestion for proactive token management
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_all_organizations(self) -> Dict[str, int]:
        """
        Check Epic connection status for all organizations
        Returns summary of organizations by status
        """
        try:
            organizations = Organization.query.all()
            
            stats = {
                'total': len(organizations),
                'connected': 0,
                'expired': 0,
                'expiring_soon': 0,
                'disconnected': 0,
                'checked': 0
            }
            
            for org in organizations:
                if org.epic_client_id:  # Only check orgs with Epic configuration
                    self.check_organization_connection(org)
                    stats['checked'] += 1
                    
                    status = org.get_epic_connection_status()
                    if status['is_connected']:
                        if status['action_required']:
                            stats['expiring_soon'] += 1
                        else:
                            stats['connected'] += 1
                    elif 'expired' in status['status_message'].lower():
                        stats['expired'] += 1
                    else:
                        stats['disconnected'] += 1
            
            self.logger.info(f"Connection check complete: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error checking organization connections: {str(e)}")
            return {'error': str(e)}
    
    def check_organization_connection(self, org: Organization) -> bool:
        """
        Check specific organization's Epic connection status
        Returns True if action was taken, False if no action needed
        """
        try:
            # Skip if organization doesn't need checking
            if not org.needs_token_check():
                return False
            
            self.logger.debug(f"Checking connection for organization {org.name}")
            
            # Check if Epic credentials exist
            epic_creds = org.epic_credentials
            if not epic_creds:
                org.update_epic_connection_status(
                    is_connected=False,
                    error_message="No Epic credentials configured"
                )
                return True
            
            # Get most recent credentials
            latest_cred = max(epic_creds, key=lambda c: c.updated_at) if epic_creds else None
            
            if not latest_cred or latest_cred.is_expired:
                if latest_cred and latest_cred.expires_soon:
                    # Try to refresh before expiry
                    if self._attempt_token_refresh(org, latest_cred):
                        org.update_epic_connection_status(
                            is_connected=True,
                            token_expiry=latest_cred.token_expires_at
                        )
                    else:
                        org.update_epic_connection_status(
                            is_connected=False,
                            error_message="Token refresh failed - re-authentication required"
                        )
                else:
                    org.update_epic_connection_status(
                        is_connected=False,
                        error_message="Epic token expired - re-authentication required"
                    )
                return True
            
            # Connection is healthy
            org.update_epic_connection_status(
                is_connected=True,
                token_expiry=latest_cred.token_expires_at
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking connection for org {org.name}: {str(e)}")
            org.update_epic_connection_status(
                is_connected=False,
                error_message=f"Connection check failed: {str(e)}"
            )
            return True
    
    def _attempt_token_refresh(self, org: Organization, credentials) -> bool:
        """Attempt to refresh Epic token for organization"""
        try:
            # Create FHIR client with organization context
            epic_config = org.get_epic_fhir_config()
            fhir_client = FHIRClient(
                organization_config=epic_config,
                organization=org
            )
            
            # Set current tokens
            fhir_client.set_tokens(
                access_token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                expires_in=(credentials.token_expires_at - datetime.utcnow()).total_seconds() if credentials.token_expires_at else 0
            )
            
            # Attempt refresh
            success = fhir_client.refresh_access_token()
            
            if success:
                # Update credentials in database
                credentials.access_token = fhir_client.access_token
                if fhir_client.refresh_token:
                    credentials.refresh_token = fhir_client.refresh_token
                credentials.token_expires_at = fhir_client.token_expires
                credentials.updated_at = datetime.utcnow()
                db.session.commit()
                
                self.logger.info(f"Successfully refreshed token for organization {org.name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Token refresh attempt failed for org {org.name}: {str(e)}")
            return False
    
    def get_organizations_needing_attention(self) -> List[Dict]:
        """
        Get list of organizations that need admin attention
        For proactive notification system
        """
        try:
            organizations = Organization.query.filter(
                Organization.epic_client_id.isnot(None)
            ).all()
            
            attention_needed = []
            
            for org in organizations:
                status = org.get_epic_connection_status()
                
                if status['action_required']:
                    attention_needed.append({
                        'org_id': org.id,
                        'org_name': org.name,
                        'status_message': status['status_message'],
                        'status_class': status['status_class'],
                        'last_error': status['last_error'],
                        'retry_count': status['retry_count'],
                        'last_sync': status['last_sync']
                    })
            
            return attention_needed
            
        except Exception as e:
            self.logger.error(f"Error getting organizations needing attention: {str(e)}")
            return []
    
    def generate_connection_report(self) -> Dict:
        """Generate comprehensive connection status report"""
        try:
            stats = self.check_all_organizations()
            attention_needed = self.get_organizations_needing_attention()
            
            return {
                'generated_at': datetime.utcnow().isoformat(),
                'summary': stats,
                'organizations_needing_attention': attention_needed,
                'total_issues': len(attention_needed),
                'recommendations': self._get_recommendations(stats, attention_needed)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating connection report: {str(e)}")
            return {
                'error': str(e),
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def _get_recommendations(self, stats: Dict, attention_needed: List) -> List[str]:
        """Generate recommendations based on connection status"""
        recommendations = []
        
        if stats.get('expired', 0) > 0:
            recommendations.append(
                f"{stats['expired']} organization(s) have expired Epic tokens and need re-authentication"
            )
        
        if stats.get('expiring_soon', 0) > 0:
            recommendations.append(
                f"{stats['expiring_soon']} organization(s) have tokens expiring soon - proactive renewal recommended"
            )
        
        if stats.get('disconnected', 0) > 0:
            recommendations.append(
                f"{stats['disconnected']} organization(s) are not connected to Epic - check credentials and network"
            )
        
        high_retry_orgs = [org for org in attention_needed if org['retry_count'] > 3]
        if high_retry_orgs:
            recommendations.append(
                f"{len(high_retry_orgs)} organization(s) have high retry counts - investigate persistent connection issues"
            )
        
        if not recommendations:
            recommendations.append("All Epic connections are healthy")
        
        return recommendations


def get_connection_monitor() -> EpicConnectionMonitor:
    """Factory function to get connection monitor instance"""
    return EpicConnectionMonitor()
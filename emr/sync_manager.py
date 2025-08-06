"""
EMR Synchronization Manager with Selective Refresh Integration
Handles FHIR data synchronization and triggers selective updates
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from core.selective_refresh import SelectiveRefreshManager
from models import Patient, Document, ScreeningType, PatientCondition, db

class EMRSyncManager:
    """
    Manages EMR data synchronization with intelligent selective refresh
    Integrates with FHIR endpoints and triggers targeted screening updates
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.selective_refresh = SelectiveRefreshManager()
        
    def sync_from_emr(self, emr_endpoint: str, sync_config: Dict) -> Dict:
        """
        Main synchronization method with selective refresh
        
        Args:
            emr_endpoint: FHIR endpoint URL
            sync_config: Configuration for sync operation
            
        Returns:
            Comprehensive sync results with selective refresh data
        """
        try:
            self.logger.info(f"Starting EMR sync from {emr_endpoint}")
            
            # Fetch data from EMR
            emr_data = self._fetch_emr_data(emr_endpoint, sync_config)
            
            # Process and update local data
            sync_results = self._process_emr_data(emr_data)
            
            # Trigger selective refresh based on changes
            refresh_results = self.selective_refresh.sync_emr_changes(emr_data)
            
            # Combine results
            combined_results = {
                'sync_timestamp': datetime.utcnow().isoformat(),
                'emr_endpoint': emr_endpoint,
                'data_sync': sync_results,
                'selective_refresh': refresh_results,
                'total_affected_screenings': refresh_results.get('total_regenerated', 0),
                'preserved_screenings': refresh_results.get('preserved_screenings', 0),
                'efficiency_ratio': self._calculate_efficiency_ratio(refresh_results)
            }
            
            self.logger.info(f"EMR sync completed successfully: {combined_results['total_affected_screenings']} screenings updated")
            return combined_results
            
        except Exception as e:
            self.logger.error(f"EMR sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_incremental_changes(self, changes_data: Dict) -> Dict:
        """
        Handle incremental changes from EMR (webhooks, real-time updates)
        
        Args:
            changes_data: Incremental change data from EMR
            
        Returns:
            Results of selective refresh operation
        """
        try:
            self.logger.info("Processing incremental EMR changes")
            
            # Format changes for selective refresh
            formatted_changes = self._format_incremental_changes(changes_data)
            
            # Trigger selective refresh
            refresh_results = self.selective_refresh.sync_emr_changes(formatted_changes)
            
            return {
                'success': True,
                'change_type': 'incremental',
                'timestamp': datetime.utcnow().isoformat(),
                **refresh_results
            }
            
        except Exception as e:
            self.logger.error(f"Incremental sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_emr_data(self, endpoint: str, config: Dict) -> Dict:
        """
        Fetch data from FHIR EMR endpoint
        This would implement actual FHIR API calls in production
        """
        # Placeholder for FHIR API integration
        # In production, this would:
        # 1. Authenticate with EMR system
        # 2. Fetch Patient resources
        # 3. Fetch DocumentReference resources
        # 4. Fetch Condition resources
        # 5. Fetch any custom screening configuration
        
        return {
            'patients': self._fetch_patient_data(endpoint, config),
            'documents': self._fetch_document_data(endpoint, config),
            'patient_conditions': self._fetch_condition_data(endpoint, config),
            'screening_types': self._fetch_screening_config(endpoint, config)
        }
    
    def _fetch_patient_data(self, endpoint: str, config: Dict) -> List[Dict]:
        """Fetch patient data from FHIR Patient resources"""
        # Placeholder implementation
        # Would implement FHIR Patient resource queries
        return []
    
    def _fetch_document_data(self, endpoint: str, config: Dict) -> List[Dict]:
        """Fetch document data from FHIR DocumentReference resources"""
        # Placeholder implementation  
        # Would implement FHIR DocumentReference queries
        return []
    
    def _fetch_condition_data(self, endpoint: str, config: Dict) -> List[Dict]:
        """Fetch condition data from FHIR Condition resources"""
        # Placeholder implementation
        # Would implement FHIR Condition resource queries
        return []
    
    def _fetch_screening_config(self, endpoint: str, config: Dict) -> List[Dict]:
        """Fetch screening configuration from EMR custom resources"""
        # Placeholder implementation
        # Would fetch any EMR-specific screening configurations
        return []
    
    def _process_emr_data(self, emr_data: Dict) -> Dict:
        """Process and update local database with EMR data"""
        results = {
            'patients_processed': 0,
            'documents_processed': 0,
            'conditions_processed': 0,
            'screening_types_processed': 0
        }
        
        try:
            # Process patients
            if 'patients' in emr_data:
                results['patients_processed'] = self._process_patients(emr_data['patients'])
            
            # Process documents  
            if 'documents' in emr_data:
                results['documents_processed'] = self._process_documents(emr_data['documents'])
            
            # Process conditions
            if 'patient_conditions' in emr_data:
                results['conditions_processed'] = self._process_conditions(emr_data['patient_conditions'])
            
            # Process screening types
            if 'screening_types' in emr_data:
                results['screening_types_processed'] = self._process_screening_types(emr_data['screening_types'])
            
            db.session.commit()
            return results
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def _process_patients(self, patient_data: List[Dict]) -> int:
        """Process patient data and update database"""
        processed_count = 0
        
        for patient_info in patient_data:
            try:
                # Update or create patient record
                patient = self._update_or_create_patient(patient_info)
                if patient:
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing patient {patient_info.get('id', 'unknown')}: {str(e)}")
        
        return processed_count
    
    def _process_documents(self, document_data: List[Dict]) -> int:
        """Process document data and update database"""
        processed_count = 0
        
        for doc_info in document_data:
            try:
                # Update or create document record
                document = self._update_or_create_document(doc_info)
                if document:
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing document {doc_info.get('id', 'unknown')}: {str(e)}")
        
        return processed_count
    
    def _process_conditions(self, condition_data: List[Dict]) -> int:
        """Process patient condition data and update database"""
        processed_count = 0
        
        for condition_info in condition_data:
            try:
                # Update or create condition record
                condition = self._update_or_create_condition(condition_info)
                if condition:
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing condition {condition_info.get('id', 'unknown')}: {str(e)}")
        
        return processed_count
    
    def _process_screening_types(self, screening_type_data: List[Dict]) -> int:
        """Process screening type configuration from EMR"""
        processed_count = 0
        
        for type_info in screening_type_data:
            try:
                # Update or create screening type
                screening_type = self._update_or_create_screening_type(type_info)
                if screening_type:
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing screening type {type_info.get('id', 'unknown')}: {str(e)}")
        
        return processed_count
    
    def _update_or_create_patient(self, patient_data: Dict) -> Optional[Patient]:
        """Update existing patient or create new one"""
        # Implementation for patient CRUD operations
        # Would handle FHIR Patient resource mapping
        pass
    
    def _update_or_create_document(self, doc_data: Dict) -> Optional[Document]:
        """Update existing document or create new one"""
        # Implementation for document CRUD operations
        # Would handle FHIR DocumentReference resource mapping
        pass
    
    def _update_or_create_condition(self, condition_data: Dict) -> Optional[PatientCondition]:
        """Update existing condition or create new one"""
        # Implementation for condition CRUD operations
        # Would handle FHIR Condition resource mapping
        pass
    
    def _update_or_create_screening_type(self, type_data: Dict) -> Optional[ScreeningType]:
        """Update existing screening type or create new one"""
        # Implementation for screening type CRUD operations
        # Would handle EMR-specific screening configuration
        pass
    
    def _format_incremental_changes(self, changes_data: Dict) -> Dict:
        """Format incremental change data for selective refresh"""
        # Transform incoming change data into standard format
        formatted = {
            'patients': changes_data.get('patients', []),
            'documents': changes_data.get('documents', []),
            'patient_conditions': changes_data.get('conditions', []),
            'screening_types': changes_data.get('screening_types', [])
        }
        
        return formatted
    
    def _calculate_efficiency_ratio(self, refresh_results: Dict) -> float:
        """Calculate efficiency ratio of selective refresh"""
        total_regenerated = refresh_results.get('total_regenerated', 0)
        preserved = refresh_results.get('preserved_screenings', 0)
        
        total_screenings = total_regenerated + preserved
        
        if total_screenings == 0:
            return 1.0
        
        # Efficiency ratio: higher is better (more screenings preserved)
        efficiency = preserved / total_screenings
        return round(efficiency, 3)


class EMRChangeListener:
    """
    Handles real-time EMR change notifications
    Integrates with EMR webhooks or message queues
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sync_manager = EMRSyncManager()
    
    def handle_emr_webhook(self, webhook_data: Dict) -> Dict:
        """Handle incoming EMR webhook notifications"""
        try:
            # Parse webhook data
            change_type = webhook_data.get('type', 'unknown')
            resource_type = webhook_data.get('resource_type', 'unknown')
            
            self.logger.info(f"Received EMR webhook: {change_type} for {resource_type}")
            
            # Convert webhook to incremental change format
            incremental_changes = self._parse_webhook_to_changes(webhook_data)
            
            # Trigger selective refresh
            results = self.sync_manager.sync_incremental_changes(incremental_changes)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error handling EMR webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _parse_webhook_to_changes(self, webhook_data: Dict) -> Dict:
        """Parse webhook data into standard change format"""
        # Implementation depends on EMR webhook format
        # This would map EMR-specific webhook format to our change structure
        
        resource_type = webhook_data.get('resource_type')
        change_type = webhook_data.get('type')  # create, update, delete
        
        changes = {
            'patients': [],
            'documents': [],
            'conditions': [],
            'screening_types': []
        }
        
        # Map resource types to our categories
        if resource_type == 'Patient':
            changes['patients'].append(webhook_data.get('resource', {}))
        elif resource_type == 'DocumentReference':
            changes['documents'].append(webhook_data.get('resource', {}))
        elif resource_type == 'Condition':
            changes['conditions'].append(webhook_data.get('resource', {}))
        
        return changes
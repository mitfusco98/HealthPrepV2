"""
Epic FHIR Service Layer
Handles FHIR API operations, token management, and Epic integration
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from flask import session, current_app
from flask_login import current_user

from emr.fhir_client import FHIRClient
from emr.epic_integration import EpicScreeningIntegration
from models import db, Patient, FHIRDocument, Organization, ScreeningType
from routes.oauth_routes import get_epic_fhir_client

logger = logging.getLogger(__name__)


class EpicFHIRService:
    """Service layer for Epic FHIR operations with enhanced token management"""
    
    def __init__(self, organization_id: int = None):
        self.organization_id = organization_id or (current_user.org_id if current_user and current_user.is_authenticated else None)
        self.fhir_client = None
        self.organization = None
        
        if self.organization_id:
            self.organization = Organization.query.get(self.organization_id)
            
            # Try to get authenticated client first
            self.fhir_client = get_epic_fhir_client()
            
            # If no authenticated client, create basic client with org config
            if not self.fhir_client and self.organization and self.organization.epic_client_id:
                from emr.fhir_client import FHIRClient
                epic_config = {
                    'epic_client_id': self.organization.epic_client_id,
                    'epic_client_secret': self.organization.epic_client_secret,
                    'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
                }
                self.fhir_client = FHIRClient(epic_config, organization=self.organization)
    
    def ensure_authenticated(self) -> bool:
        """Ensure FHIR client is authenticated and tokens are valid"""
        if not self.fhir_client:
            logger.error("No FHIR client available - OAuth2 authentication required")
            return False
        
        if not self.fhir_client.access_token:
            logger.error("No access token available - OAuth2 authentication required")
            return False
        
        # Check if token is expired
        if self.fhir_client.token_expires and datetime.now() >= self.fhir_client.token_expires:
            logger.info("Access token expired, attempting refresh")
            if not self.fhir_client.refresh_access_token():
                logger.error("Failed to refresh access token")
                return False
            
            # Update session with new tokens
            session['epic_access_token'] = self.fhir_client.access_token
            if self.fhir_client.refresh_token:
                session['epic_refresh_token'] = self.fhir_client.refresh_token
            expires_in = int((self.fhir_client.token_expires - datetime.now()).total_seconds())
            session['epic_token_expires'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        return True
    
    def sync_patient_from_epic(self, epic_patient_id: str) -> Optional[Patient]:
        """
        Sync patient data from Epic FHIR and create/update local record
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Fetch patient from Epic
            fhir_patient = self.fhir_client.get_patient(epic_patient_id)
            if not fhir_patient:
                logger.error(f"Patient not found in Epic: {epic_patient_id}")
                return None
            
            # Find existing patient or create new one
            patient = Patient.query.filter_by(
                epic_patient_id=epic_patient_id,
                org_id=self.organization_id
            ).first()
            
            if not patient:
                # Create new patient from FHIR data
                patient = self._create_patient_from_fhir(fhir_patient)
            else:
                # Update existing patient
                patient.update_from_fhir(fhir_patient)
            
            db.session.add(patient)
            db.session.commit()
            
            logger.info(f"Successfully synced patient {epic_patient_id} from Epic")
            return patient
            
        except Exception as e:
            logger.error(f"Error syncing patient from Epic: {str(e)}")
            db.session.rollback()
            raise
    
    def _create_patient_from_fhir(self, fhir_patient: dict) -> Patient:
        """Create new Patient record from FHIR Patient resource"""
        patient = Patient()
        patient.org_id = self.organization_id
        patient.epic_patient_id = fhir_patient.get('id')
        
        # Extract MRN from identifiers
        if 'identifier' in fhir_patient:
            for identifier in fhir_patient['identifier']:
                if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                    patient.mrn = identifier.get('value')
                    break
        
        if not patient.mrn:
            patient.mrn = f"EPIC_{fhir_patient.get('id')}"
        
        # Update from FHIR data
        patient.update_from_fhir(fhir_patient)
        
        return patient
    
    def sync_patient_documents(self, patient: Patient) -> List[FHIRDocument]:
        """
        Sync patient documents from Epic DocumentReference resources
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        if not patient.epic_patient_id:
            logger.warning(f"Patient {patient.id} has no Epic patient ID")
            return []
        
        try:
            # Fetch documents from Epic
            document_references = self.fhir_client.get_patient_documents(patient.epic_patient_id)
            synced_documents = []
            
            for doc_ref in document_references:
                fhir_doc = self._sync_document_reference(patient, doc_ref)
                if fhir_doc:
                    synced_documents.append(fhir_doc)
            
            db.session.commit()
            logger.info(f"Synced {len(synced_documents)} documents for patient {patient.id}")
            return synced_documents
            
        except Exception as e:
            logger.error(f"Error syncing documents for patient {patient.id}: {str(e)}")
            db.session.rollback()
            raise
    
    def _sync_document_reference(self, patient: Patient, doc_ref: dict) -> Optional[FHIRDocument]:
        """Sync individual DocumentReference to FHIRDocument"""
        epic_doc_id = doc_ref.get('id')
        if not epic_doc_id:
            return None
        
        # Find existing document or create new one
        fhir_doc = FHIRDocument.query.filter_by(
            epic_document_id=epic_doc_id,
            org_id=self.organization_id
        ).first()
        
        if not fhir_doc:
            fhir_doc = FHIRDocument()
            fhir_doc.patient_id = patient.id
            fhir_doc.org_id = self.organization_id
            fhir_doc.epic_document_id = epic_doc_id
        
        # Update from FHIR data
        fhir_doc.update_from_fhir(doc_ref)
        
        db.session.add(fhir_doc)
        return fhir_doc
    
    def write_prep_sheet_to_epic(self, patient: Patient, prep_sheet_content: str, 
                                screening_types: List[ScreeningType]) -> Optional[str]:
        """
        Write preparation sheet back to Epic as DocumentReference
        Returns Epic DocumentReference ID if successful
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Create FHIR DocumentReference for prep sheet
            document_reference = self._create_prep_sheet_document_reference(
                patient, prep_sheet_content, screening_types
            )
            
            # Post to Epic FHIR server
            result = self.fhir_client.create_document_reference(document_reference)
            
            if result and 'id' in result:
                epic_doc_id = result['id']
                
                # Create local FHIRDocument record
                fhir_doc = FHIRDocument()
                fhir_doc.patient_id = patient.id
                fhir_doc.org_id = self.organization_id
                fhir_doc.epic_document_id = epic_doc_id
                fhir_doc.update_from_fhir(result)
                fhir_doc.mark_processed('completed', ocr_text=prep_sheet_content)
                
                db.session.add(fhir_doc)
                db.session.commit()
                
                logger.info(f"Successfully wrote prep sheet to Epic for patient {patient.id}: {epic_doc_id}")
                return epic_doc_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error writing prep sheet to Epic: {str(e)}")
            db.session.rollback()
            raise
    
    def _create_prep_sheet_document_reference(self, patient: Patient, content: str, 
                                           screening_types: List[ScreeningType]) -> dict:
        """Create FHIR DocumentReference resource for prep sheet"""
        import base64
        
        # Generate screening type summary
        screening_names = [st.name for st in screening_types]
        title = f"Medical Screening Preparation Sheet - {', '.join(screening_names[:3])}"
        if len(screening_names) > 3:
            title += f" (+{len(screening_names) - 3} more)"
        
        document_reference = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Provider-unspecified progress note"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "LP173421-1",
                            "display": "Clinical note"
                        }
                    ]
                }
            ],
            "subject": {
                "reference": f"Patient/{patient.epic_patient_id}"
            },
            "date": datetime.utcnow().isoformat() + "Z",
            "author": [
                {
                    "display": f"HealthPrep System - {self.organization.name}"
                }
            ],
            "description": title,
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": base64.b64encode(content.encode('utf-8')).decode('ascii'),
                        "title": title,
                        "creation": datetime.utcnow().isoformat() + "Z"
                    }
                }
            ]
        }
        
        return document_reference
    
    def process_fhir_documents_for_screening(self, patient: Patient, 
                                           screening_types: List[ScreeningType]) -> List[FHIRDocument]:
        """
        Process FHIR documents for screening relevance using OCR and keyword matching
        """
        if not patient.fhir_documents:
            return []
        
        relevant_documents = []
        
        for fhir_doc in patient.fhir_documents:
            try:
                # Download and process document content if not already processed
                if not fhir_doc.is_processed and fhir_doc.content_url:
                    self._download_and_process_document(fhir_doc)
                
                # Check relevance for screening types
                for screening_type in screening_types:
                    if fhir_doc.is_relevant_for_screening(screening_type):
                        # Calculate relevance score based on keyword matching
                        relevance_score = self._calculate_relevance_score(fhir_doc, screening_type)
                        
                        if relevance_score > 0.3:  # Threshold for relevance
                            fhir_doc.relevance_score = relevance_score
                            relevant_documents.append(fhir_doc)
                
            except Exception as e:
                logger.error(f"Error processing FHIR document {fhir_doc.id}: {str(e)}")
                fhir_doc.mark_processed('failed', error=str(e))
        
        db.session.commit()
        return relevant_documents
    
    def _download_and_process_document(self, fhir_doc: FHIRDocument):
        """Download document content from Epic and extract text"""
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Download document content
            content = self.fhir_client.get_document_content(fhir_doc.content_url)
            
            if content and fhir_doc.is_pdf:
                # Use OCR to extract text from PDF
                from ocr.pdf_processor import PDFProcessor
                processor = PDFProcessor()
                ocr_result = processor.process_pdf_content(content)
                fhir_doc.ocr_text = ocr_result.get('text', '')
            elif content:
                fhir_doc.ocr_text = content.decode('utf-8', errors='ignore')
            
            fhir_doc.mark_processed('completed', ocr_text=fhir_doc.ocr_text)
            fhir_doc.last_accessed = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error downloading document {fhir_doc.epic_document_id}: {str(e)}")
            fhir_doc.mark_processed('failed', error=str(e))
    
    def _calculate_relevance_score(self, fhir_doc: FHIRDocument, screening_type: ScreeningType) -> float:
        """Calculate relevance score based on keyword matching"""
        if not fhir_doc.ocr_text or not screening_type.keywords_list:
            return 0.0
        
        from utils.fuzzy_matching import FuzzyMatcher
        matcher = FuzzyMatcher()
        
        text_lower = fhir_doc.ocr_text.lower()
        total_keywords = len(screening_type.keywords_list)
        matched_keywords = 0
        
        for keyword in screening_type.keywords_list:
            if matcher.fuzzy_match(keyword.lower(), text_lower, threshold=0.8):
                matched_keywords += 1
        
        return matched_keywords / total_keywords if total_keywords > 0 else 0.0
    
    def get_patient_screening_data(self, patient: Patient, 
                                 screening_types: List[ScreeningType]) -> Dict[str, Any]:
        """
        Get comprehensive screening data for patient from Epic FHIR
        Implements Epic's blueprint data retrieval sequence
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        if not patient.epic_patient_id:
            raise Exception(f"Patient {patient.id} has no Epic patient ID")
        
        try:
            # Use Epic integration for comprehensive data retrieval
            epic_integration = EpicScreeningIntegration(self.organization_id)
            epic_integration.fhir_client = self.fhir_client
            
            screening_type_names = [st.name for st in screening_types]
            screening_data = epic_integration.get_screening_data_for_patient(
                patient.mrn, screening_type_names
            )
            
            return screening_data
            
        except Exception as e:
            logger.error(f"Error getting screening data for patient {patient.id}: {str(e)}")
            raise
    
    def get_fhir_client(self):
        """
        Get the FHIR client instance for this service
        Returns the authenticated FHIR client or None if not available
        """
        return self.fhir_client


def get_epic_fhir_service(organization_id: int = None) -> EpicFHIRService:
    """Factory function to get Epic FHIR service instance"""
    return EpicFHIRService(organization_id)
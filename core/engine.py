"""
Core screening engine that orchestrates the screening process with fuzzy detection
"""
from app import db
from models import Patient, ScreeningType, Screening, Document
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria
from .fuzzy_detection import FuzzyDetectionEngine
from emr.epic_integration import EpicScreeningIntegration
from datetime import datetime, date
import logging
from flask_login import current_user

class ScreeningEngine:
    """Main screening engine that coordinates all screening operations"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        self.fuzzy_engine = FuzzyDetectionEngine()
        self.logger = logging.getLogger(__name__)
        self.epic_integration = None
    
    def refresh_all_screenings(self):
        """Refresh all patient screenings based on current criteria and sync with Epic if available"""
        updated_count = 0
        
        try:
            # Initialize Epic integration if user is authenticated and has access
            self._initialize_epic_integration()
            
            patients = Patient.query.all()
            
            for patient in patients:
                updated_count += self.refresh_patient_screenings(patient.id)
            
            db.session.commit()
            self.logger.info(f"Successfully refreshed {updated_count} screenings")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error refreshing screenings: {str(e)}")
            raise
        
        return updated_count
    
    def refresh_patient_screenings(self, patient_id):
        """Refresh screenings for a specific patient and sync with Epic if available"""
        patient = Patient.query.get(patient_id)
        if not patient:
            return 0
        
        updated_count = 0
        
        try:
            # Sync with Epic if integration is available
            if self.epic_integration and patient.mrn:
                self._sync_patient_with_epic(patient)
            
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            for screening_type in screening_types:
                if self.criteria.is_patient_eligible(patient, screening_type):
                    screening = self._get_or_create_screening(patient, screening_type)
                    if self._update_screening_status(screening):
                        updated_count += 1
                        
        except Exception as e:
            self.logger.error(f"Error refreshing patient {patient_id} screenings: {str(e)}")
            # Continue with local refresh even if Epic sync fails
            
        return updated_count
    
    def process_new_document(self, document_id):
        """Process a new document and update relevant screenings"""
        document = Document.query.get(document_id)
        if not document or not document.patient:
            return
        
        # Find matching screenings for this document
        matches = self.matcher.find_document_matches(document)
        
        # Update screening statuses based on matches
        for screening_id, confidence in matches:
            screening = Screening.query.get(screening_id)
            if screening:
                self._update_screening_from_document(screening, document, confidence)
        
        db.session.commit()
    
    def _get_or_create_screening(self, patient, screening_type):
        """Get existing screening or create new one"""
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                org_id=patient.org_id,
                status='due'
            )
            db.session.add(screening)
        
        return screening
    
    def _update_screening_status(self, screening):
        """Update screening status based on documents and criteria"""
        # Find matching documents
        matches = self.matcher.find_screening_matches(screening)
        
        if matches:
            # Get the most recent matching document
            latest_match = max(matches, key=lambda x: x['document_date'] or date.min)
            
            # Calculate status based on frequency and last completion
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                latest_match['document_date']
            )
            
            if new_status != screening.status:
                screening.status = new_status
                screening.last_completed_date = latest_match['document_date']
                screening.updated_at = datetime.utcnow()
                return True
        
        return False
    
    def _initialize_epic_integration(self):
        """Initialize Epic integration if available"""
        try:
            # Only initialize if user is logged in and has organization with Epic connection
            if current_user and current_user.is_authenticated and hasattr(current_user, 'org_id'):
                from models import EpicCredentials
                org = current_user.organization
                
                # Check if organization has Epic credentials
                epic_creds = EpicCredentials.query.filter_by(org_id=current_user.org_id).first()
                if epic_creds and epic_creds.access_token and not (
                    epic_creds.token_expires_at and datetime.now() >= epic_creds.token_expires_at
                ):
                    self.epic_integration = EpicScreeningIntegration(current_user.org_id)
                    self.logger.info(f"Epic integration initialized for organization {current_user.org_id}")
                else:
                    self.logger.info(f"No valid Epic credentials found for organization {current_user.org_id}")
                    self.epic_integration = None
        except Exception as e:
            self.logger.warning(f"Could not initialize Epic integration: {str(e)}")
            self.epic_integration = None
    
    def _sync_patient_with_epic(self, patient):
        """Sync patient data with Epic FHIR"""
        try:
            if not self.epic_integration:
                return
            
            # Get screening types to determine what data to fetch
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            screening_data = [{
                'name': st.name,
                'fhir_mappings': st.fhir_mappings or {}
            } for st in screening_types]
            
            # Fetch Epic data for this patient
            epic_data = self.epic_integration.get_screening_relevant_data(
                patient.mrn, screening_data
            )
            
            if epic_data and epic_data.get('success'):
                # Process the Epic data and create/update documents
                self._process_epic_documents(patient, epic_data)
                self.logger.info(f"Successfully synced Epic data for patient {patient.mrn}")
            else:
                self.logger.warning(f"No Epic data retrieved for patient {patient.mrn}")
                
        except Exception as e:
            self.logger.error(f"Error syncing patient {patient.mrn} with Epic: {str(e)}")
    
    def _process_epic_documents(self, patient, epic_data):
        """Process Epic FHIR documents and create database records"""
        try:
            from models import FHIRDocument
            
            # Process conditions
            conditions = epic_data.get('conditions', [])
            for condition in conditions:
                self._create_fhir_document(patient, condition, 'Condition')
            
            # Process observations  
            observations = epic_data.get('observations', [])
            for observation in observations:
                self._create_fhir_document(patient, observation, 'Observation')
            
            # Process document references
            documents = epic_data.get('documents', [])
            for document in documents:
                self._create_fhir_document(patient, document, 'DocumentReference')
                
        except Exception as e:
            self.logger.error(f"Error processing Epic documents for patient {patient.id}: {str(e)}")
    
    def _create_fhir_document(self, patient, fhir_resource, resource_type):
        """Create or update FHIR document record"""
        try:
            from models import FHIRDocument
            
            # Check if document already exists
            fhir_id = fhir_resource.get('id')
            existing_doc = FHIRDocument.query.filter_by(
                patient_id=patient.id,
                fhir_id=fhir_id,
                resource_type=resource_type
            ).first()
            
            if not existing_doc:
                # Create new FHIR document
                fhir_doc = FHIRDocument(
                    patient_id=patient.id,
                    fhir_id=fhir_id,
                    resource_type=resource_type,
                    resource_data=fhir_resource,
                    last_updated=datetime.utcnow()
                )
                db.session.add(fhir_doc)
                self.logger.debug(f"Created new FHIR {resource_type} document for patient {patient.id}")
            else:
                # Update existing document
                existing_doc.resource_data = fhir_resource
                existing_doc.last_updated = datetime.utcnow()
                self.logger.debug(f"Updated FHIR {resource_type} document for patient {patient.id}")
                
        except Exception as e:
            self.logger.error(f"Error creating/updating FHIR document: {str(e)}")
    
    def _update_screening_from_document(self, screening, document, confidence):
        """Update a specific screening based on a document match"""
        # Create or update document match record
        from models import ScreeningDocumentMatch
        
        match = ScreeningDocumentMatch.query.filter_by(
            screening_id=screening.id,
            document_id=document.id
        ).first()
        
        if not match:
            match = ScreeningDocumentMatch(
                screening_id=screening.id,
                document_id=document.id,
                match_confidence=confidence
            )
            db.session.add(match)
        else:
            match.match_confidence = confidence
        
        # Update screening status
        if document.document_date:
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                document.document_date
            )
            
            if new_status != screening.status:
                screening.status = new_status
                screening.last_completed_date = document.document_date
                screening.updated_at = datetime.utcnow()
    
    def get_screening_summary(self, patient_id):
        """Get comprehensive screening summary for a patient"""
        screenings = Screening.query.filter_by(patient_id=patient_id).join(ScreeningType).all()
        
        summary = {
            'total': len(screenings),
            'due': len([s for s in screenings if s.status == 'due']),
            'due_soon': len([s for s in screenings if s.status == 'due_soon']),
            'complete': len([s for s in screenings if s.status == 'complete']),
            'screenings': []
        }
        
        for screening in screenings:
            matches = self.matcher.find_screening_matches(screening)
            summary['screenings'].append({
                'screening': screening,
                'matches': matches
            })
        
        return summary
    
    def analyze_screening_keywords(self, screening_type_id):
        """Analyze and optimize keywords for a screening type using fuzzy detection"""
        screening_type = ScreeningType.query.get(screening_type_id)
        if not screening_type:
            return None
        
        # Get related documents for analysis
        related_documents = []
        screenings = Screening.query.filter_by(screening_type_id=screening_type_id).all()
        
        for screening in screenings:
            matches = self.matcher.find_screening_matches(screening)
            for match in matches:
                related_documents.append(match['document'])
        
        # Analyze current keywords effectiveness
        current_keywords = screening_type.keywords_list
        keyword_analysis = {}
        
        for keyword in current_keywords:
            document_texts = [f"{doc.filename or ''} {doc.ocr_text or ''}" 
                             for doc in related_documents if doc.filename or doc.ocr_text]
            
            relevance = self.fuzzy_engine.validate_keyword_relevance(keyword, document_texts)
            keyword_analysis[keyword] = {
                'relevance': relevance,
                'effective': relevance > 0.5
            }
        
        # Get keyword suggestions
        suggested_keywords = self.matcher.suggest_keywords_for_screening(
            screening_type_id, related_documents
        )
        
        return {
            'screening_type': screening_type.name,
            'current_keywords': keyword_analysis,
            'suggested_keywords': suggested_keywords,
            'total_related_documents': len(related_documents),
            'recommendations': self._generate_keyword_recommendations(keyword_analysis, suggested_keywords)
        }
    
    def _generate_keyword_recommendations(self, keyword_analysis, suggested_keywords):
        """Generate actionable keyword recommendations"""
        recommendations = []
        
        # Identify ineffective keywords
        ineffective_keywords = [kw for kw, analysis in keyword_analysis.items() 
                               if not analysis['effective']]
        
        if ineffective_keywords:
            recommendations.append({
                'type': 'remove',
                'message': f"Consider removing these ineffective keywords: {', '.join(ineffective_keywords)}",
                'keywords': ineffective_keywords
            })
        
        # Recommend new keywords
        if suggested_keywords:
            recommendations.append({
                'type': 'add',
                'message': f"Consider adding these relevant keywords: {', '.join(suggested_keywords[:5])}",
                'keywords': suggested_keywords[:5]
            })
        
        # Check for keyword gaps
        high_relevance_keywords = [kw for kw, analysis in keyword_analysis.items() 
                                  if analysis['relevance'] > 0.8]
        
        if len(high_relevance_keywords) < 3:
            recommendations.append({
                'type': 'optimize',
                'message': "Consider expanding keyword coverage for better document matching",
                'keywords': []
            })
        
        return recommendations
    
    def optimize_all_screening_keywords(self):
        """Optimize keywords for all active screening types"""
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        optimization_results = []
        
        for screening_type in screening_types:
            try:
                analysis = self.analyze_screening_keywords(screening_type.id)
                if analysis:
                    optimization_results.append(analysis)
                    
                    # Auto-apply high-confidence recommendations
                    auto_applied = self._auto_apply_recommendations(
                        screening_type, analysis['recommendations']
                    )
                    
                    if auto_applied:
                        self.logger.info(f"Auto-applied keyword optimizations for {screening_type.name}")
                        
            except Exception as e:
                self.logger.error(f"Error optimizing keywords for {screening_type.name}: {str(e)}")
        
        if optimization_results:
            db.session.commit()
        
        return optimization_results
    
    def _auto_apply_recommendations(self, screening_type, recommendations):
        """Automatically apply high-confidence keyword recommendations"""
        applied = False
        current_keywords = screening_type.keywords_list.copy()
        
        for rec in recommendations:
            if rec['type'] == 'remove' and len(current_keywords) > 2:
                # Only remove if we have enough keywords left
                for keyword in rec['keywords'][:2]:  # Remove max 2 at a time
                    if keyword in current_keywords:
                        current_keywords.remove(keyword)
                        applied = True
            
            elif rec['type'] == 'add' and len(current_keywords) < 10:
                # Add high-confidence suggestions
                for keyword in rec['keywords'][:3]:  # Add max 3 at a time
                    if keyword not in current_keywords:
                        current_keywords.append(keyword)
                        applied = True
        
        if applied:
            # Update the screening type keywords
            import json
            screening_type.keywords = json.dumps(current_keywords)
        
        return applied

"""
Core screening engine that orchestrates the screening process with fuzzy detection
"""
from app import db
from models import Patient, ScreeningType, Screening, Document, Organization
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria
from .fuzzy_detection import FuzzyDetectionEngine
from emr.epic_integration import EpicScreeningIntegration
from services.appointment_prioritization import AppointmentBasedPrioritization
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
    
    def refresh_all_screenings(self, org_id=None):
        """
        Refresh all patient screenings based on current criteria and sync with Epic if available
        Supports appointment-based prioritization to reduce workload
        
        Args:
            org_id: Organization ID to filter patients (optional)
        """
        updated_count = 0
        
        try:
            # Initialize Epic integration if user is authenticated and has access
            self._initialize_epic_integration()
            
            # If org_id provided, check if appointment prioritization is enabled
            if org_id:
                organization = Organization.query.get(org_id)
                
                if organization and organization.appointment_based_prioritization:
                    self.logger.info("Appointment-based prioritization is ENABLED - processing priority patients first")
                    
                    # Use appointment-based prioritization
                    prioritization_service = AppointmentBasedPrioritization(org_id)
                    priority_patient_ids = prioritization_service.get_priority_patients()
                    
                    if priority_patient_ids:
                        self.logger.info(f"Processing {len(priority_patient_ids)} priority patients with upcoming appointments")
                        
                        # Process priority patients first - mark as NOT dormant
                        for patient_id in priority_patient_ids:
                            updated_count += self.refresh_patient_screenings(patient_id)
                            # Mark all screenings for this patient as active (not dormant)
                            self._mark_patient_screenings_dormancy(patient_id, is_dormant=False)
                        
                        # Process non-scheduled patients if enabled
                        if organization.process_non_scheduled_patients:
                            self.logger.info("Processing non-scheduled patients (process_non_scheduled_patients is enabled)")
                            non_scheduled_ids = prioritization_service.get_non_scheduled_patients(
                                exclude_patient_ids=priority_patient_ids
                            )
                            
                            for patient_id in non_scheduled_ids:
                                updated_count += self.refresh_patient_screenings(patient_id)
                                # Mark processed non-scheduled patients as active too
                                self._mark_patient_screenings_dormancy(patient_id, is_dormant=False)
                        else:
                            # Mark non-scheduled patients as dormant (stale data)
                            non_scheduled_ids = prioritization_service.get_non_scheduled_patients(
                                exclude_patient_ids=priority_patient_ids
                            )
                            self.logger.info(f"Marking {len(non_scheduled_ids)} non-scheduled patients as dormant (process_non_scheduled_patients is disabled)")
                            for patient_id in non_scheduled_ids:
                                self._mark_patient_screenings_dormancy(patient_id, is_dormant=True)
                    else:
                        self.logger.info("No priority patients found - falling back to standard processing")
                        # Fall back to standard processing
                        patients = Patient.query.filter_by(org_id=org_id).all()
                        for patient in patients:
                            updated_count += self.refresh_patient_screenings(patient.id)
                else:
                    # Standard processing for org without prioritization
                    self.logger.info("Appointment-based prioritization is DISABLED - processing all patients")
                    patients = Patient.query.filter_by(org_id=org_id).all()
                    for patient in patients:
                        updated_count += self.refresh_patient_screenings(patient.id)
            else:
                # No org_id provided - process all patients (legacy behavior)
                self.logger.info("No org_id provided - processing all patients across all organizations")
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
    
    def refresh_patient_screenings(self, patient_id, force_refresh=False):
        """Refresh screenings for a specific patient and sync with Epic if available
        
        Args:
            patient_id: Patient ID to refresh
            force_refresh: If True, refresh all screenings regardless of criteria changes
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return 0
        
        updated_count = 0
        
        try:
            # Sync with Epic if integration is available
            if self.epic_integration and patient.mrn:
                self._sync_patient_with_epic(patient)
            
            # CRITICAL: Only get screening types from patient's organization
            screening_types = ScreeningType.query.filter_by(is_active=True, org_id=patient.org_id).all()
            
            for screening_type in screening_types:
                # Check if patient is eligible
                if self.criteria.is_patient_eligible(patient, screening_type):
                    screening = self._get_or_create_screening(patient, screening_type)
                    
                    # SELECTIVE REFRESH: Only reprocess if criteria changed or force refresh
                    if force_refresh or self._should_refresh_screening(screening, screening_type):
                        if self._update_screening_status(screening):
                            updated_count += 1
                    else:
                        self.logger.debug(f"Skipping {screening_type.name} for patient {patient_id} - no criteria changes")
                        
        except Exception as e:
            self.logger.error(f"Error refreshing patient {patient_id} screenings: {str(e)}")
            # Continue with local refresh even if Epic sync fails
            
        return updated_count
    
    def _mark_patient_screenings_dormancy(self, patient_id, is_dormant=True):
        """Mark all screenings for a patient as dormant or active
        
        Args:
            patient_id: Patient ID
            is_dormant: True to mark as dormant (stale), False to mark as active
        """
        from datetime import datetime
        screenings = Screening.query.filter_by(patient_id=patient_id).all()
        for screening in screenings:
            screening.is_dormant = is_dormant
            screening.last_processed = datetime.utcnow()
        self.logger.debug(f"Marked {len(screenings)} screenings for patient {patient_id} as {'dormant' if is_dormant else 'active'}")
    
    def _should_refresh_screening(self, screening: Screening, screening_type: ScreeningType) -> bool:
        """Determine if a screening needs to be refreshed based on criteria changes
        
        Args:
            screening: Existing screening record
            screening_type: Associated screening type
            
        Returns:
            True if refresh needed, False if can skip
        """
        # Always refresh if screening was never updated
        if not screening.updated_at:
            return True
        
        # Refresh if screening type criteria have changed since last update
        if screening_type.updated_at and screening_type.updated_at > screening.updated_at:
            self.logger.debug(f"Criteria changed for {screening_type.name}: {screening_type.updated_at} > {screening.updated_at}")
            return True
        
        # Check if patient has new documents since last screening update
        from models import Document, FHIRDocument
        
        new_manual_docs = Document.query.filter(
            Document.patient_id == screening.patient_id,
            Document.created_at > screening.updated_at
        ).count()
        
        new_fhir_docs = FHIRDocument.query.filter(
            FHIRDocument.patient_id == screening.patient_id,
            FHIRDocument.created_at > screening.updated_at
        ).count()
        
        if new_manual_docs > 0 or new_fhir_docs > 0:
            self.logger.debug(f"New documents found for patient {screening.patient_id}: {new_manual_docs} manual + {new_fhir_docs} FHIR")
            return True
        
        # No changes detected - safe to skip
        return False
    
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
            # Get the most recent matching document with safe date comparison
            def safe_date_key(match):
                """Safely extract and normalize date for comparison"""
                doc_date = match['document_date']
                if doc_date is None:
                    return date.min
                # Ensure we're comparing date objects, not datetime
                if hasattr(doc_date, 'date'):
                    return doc_date.date()
                return doc_date
            
            latest_match = max(matches, key=safe_date_key)
            
            # Calculate status based on frequency and last completion
            # Use document_date if available, otherwise fall back to created_at
            document_date = latest_match['document_date'] or latest_match['document'].created_at.date()
            
            # Ensure document_date is a date object, not datetime
            if hasattr(document_date, 'date'):
                document_date = document_date.date()
            
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                document_date
            )
            
            # Always update last_completed if we have a newer date
            status_changed = new_status != screening.status
            date_changed = (screening.last_completed is None or 
                          document_date > screening.last_completed)
            
            if status_changed or date_changed:
                screening.status = new_status
                screening.last_completed = document_date
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
            
            # Get screening types from patient's organization to determine what data to fetch
            screening_types = ScreeningType.query.filter_by(is_active=True, org_id=patient.org_id).all()
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
        
        # Update screening status with robust date fallback
        # Priority: document_date > created_at > current_date (for sandbox documents)
        from datetime import date
        document_date = getattr(document, 'document_date', None)
        if document_date is None:
            # Fallback to created_at if available
            if hasattr(document, 'created_at') and document.created_at:
                document_date = document.created_at.date()
            else:
                # Final fallback to current date for sandbox documents without dates
                document_date = date.today()
                self.logger.info(f"Using current date fallback for document {document.id} - sandbox document missing date")
        
        if document_date:
            # Ensure document_date is a date object, not datetime
            if hasattr(document_date, 'date'):
                document_date = document_date.date()
                
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                document_date
            )
            
            # Always update last_completed if we have a newer date
            status_changed = new_status != screening.status
            date_changed = (screening.last_completed is None or 
                          document_date > screening.last_completed)
            
            if status_changed or date_changed:
                screening.status = new_status
                screening.last_completed = document_date
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

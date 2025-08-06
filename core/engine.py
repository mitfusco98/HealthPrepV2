"""
Core screening engine that orchestrates the screening process with fuzzy detection
"""
from app import db
from models import Patient, ScreeningType, Screening, Document
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria
from .fuzzy_detection import FuzzyDetectionEngine
from datetime import datetime, date
import logging

class ScreeningEngine:
    """Main screening engine that coordinates all screening operations"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        self.fuzzy_engine = FuzzyDetectionEngine()
        self.logger = logging.getLogger(__name__)
    
    def refresh_all_screenings(self):
        """Refresh all patient screenings based on current criteria"""
        updated_count = 0
        
        try:
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
        """Refresh screenings for a specific patient"""
        patient = Patient.query.get(patient_id)
        if not patient:
            return 0
        
        updated_count = 0
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for screening_type in screening_types:
            if self.criteria.is_patient_eligible(patient, screening_type):
                screening = self._get_or_create_screening(patient, screening_type)
                if self._update_screening_status(screening):
                    updated_count += 1
        
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

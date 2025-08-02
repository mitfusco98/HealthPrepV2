"""
Converts FHIR bundles to internal data model
"""
import json
import logging
from datetime import datetime, date
from models import MedicalDocument, Patient
from app import db

class FHIRParser:
    
    def process_patient_data(self, patient_id, fhir_data):
        """Process FHIR data and create internal records"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                logging.error(f"Patient {patient_id} not found")
                return False
            
            # Process observations
            if fhir_data.get('observations'):
                self._process_observations(patient, fhir_data['observations'])
            
            # Process diagnostic reports
            if fhir_data.get('reports'):
                self._process_diagnostic_reports(patient, fhir_data['reports'])
            
            # Process conditions
            if fhir_data.get('conditions'):
                self._process_conditions(patient, fhir_data['conditions'])
            
            db.session.commit()
            return True
            
        except Exception as e:
            logging.error(f"Error processing FHIR data: {e}")
            db.session.rollback()
            return False
    
    def _process_observations(self, patient, observations_bundle):
        """Process FHIR observations and create document records"""
        if not observations_bundle.get('entry'):
            return
        
        for entry in observations_bundle['entry']:
            observation = entry.get('resource', {})
            
            if observation.get('resourceType') != 'Observation':
                continue
            
            try:
                # Extract observation data
                code_text = self._extract_code_text(observation.get('code', {}))
                value_text = self._extract_value_text(observation.get('value', {}))
                effective_date = self._parse_fhir_date(observation.get('effectiveDateTime'))
                
                # Create document record
                doc_content = f"Observation: {code_text}\nValue: {value_text}\nDate: {effective_date}"
                
                document = MedicalDocument(
                    patient_id=patient.id,
                    filename=f"lab_observation_{observation.get('id', 'unknown')}.txt",
                    document_type='lab',
                    ocr_text=doc_content,
                    ocr_confidence=1.0,  # FHIR data is structured, so high confidence
                    phi_filtered=False  # Will be filtered by PHI filter if needed
                )
                
                db.session.add(document)
                
            except Exception as e:
                logging.error(f"Error processing observation: {e}")
                continue
    
    def _process_diagnostic_reports(self, patient, reports_bundle):
        """Process FHIR diagnostic reports"""
        if not reports_bundle.get('entry'):
            return
        
        for entry in reports_bundle['entry']:
            report = entry.get('resource', {})
            
            if report.get('resourceType') != 'DiagnosticReport':
                continue
            
            try:
                # Extract report data
                category = self._extract_code_text(report.get('category', [{}])[0] if report.get('category') else {})
                code_text = self._extract_code_text(report.get('code', {}))
                conclusion = report.get('conclusion', '')
                effective_date = self._parse_fhir_date(report.get('effectiveDateTime'))
                
                # Determine document type based on category
                doc_type = self._map_report_category(category)
                
                # Create document content
                doc_content = f"Diagnostic Report: {code_text}\nCategory: {category}\nConclusion: {conclusion}\nDate: {effective_date}"
                
                document = MedicalDocument(
                    patient_id=patient.id,
                    filename=f"{doc_type}_report_{report.get('id', 'unknown')}.txt",
                    document_type=doc_type,
                    ocr_text=doc_content,
                    ocr_confidence=1.0,
                    phi_filtered=False
                )
                
                db.session.add(document)
                
            except Exception as e:
                logging.error(f"Error processing diagnostic report: {e}")
                continue
    
    def _process_conditions(self, patient, conditions_bundle):
        """Process FHIR conditions"""
        if not conditions_bundle.get('entry'):
            return
        
        # For now, we'll store conditions as documents for screening matching
        # In a full implementation, these would be stored in a separate conditions table
        
        for entry in conditions_bundle['entry']:
            condition = entry.get('resource', {})
            
            if condition.get('resourceType') != 'Condition':
                continue
            
            try:
                code_text = self._extract_code_text(condition.get('code', {}))
                onset_date = self._parse_fhir_date(condition.get('onsetDateTime'))
                clinical_status = condition.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '')
                
                doc_content = f"Condition: {code_text}\nStatus: {clinical_status}\nOnset: {onset_date}"
                
                document = MedicalDocument(
                    patient_id=patient.id,
                    filename=f"condition_{condition.get('id', 'unknown')}.txt",
                    document_type='condition',
                    ocr_text=doc_content,
                    ocr_confidence=1.0,
                    phi_filtered=False
                )
                
                db.session.add(document)
                
            except Exception as e:
                logging.error(f"Error processing condition: {e}")
                continue
    
    def _extract_code_text(self, code_data):
        """Extract human-readable text from FHIR code data"""
        if not code_data:
            return ""
        
        # Try display text first
        if code_data.get('text'):
            return code_data['text']
        
        # Try coding display
        if code_data.get('coding'):
            for coding in code_data['coding']:
                if coding.get('display'):
                    return coding['display']
                elif coding.get('code'):
                    return coding['code']
        
        return ""
    
    def _extract_value_text(self, value_data):
        """Extract human-readable value from FHIR value data"""
        if not value_data:
            return ""
        
        # Handle different value types
        if isinstance(value_data, dict):
            if 'valueQuantity' in value_data:
                qty = value_data['valueQuantity']
                return f"{qty.get('value', '')} {qty.get('unit', '')}"
            elif 'valueString' in value_data:
                return value_data['valueString']
            elif 'valueCodeableConcept' in value_data:
                return self._extract_code_text(value_data['valueCodeableConcept'])
        
        return str(value_data)
    
    def _parse_fhir_date(self, date_string):
        """Parse FHIR date string to Python date"""
        if not date_string:
            return ""
        
        try:
            # Handle different FHIR date formats
            if 'T' in date_string:
                dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M')
            else:
                dt = datetime.strptime(date_string, '%Y-%m-%d')
                return dt.strftime('%Y-%m-%d')
        except Exception as e:
            logging.error(f"Error parsing FHIR date {date_string}: {e}")
            return date_string
    
    def _map_report_category(self, category):
        """Map FHIR diagnostic report category to internal document type"""
        category_lower = category.lower()
        
        if 'lab' in category_lower or 'chemistry' in category_lower:
            return 'lab'
        elif 'imaging' in category_lower or 'radiology' in category_lower:
            return 'imaging'
        elif 'pathology' in category_lower:
            return 'pathology'
        else:
            return 'general'

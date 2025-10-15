"""
Epic FHIR Write-Back Service
Handles writing prep sheets back to Epic as DocumentReference resources
"""

import logging
import base64
import os
import json
from datetime import datetime
from io import BytesIO
from weasyprint import HTML, CSS
from flask import render_template_string
from emr.fhir_client import FHIRClient
from models import Patient, Organization, log_admin_event

logger = logging.getLogger(__name__)


class EpicWriteBackService:
    """Service for writing prep sheets to Epic as FHIR DocumentReference resources"""
    
    def __init__(self, organization_id):
        """Initialize with organization for Epic connection"""
        self.organization = Organization.query.get(organization_id)
        if not self.organization:
            raise ValueError(f"Organization {organization_id} not found")
        
        self.fhir_client = None
        self.logger = logger
        
        # Check for dry-run mode
        self.dry_run = os.environ.get('EPIC_DRY_RUN', 'false').lower() == 'true'
        if self.dry_run:
            self.logger.warning("⚠️  EPIC DRY-RUN MODE ENABLED - No actual writes to Epic will occur")
    
    def _initialize_fhir_client(self):
        """Initialize FHIR client with Epic credentials"""
        if not self.organization.epic_client_id:
            raise ValueError("Epic credentials not configured for organization")
        
        self.fhir_client = FHIRClient(
            organization=self.organization,
            client_id=self.organization.epic_client_id,
            client_secret=self.organization.epic_client_secret,
            base_url=self.organization.epic_fhir_url
        )
        
        # Verify connection and refresh token if needed
        if not self._verify_epic_connection():
            raise ConnectionError("Epic connection failed - token may be expired")
    
    def _verify_epic_connection(self):
        """Verify Epic connection and refresh token if needed"""
        try:
            # Check if token is expired or about to expire
            if hasattr(self.fhir_client, 'token_expires'):
                if self.fhir_client.token_expires and self.fhir_client.token_expires < datetime.now():
                    self.logger.info("Access token expired, refreshing...")
                    if not self.fhir_client.refresh_access_token():
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Epic connection verification failed: {str(e)}")
            return False
    
    def write_prep_sheet_to_epic(self, patient_id, prep_sheet_html, user_id, user_ip):
        """
        Write prep sheet to Epic as DocumentReference
        
        Args:
            patient_id: Patient ID
            prep_sheet_html: Rendered prep sheet HTML
            user_id: User who triggered the generation
            user_ip: IP address of user
            
        Returns:
            dict: {'success': bool, 'epic_document_id': str, 'error': str}
        """
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                return {'success': False, 'error': f'Patient {patient_id} not found'}
            
            # Validate Epic patient ID is present
            if not patient.epic_patient_id:
                return {
                    'success': False, 
                    'error': f'Patient {patient.full_name} (MRN: {patient.mrn}) does not have an Epic patient ID. Please sync with Epic first.'
                }
            
            # Initialize FHIR client
            self._initialize_fhir_client()
            
            # Generate timestamp for filename and document
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"PrepSheet_{patient.mrn}_{timestamp}.pdf"
            
            # Convert HTML to PDF
            pdf_content = self._html_to_pdf(prep_sheet_html, patient, timestamp)
            
            # Base64 encode PDF
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # Create FHIR DocumentReference resource
            document_reference = self._create_document_reference_structure(
                patient=patient,
                pdf_base64=pdf_base64,
                filename=filename,
                timestamp=timestamp
            )
            
            # DRY-RUN MODE: Log payload without sending to Epic
            if self.dry_run:
                self.logger.warning("=" * 80)
                self.logger.warning("🔍 DRY-RUN MODE: Epic Write-Back Simulation")
                self.logger.warning("=" * 80)
                self.logger.warning(f"Patient: {patient.full_name} (MRN: {patient.mrn})")
                self.logger.warning(f"Epic Patient ID: {patient.epic_patient_id}")
                self.logger.warning(f"Filename: {filename}")
                self.logger.warning(f"PDF Size: {len(pdf_content)} bytes")
                self.logger.warning(f"Base64 Size: {len(pdf_base64)} chars")
                self.logger.warning("-" * 80)
                self.logger.warning("📄 DocumentReference Structure (would be sent to Epic):")
                self.logger.warning("-" * 80)
                
                # Log the complete DocumentReference (excluding base64 content for readability)
                doc_ref_display = document_reference.copy()
                if 'content' in doc_ref_display and len(doc_ref_display['content']) > 0:
                    if 'attachment' in doc_ref_display['content'][0]:
                        doc_ref_display['content'][0]['attachment']['data'] = f"<BASE64_PDF_{len(pdf_base64)}_CHARS>"
                
                self.logger.warning(json.dumps(doc_ref_display, indent=2))
                self.logger.warning("=" * 80)
                
                # Return mock success response
                mock_epic_id = f"DRY-RUN-{timestamp}"
                
                log_admin_event(
                    event_type='epic_prep_sheet_write_dry_run',
                    user_id=user_id,
                    org_id=self.organization.id,
                    ip=user_ip,
                    data={
                        'patient_mrn': patient.mrn,
                        'mock_epic_document_id': mock_epic_id,
                        'filename': filename,
                        'dry_run': True,
                        'description': f'DRY-RUN: Simulated prep sheet write to Epic for patient {patient.mrn}'
                    }
                )
                
                return {
                    'success': True,
                    'epic_document_id': mock_epic_id,
                    'filename': filename,
                    'timestamp': timestamp,
                    'dry_run': True
                }
            
            # PRODUCTION MODE: Write to Epic with retry on 401
            result = self._write_document_with_retry(document_reference)
            
            if result and result.get('id'):
                epic_doc_id = result.get('id')
                
                # Log successful write to Epic
                log_admin_event(
                    event_type='epic_prep_sheet_write',
                    user_id=user_id,
                    org_id=self.organization.id,
                    ip=user_ip,
                    data={
                        'patient_mrn': patient.mrn,
                        'epic_document_id': epic_doc_id,
                        'filename': filename,
                        'description': f'Wrote prep sheet to Epic for patient {patient.mrn}'
                    }
                )
                
                self.logger.info(f"Successfully wrote prep sheet to Epic: {epic_doc_id}")
                return {
                    'success': True,
                    'epic_document_id': epic_doc_id,
                    'filename': filename,
                    'timestamp': timestamp
                }
            else:
                return {'success': False, 'error': 'Epic DocumentReference creation failed'}
                
        except ConnectionError as e:
            self.logger.error(f"Epic connection error: {str(e)}")
            return {
                'success': False,
                'error': 'Epic connection failed - please verify OAuth connection is valid',
                'connection_error': True
            }
            
        except Exception as e:
            self.logger.error(f"Error writing prep sheet to Epic: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _write_document_with_retry(self, document_reference):
        """
        Write DocumentReference to Epic with automatic retry on 401 (expired token)
        
        Args:
            document_reference: FHIR DocumentReference structure
            
        Returns:
            dict: Epic API response or None
        """
        try:
            # First attempt
            result = self.fhir_client.create_document_reference(document_reference)
            return result
            
        except Exception as e:
            # Check if it's a 401 error (expired token)
            if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 401:
                self.logger.warning("Received 401 error, attempting token refresh and retry...")
                
                # Refresh token
                if self.fhir_client.refresh_access_token():
                    # Retry the write operation
                    try:
                        result = self.fhir_client.create_document_reference(document_reference)
                        self.logger.info("Successfully wrote DocumentReference after token refresh")
                        return result
                    except Exception as retry_error:
                        self.logger.error(f"Retry failed after token refresh: {str(retry_error)}")
                        raise
                else:
                    self.logger.error("Token refresh failed, cannot retry DocumentReference write")
                    raise
            else:
                # Not a 401 error, re-raise
                raise
    
    def _html_to_pdf(self, html_content, patient, timestamp):
        """
        Convert HTML to PDF with timestamp in header/footer
        
        Args:
            html_content: HTML string
            patient: Patient object
            timestamp: Timestamp string
            
        Returns:
            bytes: PDF content
        """
        try:
            # Add timestamp header to HTML
            timestamped_html = self._add_timestamp_to_html(html_content, patient, timestamp)
            
            # Convert to PDF using WeasyPrint
            pdf_file = BytesIO()
            HTML(string=timestamped_html).write_pdf(pdf_file)
            pdf_content = pdf_file.getvalue()
            
            self.logger.info(f"Generated PDF ({len(pdf_content)} bytes) for patient {patient.mrn}")
            return pdf_content
            
        except Exception as e:
            self.logger.error(f"PDF generation failed: {str(e)}")
            raise
    
    def _add_timestamp_to_html(self, html_content, patient, timestamp):
        """Add timestamp header/footer to HTML for PDF"""
        timestamp_formatted = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%m/%d/%Y %I:%M %p')
        
        # Add header with timestamp
        header_html = f"""
        <div style="text-align: center; padding: 10px; border-bottom: 2px solid #667eea; margin-bottom: 20px;">
            <h2 style="margin: 0; color: #667eea;">Medical Preparation Sheet</h2>
            <p style="margin: 5px 0; color: #666;">
                Patient: {patient.full_name} (MRN: {patient.mrn}) | Generated: {timestamp_formatted}
            </p>
        </div>
        """
        
        # Insert header after body tag
        if '<body>' in html_content:
            html_content = html_content.replace('<body>', f'<body>{header_html}', 1)
        
        return html_content
    
    def _create_document_reference_structure(self, patient, pdf_base64, filename, timestamp):
        """
        Create FHIR DocumentReference structure for Epic
        
        Args:
            patient: Patient object
            pdf_base64: Base64 encoded PDF
            filename: Document filename
            timestamp: Timestamp string
            
        Returns:
            dict: FHIR DocumentReference resource
        """
        timestamp_dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
        
        document_reference = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note"
                }],
                "text": "Medical Preparation Sheet"
            },
            "subject": {
                "reference": f"Patient/{patient.epic_patient_id}",
                "display": patient.full_name
            },
            "date": timestamp_dt.isoformat(),
            "author": [{
                "display": f"{self.organization.name} - HealthPrep System"
            }],
            "description": f"Medical preparation sheet generated on {timestamp_dt.strftime('%m/%d/%Y %I:%M %p')}",
            "content": [{
                "attachment": {
                    "contentType": "application/pdf",
                    "data": pdf_base64,
                    "title": filename,
                    "creation": timestamp_dt.isoformat()
                },
                "format": {
                    "system": "http://ihe.net/fhir/ValueSet/IHE.FormatCode.codesystem",
                    "code": "urn:ihe:iti:xds:2017:mimeTypeSufficient",
                    "display": "PDF"
                }
            }],
            "context": {
                "period": {
                    "start": timestamp_dt.isoformat()
                }
            }
        }
        
        return document_reference
    
    def bulk_write_prep_sheets(self, patient_ids, prep_sheet_generator, user_id, user_ip):
        """
        Bulk write prep sheets to Epic for multiple patients
        
        Args:
            patient_ids: List of patient IDs
            prep_sheet_generator: PrepSheetGenerator instance
            user_id: User who triggered the generation
            user_ip: IP address of user
            
        Returns:
            dict: {'success_count': int, 'failed_count': int, 'results': list}
        """
        results = []
        success_count = 0
        failed_count = 0
        
        for patient_id in patient_ids:
            try:
                # Generate prep sheet HTML
                prep_result = prep_sheet_generator.generate_prep_sheet(patient_id)
                
                if not prep_result.get('success'):
                    results.append({
                        'patient_id': patient_id,
                        'success': False,
                        'error': prep_result.get('error', 'Prep sheet generation failed')
                    })
                    failed_count += 1
                    continue
                
                # Render prep sheet to HTML
                from flask import render_template
                prep_data = prep_result['data']
                prep_html = render_template('prep_sheet/prep_sheet.html', **prep_data)
                
                # Write to Epic
                write_result = self.write_prep_sheet_to_epic(
                    patient_id=patient_id,
                    prep_sheet_html=prep_html,
                    user_id=user_id,
                    user_ip=user_ip
                )
                
                if write_result.get('success'):
                    success_count += 1
                else:
                    failed_count += 1
                
                results.append({
                    'patient_id': patient_id,
                    **write_result
                })
                
            except Exception as e:
                self.logger.error(f"Error processing patient {patient_id}: {str(e)}")
                results.append({
                    'patient_id': patient_id,
                    'success': False,
                    'error': str(e)
                })
                failed_count += 1
        
        # Log summary
        if self.dry_run:
            self.logger.warning(f"🔍 DRY-RUN BULK SUMMARY: {success_count} simulated, {failed_count} failed out of {len(patient_ids)} total")
        else:
            self.logger.info(f"Bulk Epic write complete: {success_count} succeeded, {failed_count} failed out of {len(patient_ids)} total")
        
        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'total': len(patient_ids),
            'results': results,
            'dry_run': self.dry_run
        }

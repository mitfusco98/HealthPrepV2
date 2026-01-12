"""
Epic FHIR Write-Back Service
Handles writing prep sheets back to Epic as DocumentReference resources
"""

import logging
import base64
import os
import json
import copy
from datetime import datetime
from io import BytesIO
from weasyprint import HTML, CSS
from flask import render_template_string
from emr.fhir_client import FHIRClient
from models import Patient, Organization, Screening, EpicCredentials, log_admin_event

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
        
        # Create organization config dict for FHIRClient
        organization_config = {
            'epic_client_id': self.organization.epic_client_id,
            'epic_client_secret': self.organization.epic_client_secret,
            'epic_fhir_url': self.organization.epic_fhir_url
        }
        
        self.fhir_client = FHIRClient(
            organization_config=organization_config,
            organization=self.organization
        )
        
        # Load stored tokens from EpicCredentials
        epic_creds = EpicCredentials.query.filter_by(org_id=self.organization.id).first()
        if not epic_creds or not epic_creds.access_token:
            raise ValueError("No Epic access tokens found - please authenticate with Epic first")
        
        # Require refresh token for writeback operations (needed for retry path)
        if not epic_creds.refresh_token:
            raise ValueError(
                "No Epic refresh token available. Epic credentials may be incomplete. "
                "Please re-authenticate with Epic to enable prep sheet write-back."
            )
        
        # Check token expiration - if token_expires_at is NULL, treat as expired
        if epic_creds.token_expires_at:
            remaining = (epic_creds.token_expires_at - datetime.utcnow()).total_seconds()
            token_expired = remaining <= 0
        else:
            # Unknown expiration - treat as expired and force refresh
            self.logger.warning("Epic token expiration time unknown, treating as expired")
            remaining = 0
            token_expired = True
        
        # Set initial tokens on the client
        self.fhir_client.set_tokens(
            access_token=epic_creds.access_token,
            refresh_token=epic_creds.refresh_token,
            expires_in=max(int(remaining), 1),  # At least 1 second
            scopes=epic_creds.token_scope.split() if epic_creds.token_scope else []
        )
        
        # If token is expired, proactively refresh before any API calls
        if token_expired:
            self.logger.info("Access token expired, proactively refreshing before write operation")
            if not self.fhir_client.refresh_access_token():
                raise ConnectionError(
                    "Epic access token has expired and refresh failed. "
                    "Please re-authenticate with Epic to continue."
                )
            self.logger.info("Successfully refreshed Epic access token")
        else:
            self.logger.info(f"Loaded Epic tokens from database for organization {self.organization.id} (valid for {int(remaining)}s)")
        
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
    
    def write_prep_sheet_to_epic(self, patient_id, prep_sheet_html, user_id, user_ip, prep_data=None):
        """
        Write prep sheet to Epic as DocumentReference
        
        Args:
            patient_id: Patient ID
            prep_sheet_html: Rendered prep sheet HTML
            user_id: User who triggered the generation
            user_ip: IP address of user
            prep_data: Optional prep sheet data dict with screening info and cutoff dates
            
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
            
            # Convert HTML to PDF with comprehensive header
            pdf_content = self._html_to_pdf(prep_sheet_html, patient, timestamp, prep_data)
            
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
                
                # Log the complete DocumentReference (excluding base64 PDF content for PHI protection)
                doc_ref_display = copy.deepcopy(document_reference)
                if 'content' in doc_ref_display and len(doc_ref_display['content']) > 0:
                    if 'attachment' in doc_ref_display['content'][0]:
                        # Replace actual PDF data with placeholder to avoid PHI in logs
                        doc_ref_display['content'][0]['attachment']['data'] = f"<BASE64_PDF_DATA_REDACTED_{len(pdf_base64)}_CHARS>"
                
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
            
            # Check for error response (new format from enhanced FHIR client)
            if result and result.get('error'):
                error_msg = result.get('error', 'Unknown error')
                is_sandbox = result.get('is_sandbox_limitation', False)
                
                if is_sandbox:
                    self.logger.warning(f"Epic sandbox limitation detected: {error_msg}")
                    return {
                        'success': False, 
                        'error': f'Epic sandbox does not support document writes. This feature requires a production Epic environment. Details: {error_msg}',
                        'is_sandbox_limitation': True,
                        'details': result.get('details', {})
                    }
                else:
                    self.logger.error(f"Epic DocumentReference creation failed: {error_msg}")
                    return {
                        'success': False, 
                        'error': error_msg,
                        'details': result.get('details', {})
                    }
            
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
                return {'success': False, 'error': 'Epic DocumentReference creation failed - no document ID returned'}
                
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
            dict: Epic API response with 'id' on success, or 'error' on failure
        """
        # First attempt
        result = self.fhir_client.create_document_reference(document_reference)
        
        # Check if we got a 401 error (expired token) - new error response format
        if result and result.get('error') and result.get('status_code') == 401:
            self.logger.warning("Received 401 error, attempting token refresh and retry...")
            
            # Refresh token
            if self.fhir_client.refresh_access_token():
                # Retry the write operation
                result = self.fhir_client.create_document_reference(document_reference)
                
                if result and result.get('id'):
                    self.logger.info("Successfully wrote DocumentReference after token refresh")
                elif result and result.get('error'):
                    self.logger.error(f"Retry failed after token refresh: {result.get('error')}")
                
                return result
            else:
                self.logger.error("Token refresh failed, cannot retry DocumentReference write")
                return {
                    'error': 'Token refresh failed - please re-authenticate with Epic',
                    'details': {},
                    'is_sandbox_limitation': False
                }
        
        return result
    
    def _html_to_pdf(self, html_content, patient, timestamp, prep_data=None):
        """
        Convert HTML to PDF with comprehensive header including provider, screening status, and cutoff dates
        
        Args:
            html_content: HTML string
            patient: Patient object
            timestamp: Timestamp string
            prep_data: Optional prep sheet data dict with screening info and cutoff dates
            
        Returns:
            bytes: PDF content
        """
        try:
            # Add comprehensive header to HTML
            timestamped_html = self._add_timestamp_to_html(html_content, patient, timestamp, prep_data)
            
            # IMPORTANT: Use custom URL fetcher to avoid HTTP deadlock
            # Using request.host_url causes WeasyPrint to make HTTP requests back to the same server,
            # which blocks because the server is waiting for this response to complete.
            # The custom fetcher intercepts /static/... URLs and reads files directly from disk.
            from flask import current_app, has_app_context
            from weasyprint import default_url_fetcher
            import os
            from urllib.parse import urlparse
            from pathlib import Path
            
            # Determine static folder - handle both app context and background task scenarios
            if has_app_context() and current_app:
                static_folder = current_app.static_folder or os.path.join(current_app.root_path, 'static')
                root_path = current_app.root_path
            else:
                # Fallback: use current working directory (for background/batch tasks)
                static_folder = os.path.join(os.getcwd(), 'static')
                root_path = os.getcwd()
            
            base_url = Path(root_path).as_uri() + '/'
            
            def custom_url_fetcher(url):
                """Custom URL fetcher that maps /static/... to local files.
                
                This prevents WeasyPrint from making HTTP requests to the server,
                which would cause a deadlock since the server is waiting for PDF generation.
                Handles URLs from HTML attributes and CSS url() references.
                """
                parsed = urlparse(url)
                
                # Handle /static/... paths (absolute or with hostname)
                if parsed.path.startswith('/static/'):
                    # Strip query strings and fragments, get path relative to static folder
                    relative_path = parsed.path[8:]  # Remove '/static/'
                    local_path = os.path.join(static_folder, relative_path)
                    
                    if os.path.isfile(local_path):
                        # Return properly quoted file:// URL for WeasyPrint
                        file_uri = Path(local_path).as_uri()
                        return default_url_fetcher(file_uri)
                    else:
                        self.logger.warning(f"Static file not found: {local_path}")
                
                # For file:// URLs and other cases, use default fetcher
                # Skip HTTP/HTTPS URLs to avoid deadlock
                if parsed.scheme in ('http', 'https'):
                    # Check if it's a request to our own server's static files
                    if '/static/' in parsed.path:
                        relative_path = parsed.path.split('/static/', 1)[1]
                        local_path = os.path.join(static_folder, relative_path)
                        if os.path.isfile(local_path):
                            file_uri = Path(local_path).as_uri()
                            return default_url_fetcher(file_uri)
                    # For external URLs, let them fail silently (timeout already handled by not fetching)
                    self.logger.debug(f"Skipping external URL to avoid deadlock: {url}")
                    return {'string': b'', 'mime_type': 'text/css'}
                
                return default_url_fetcher(url)
            
            # Convert to PDF using WeasyPrint with custom URL fetcher
            pdf_file = BytesIO()
            html_doc = HTML(string=timestamped_html, base_url=base_url, url_fetcher=custom_url_fetcher)
            html_doc.write_pdf(pdf_file)
            pdf_content = pdf_file.getvalue()
            
            self.logger.info(f"Generated PDF ({len(pdf_content)} bytes) for patient {patient.mrn}")
            return pdf_content
            
        except Exception as e:
            self.logger.error(f"PDF generation failed: {str(e)}")
            raise
    
    def _add_timestamp_to_html(self, html_content, patient, timestamp, prep_data=None):
        """Add comprehensive header with provider, screening status, and cutoff dates to HTML for PDF"""
        timestamp_formatted = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%m/%d/%Y %I:%M %p')
        
        # Extract provider information
        provider_name = "N/A"
        if patient.provider:
            provider_name = patient.provider.name if hasattr(patient.provider, 'name') else str(patient.provider)
        
        # Extract screening status summary
        screening_summary = ""
        if prep_data and 'prep_sheet' in prep_data:
            prep_sheet = prep_data['prep_sheet']
            content = prep_sheet.get('content', {})
            quality_checklist = content.get('quality_checklist', [])
            
            if quality_checklist:
                due_count = sum(1 for item in quality_checklist if item.get('status') == 'due')
                due_soon_count = sum(1 for item in quality_checklist if item.get('status') == 'due_soon')
                complete_count = sum(1 for item in quality_checklist if item.get('status') == 'complete')
                overdue_count = sum(1 for item in quality_checklist if item.get('status') == 'overdue')
                total_count = len(quality_checklist)
                
                screening_summary = f"""
                <div style="margin-top: 10px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;">
                    <strong style="color: #333;">Screening Status Summary:</strong>
                    <span style="margin-left: 10px;">
                        <span style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">Complete: {complete_count}</span>
                        <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">Due: {due_count}</span>
                        <span style="background-color: #ffc107; color: #333; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">Due Soon: {due_soon_count}</span>
                        <span style="background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 3px;">Overdue: {overdue_count}</span>
                    </span>
                    <span style="margin-left: 15px; color: #666;">Total: {total_count}</span>
                </div>
                """
        
        # Extract cutoff dates for the four bulk sections
        cutoff_section = ""
        if prep_data and 'prep_sheet' in prep_data:
            prep_sheet = prep_data['prep_sheet']
            content = prep_sheet.get('content', {})
            medical_data = content.get('medical_data', {})
            cutoff_dates = medical_data.get('cutoff_dates', {})
            
            if cutoff_dates:
                labs_cutoff = cutoff_dates.get('labs')
                imaging_cutoff = cutoff_dates.get('imaging')
                consults_cutoff = cutoff_dates.get('consults')
                hospital_cutoff = cutoff_dates.get('hospital')
                
                def format_date(d):
                    if d:
                        if hasattr(d, 'strftime'):
                            return d.strftime('%m/%d/%Y')
                        return str(d)
                    return 'N/A'
                
                cutoff_section = f"""
                <div style="margin-top: 10px; padding: 8px; background-color: #e9ecef; border-radius: 4px;">
                    <strong style="color: #333;">Data Cutoff Dates:</strong>
                    <div style="display: flex; flex-wrap: wrap; margin-top: 5px;">
                        <div style="flex: 1; min-width: 120px; margin-right: 10px;">
                            <span style="color: #6c757d;">Labs:</span> {format_date(labs_cutoff)}
                        </div>
                        <div style="flex: 1; min-width: 120px; margin-right: 10px;">
                            <span style="color: #6c757d;">Imaging:</span> {format_date(imaging_cutoff)}
                        </div>
                        <div style="flex: 1; min-width: 120px; margin-right: 10px;">
                            <span style="color: #6c757d;">Consults:</span> {format_date(consults_cutoff)}
                        </div>
                        <div style="flex: 1; min-width: 120px;">
                            <span style="color: #6c757d;">Hospital:</span> {format_date(hospital_cutoff)}
                        </div>
                    </div>
                </div>
                """
        
        # Build comprehensive header
        header_html = f"""
        <div style="padding: 15px; border-bottom: 3px solid #667eea; margin-bottom: 20px; background: linear-gradient(to bottom, #f8f9fa, #ffffff);">
            <div style="text-align: center;">
                <h2 style="margin: 0; color: #667eea; font-size: 24px;">Medical Preparation Sheet</h2>
                <p style="margin: 5px 0; color: #666; font-size: 12px;">
                    Generated by HealthPrep System | {self.organization.name}
                </p>
            </div>
            
            <div style="display: flex; justify-content: space-between; margin-top: 15px; padding-top: 10px; border-top: 1px solid #dee2e6;">
                <div style="flex: 1;">
                    <strong style="color: #333;">Patient:</strong> {patient.full_name}<br>
                    <span style="color: #666; font-size: 12px;">MRN: {patient.mrn} | DOB: {patient.date_of_birth.strftime('%m/%d/%Y') if patient.date_of_birth else 'N/A'}</span>
                </div>
                <div style="flex: 1; text-align: center;">
                    <strong style="color: #333;">Provider:</strong> {provider_name}
                </div>
                <div style="flex: 1; text-align: right;">
                    <strong style="color: #333;">Generated:</strong> {timestamp_formatted}
                </div>
            </div>
            
            {screening_summary}
            {cutoff_section}
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
            "identifier": [{
                "system": "https://healthprep.io/fhir/identifier",
                "value": "healthprep-generated"
            }],
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note"
                }],
                "text": "Medical Preparation Sheet"
            },
            "category": [{
                "coding": [{
                    "system": "https://healthprep.io/fhir/category",
                    "code": "healthprep-prep-sheet",
                    "display": "HealthPrep Generated Prep Sheet"
                }]
            }],
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
                
                # Write to Epic with prep_data for comprehensive PDF header
                write_result = self.write_prep_sheet_to_epic(
                    patient_id=patient_id,
                    prep_sheet_html=prep_html,
                    user_id=user_id,
                    user_ip=user_ip,
                    prep_data=prep_data
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

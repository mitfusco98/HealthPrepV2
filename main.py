"""
HealthPrep Medical Screening System
Main application entry point
"""
import os
import logging
from app import create_app
from routes import (
    main_routes, admin_routes, auth_routes, api_routes,
    screening_routes, document_routes, prep_sheet_routes,
    ocr_routes, async_routes, emr_sync_routes, fhir_routes,
    oauth_routes, epic_registration_routes, epic_admin_routes,
    fuzzy_detection_routes, phi_test_routes, root_admin_routes,
    epic_public_routes
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask application
app = create_app()

# Register blueprints
app.register_blueprint(main_routes.main_bp)
app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')
app.register_blueprint(auth_routes.auth_bp, url_prefix='/auth')
app.register_blueprint(api_routes.api_bp, url_prefix='/api')
app.register_blueprint(screening_routes.screening_bp, url_prefix='/screening')
app.register_blueprint(document_routes.document_bp, url_prefix='/documents')
app.register_blueprint(prep_sheet_routes.prep_sheet_bp, url_prefix='/prep-sheet')
app.register_blueprint(ocr_routes.ocr_bp, url_prefix='/ocr')
app.register_blueprint(async_routes.async_bp, url_prefix='/async')
app.register_blueprint(emr_sync_routes.emr_sync_bp, url_prefix='/emr-sync')
app.register_blueprint(fhir_routes.fhir_bp, url_prefix='/fhir')
app.register_blueprint(oauth_routes.oauth_bp, url_prefix='/oauth')
app.register_blueprint(epic_registration_routes.epic_registration_bp, url_prefix='/epic-registration')
app.register_blueprint(epic_admin_routes.epic_admin_bp, url_prefix='/epic-admin')
app.register_blueprint(fuzzy_detection_routes.fuzzy_bp, url_prefix='/fuzzy')
app.register_blueprint(phi_test_routes.phi_test_bp, url_prefix='/phi-test')
app.register_blueprint(root_admin_routes.root_admin_bp, url_prefix='/root-admin')
app.register_blueprint(epic_public_routes.epic_public_bp)  # No prefix - serves /.well-known/ routes

if __name__ == '__main__':
    logger.info("Starting HealthPrep Medical Screening System")
    app.run(host='0.0.0.0', port=5000, debug=True)
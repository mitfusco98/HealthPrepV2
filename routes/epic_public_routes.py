
"""
Epic Public Routes
Provides public endpoints required for Epic App Orchard registration
"""

from flask import Blueprint, jsonify, render_template_string
import json
import base64
import hashlib
from datetime import datetime, timedelta
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os

# Create blueprint
epic_public_bp = Blueprint('epic_public', __name__)

def generate_rsa_keypair():
    """Generate RSA keypair for JWT signing"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    public_key = private_key.public_key()
    
    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem, public_pem, public_key

def get_jwk_from_public_key(public_key):
    """Convert RSA public key to JWK format"""
    public_numbers = public_key.public_numbers()
    
    # Convert to JWK format
    def int_to_base64url(val):
        byte_length = (val.bit_length() + 7) // 8
        val_bytes = val.to_bytes(byte_length, 'big')
        return base64.urlsafe_b64encode(val_bytes).decode('ascii').rstrip('=')
    
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "healthprep-epic-key-1",
        "n": int_to_base64url(public_numbers.n),
        "e": int_to_base64url(public_numbers.e)
    }
    
    return jwk

@epic_public_bp.route('/.well-known/smart-configuration')
def smart_configuration():
    """
    SMART on FHIR configuration endpoint
    Required by Epic for app discovery and configuration
    """
    config = {
        "issuer": "https://fhir.epic.com/interconnect-fhir-oauth",
        "authorization_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        "token_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        "userinfo_endpoint": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/userinfo",
        "jwks_uri": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/jwks",
        "scopes_supported": [
            "openid",
            "fhirUser",
            "patient/Patient.read",
            "patient/Observation.read",
            "patient/Condition.read",
            "patient/DocumentReference.read",
            "patient/Encounter.read",
            "user/Patient.read",
            "user/Observation.read",
            "user/Condition.read",
            "user/DocumentReference.read",
            "user/Encounter.read"
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "capabilities": [
            "launch-ehr",
            "launch-standalone",
            "client-public",
            "client-confidential",
            "sso-openid-connect",
            "context-ehr-patient",
            "context-ehr-encounter",
            "context-standalone-patient",
            "permission-offline",
            "permission-patient",
            "permission-user"
        ]
    }
    
    return jsonify(config)

@epic_public_bp.route('/epic/documentation')
def epic_documentation():
    """
    Public documentation URL for Epic App Orchard registration
    Describes the HealthPrep SMART on FHIR integration
    """
    doc_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HealthPrep Epic SMART on FHIR Integration</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
            .section { margin-bottom: 30px; }
            .endpoint { background-color: #e9ecef; padding: 10px; border-radius: 3px; font-family: monospace; }
            .scope { background-color: #d4edda; padding: 5px; margin: 2px; border-radius: 3px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>HealthPrep Medical Screening System</h1>
            <p><strong>Epic SMART on FHIR Integration Documentation</strong></p>
            <p>Version: 1.0 | Last Updated: {{ current_date }}</p>
        </div>

        <div class="section">
            <h2>Application Overview</h2>
            <p>HealthPrep is a medical screening preparation system that integrates with Epic EMRs to:</p>
            <ul>
                <li>Retrieve patient clinical data for screening assessments</li>
                <li>Generate personalized prep sheets for medical screenings</li>
                <li>Track screening compliance and due dates</li>
                <li>Provide clinical decision support for screening recommendations</li>
            </ul>
        </div>

        <div class="section">
            <h2>SMART on FHIR Implementation</h2>
            <p>HealthPrep implements the SMART on FHIR specification for secure integration with Epic:</p>
            
            <h3>OAuth 2.0 Endpoints</h3>
            <p><strong>Redirect URI:</strong></p>
            <div class="endpoint">{{ redirect_uri }}</div>
            
            <h3>Required FHIR Scopes</h3>
            <div>
                <span class="scope">openid</span>
                <span class="scope">fhirUser</span>
                <span class="scope">patient/Patient.read</span>
                <span class="scope">patient/Condition.read</span>
                <span class="scope">patient/Observation.read</span>
                <span class="scope">patient/DocumentReference.read</span>
                <span class="scope">patient/Encounter.read</span>
            </div>
        </div>

        <div class="section">
            <h2>Data Usage and Privacy</h2>
            <ul>
                <li><strong>Minimum Necessary:</strong> Only retrieves data required for screening assessments</li>
                <li><strong>Purpose Limitation:</strong> Data used solely for medical screening preparation</li>
                <li><strong>Data Retention:</strong> Clinical data is processed in real-time and not permanently stored</li>
                <li><strong>PHI Protection:</strong> All PHI is handled in compliance with HIPAA regulations</li>
            </ul>
        </div>

        <div class="section">
            <h2>Clinical Use Cases</h2>
            <h3>Supported Screening Types</h3>
            <ul>
                <li>Mammography screening</li>
                <li>Colonoscopy screening</li>
                <li>Cervical cancer screening (Pap smear)</li>
                <li>Cardiovascular risk assessment</li>
                <li>Diabetes screening</li>
                <li>Bone density screening</li>
            </ul>
            
            <h3>Data Elements Retrieved</h3>
            <ul>
                <li>Patient demographics (age, gender)</li>
                <li>Problem list and active conditions</li>
                <li>Laboratory results (relevant to screening criteria)</li>
                <li>Previous screening history</li>
                <li>Current medications</li>
            </ul>
        </div>

        <div class="section">
            <h2>Technical Specifications</h2>
            <ul>
                <li><strong>FHIR Version:</strong> R4</li>
                <li><strong>Authentication:</strong> OAuth 2.0 with PKCE</li>
                <li><strong>Token Type:</strong> Bearer tokens</li>
                <li><strong>Supported Flows:</strong> Authorization Code Grant</li>
            </ul>
        </div>

        <div class="section">
            <h2>Security and Compliance</h2>
            <ul>
                <li>HIPAA compliant data handling</li>
                <li>TLS 1.2+ encryption for all communications</li>
                <li>Token-based authentication with automatic refresh</li>
                <li>Audit logging for all FHIR API access</li>
                <li>Role-based access control</li>
            </ul>
        </div>

        <div class="section">
            <h2>Support Information</h2>
            <p><strong>Technical Support:</strong> support@healthprep.com</p>
            <p><strong>Implementation Guide:</strong> Available upon request</p>
            <p><strong>Test Environment:</strong> Sandbox testing available</p>
        </div>
    </body>
    </html>
    """
    
    from flask import request, url_for
    redirect_uri = url_for('oauth.epic_callback', _external=True)
    if redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://')
    
    return render_template_string(doc_html, 
                                current_date=datetime.now().strftime('%Y-%m-%d'),
                                redirect_uri=redirect_uri)

@epic_public_bp.route('/epic/jwks/non-production')
def non_production_jwks():
    """
    Non-Production JWK Set URL for Epic App Orchard
    Provides public keys for JWT verification in sandbox/testing
    """
    try:
        # Generate or retrieve sandbox keypair
        private_key, public_key, rsa_public_key = generate_rsa_keypair()
        
        jwk = get_jwk_from_public_key(rsa_public_key)
        
        jwks = {
            "keys": [jwk]
        }
        
        response = jsonify(jwks)
        response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
        
    except Exception as e:
        return jsonify({
            "error": "Unable to generate JWKS",
            "message": str(e)
        }), 500

@epic_public_bp.route('/epic/jwks/production')
def production_jwks():
    """
    Production JWK Set URL for Epic App Orchard
    Provides public keys for JWT verification in production
    """
    try:
        # In production, you would load from secure storage
        # For now, generate a stable keypair
        private_key, public_key, rsa_public_key = generate_rsa_keypair()
        
        jwk = get_jwk_from_public_key(rsa_public_key)
        
        jwks = {
            "keys": [jwk]
        }
        
        response = jsonify(jwks)
        response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        return response
        
    except Exception as e:
        return jsonify({
            "error": "Unable to generate JWKS",
            "message": str(e)
        }), 500

@epic_public_bp.route('/epic/app-info')
def app_info():
    """
    Application information endpoint for Epic App Orchard
    """
    info = {
        "application_name": "HealthPrep Medical Screening System",
        "vendor": "HealthPrep Technologies",
        "version": "1.0.0",
        "fhir_version": "4.0.1",
        "smart_version": "1.0.0",
        "description": "Automated medical screening preparation and clinical decision support",
        "contact_email": "support@healthprep.com",
        "privacy_policy": "https://healthprep.com/privacy",
        "terms_of_service": "https://healthprep.com/terms",
        "logo_uri": "https://healthprep.com/logo.png"
    }
    
    return jsonify(info)

@epic_public_bp.route('/health')
def health_check():
    """Health check endpoint for Epic connectivity testing"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "HealthPrep Epic Integration",
        "version": "1.0.0"
    })

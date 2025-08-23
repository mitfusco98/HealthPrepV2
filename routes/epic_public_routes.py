"""
Epic Public Routes
Provides public endpoints required for Epic App Orchard registration
"""

from flask import Blueprint, jsonify, render_template_string, request, url_for
import json
import base64
import hashlib
from datetime import datetime, timedelta
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os
from typing import Dict, List, Union
import time
import uuid

# Create blueprint
epic_public_bp = Blueprint('epic_public', __name__)

def b64u(b: bytes) -> str:
    """Base64url encode bytes without padding"""
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def jwk_from_pem(pem: bytes, kid: str) -> Dict:
    """Convert PEM private key to JWK public key format"""
    try:
        private_key = serialization.load_pem_private_key(pem, password=None)

        # Ensure we have an RSA key
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError(f"Expected RSA private key, got {type(private_key)}")

        public_key = private_key.public_key()
        pub_numbers = public_key.public_numbers()

        n = pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7)//8, "big")
        e = pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7)//8, "big")

        return {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid, "n": b64u(n), "e": b64u(e)}
    except Exception as e:
        raise ValueError(f"Failed to convert PEM to JWK: {e}")

def collect_keys(prefix: str) -> List[Dict]:
    """Collect and convert environment keys to JWK format"""
    keys = []

    for name, value in os.environ.items():
        if name.startswith(prefix) and value.strip():
            try:
                # Extract kid from environment variable name
                # P_KEY_2025_08_A -> 2025_08_A
                kid = name[len(prefix)+1:] if name.startswith(prefix + "_") else name[len(prefix):]

                # Convert PEM to JWK
                pem_bytes = value.strip().encode('utf-8')
                jwk = jwk_from_pem(pem_bytes, kid)
                keys.append(jwk)

            except Exception as e:
                print(f"Error processing key {name}: {e}")
                continue

    # Stable order helps caches
    keys.sort(key=lambda k: k["kid"])
    return keys

def generate_fallback_key() -> rsa.RSAPrivateKey:
    """Generate a fallback RSA key"""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

def get_jwk_from_fallback_key(private_key: rsa.RSAPrivateKey, kid: str) -> Dict:
    """Convert fallback private key to JWK format"""
    public_key = private_key.public_key()
    pub_numbers = public_key.public_numbers()

    n = pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7)//8, "big")
    e = pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7)//8, "big")

    return {
        "kty": "RSA",
        "alg": "RS256", 
        "use": "sig",
        "kid": kid,
        "n": b64u(n),
        "e": b64u(e)
    }

def get_private_key_for_environment(environment: str = "nonprod") -> Union[rsa.RSAPrivateKey, None]:
    """Get the appropriate private key for JWT signing"""
    prefix = "NP_KEY" if environment == "nonprod" else "P_KEY"

    # Find first available key with the prefix
    for name, value in os.environ.items():
        if name.startswith(prefix) and value.strip():
            try:
                pem_bytes = value.strip().encode('utf-8')
                private_key = serialization.load_pem_private_key(
                    pem_bytes, 
                    password=None,
                    backend=default_backend()
                )
                return private_key
            except Exception as e:
                print(f"Error loading key {name}: {e}")
                continue

    # Return fallback key if no environment keys found
    return generate_fallback_key()

def get_kid_for_environment(environment: str = "nonprod") -> str:
    """Get the appropriate key ID for JWT signing"""
    prefix = "NP_KEY" if environment == "nonprod" else "P_KEY"

    # Find first available key with the prefix
    for name, value in os.environ.items():
        if name.startswith(prefix) and value.strip():
            # Extract kid from environment variable name
            return name[len(prefix)+1:] if name.startswith(prefix + "_") else name[len(prefix):]

    # Return fallback kid if no environment keys found
    return f"{environment}-fallback"

def create_client_assertion(client_id: str, token_url: str, environment: str = "nonprod") -> str:
    """
    Create a JWT client assertion for Epic OAuth

    Args:
        client_id: Epic client ID
        token_url: Epic token endpoint URL
        environment: "nonprod" or "prod"

    Returns:
        JWT client assertion string
    """
    try:
        # Get private key and kid for the environment
        private_key = get_private_key_for_environment(environment)
        kid = get_kid_for_environment(environment)

        # Create JWT claims
        now = datetime.utcnow()
        claims = {
            "iss": client_id,  # Issuer (your client ID)
            "sub": client_id,  # Subject (your client ID)
            "aud": token_url,  # Audience (Epic's token endpoint)
            "jti": f"{client_id}-{int(now.timestamp())}-{os.urandom(8).hex()}",  # Unique JWT ID
            "exp": int((now + timedelta(minutes=5)).timestamp()),  # Expires in 5 minutes
            "iat": int(now.timestamp()),  # Issued at
            "nbf": int(now.timestamp())   # Not before
        }

        # Create JWT header
        headers = {
            "alg": "RS256",
            "typ": "JWT",
            "kid": kid
        }

        # Sign the JWT
        token = jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers=headers
        )

        return token

    except Exception as e:
        raise ValueError(f"Failed to create client assertion: {e}")

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

    redirect_uri = url_for('oauth.epic_callback', _external=True)
    if redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://')

    return render_template_string(doc_html, 
                                current_date=datetime.now().strftime('%Y-%m-%d'),
                                redirect_uri=redirect_uri)

@epic_public_bp.route('/nonprod/.well-known/jwks.json')
def nonprod_jwks():
    """
    Non-Production JWK Set URL for Epic App Orchard
    Provides public keys for JWT verification in non-production
    """
    try:
        keys = collect_keys("NP_KEY")

        # If no environment keys found, generate a fallback
        if not keys:
            fallback_key = generate_fallback_key()
            fallback_jwk = get_jwk_from_fallback_key(fallback_key, "nonprod-fallback")
            keys = [fallback_jwk]

        jwks = {"keys": keys}

        response = jsonify(jwks)
        response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        return jsonify({
            "error": "Unable to generate JWKS",
            "message": str(e)
        }), 500

@epic_public_bp.route('/.well-known/jwks.json')
def prod_jwks():
    """
    Production JWK Set URL for Epic App Orchard
    Provides public keys for JWT verification in production
    """
    try:
        keys = collect_keys("P_KEY")

        # If no environment keys found, generate a fallback
        if not keys:
            fallback_key = generate_fallback_key()
            fallback_jwk = get_jwk_from_fallback_key(fallback_key, "prod-fallback")
            keys = [fallback_jwk]

        jwks = {"keys": keys}

        response = jsonify(jwks)
        response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        return jsonify({
            "error": "Unable to generate JWKS",
            "message": str(e)
        }), 500

@epic_public_bp.route('/epic/app-info')
def epic_app_info():
    """
    Epic App Information Endpoint
    Provides app metadata for Epic App Orchard
    """
    app_info = {
        "name": "HealthPrep Medical Screening System",
        "description": "AI-powered medical screening and preparation system with Epic FHIR integration",
        "version": "2.0.0",
        "fhir_version": "R4",
        "smart_capabilities": [
            "launch-ehr",
            "client-public",
            "client-confidential-asymmetric",
            "context-ehr-patient",
            "sso-openid-connect"
        ],
        "supported_scopes": [
            "openid",
            "fhirUser",
            "patient/Patient.read",
            "patient/Observation.read",
            "patient/Condition.read", 
            "patient/MedicationRequest.read",
            "patient/DocumentReference.read",
            "patient/DocumentReference.write",
            "offline_access"
        ],
        "jwks_uri": {
            "production": "https://your-repl-url/.well-known/jwks.json",
            "nonprod": "https://your-repl-url/nonprod/.well-known/jwks.json"
        },
        "contact": {
            "name": "HealthPrep Support",
            "email": "support@healthprep.app"
        }
    }

    response = jsonify(app_info)
    response.headers['Content-Type'] = 'application/json'
    return response

@epic_public_bp.route('/health')
def health_check():
    """Health check endpoint for Epic connectivity testing"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "HealthPrep Epic Integration",
        "version": "1.0.0"
    })
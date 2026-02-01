"""
JWT Utilities for Epic Integration
Provides helper functions for creating client assertions and managing JWT keys
"""

from routes.epic_public_routes import create_client_assertion
import os

def get_epic_client_assertion(client_id: str, environment: str = "nonprod") -> str:
    """
    Create a client assertion for Epic OAuth token requests
    
    Args:
        client_id: Your Epic client ID
        environment: "nonprod" or "prod"
    
    Returns:
        JWT client assertion string
        
    Example Usage:
        # For non-production
        assertion = get_epic_client_assertion("your-client-id", "nonprod")
        
        # For production  
        assertion = get_epic_client_assertion("your-client-id", "prod")
    """
    token_url = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
    return create_client_assertion(client_id, token_url, environment)

def setup_instructions():
    """
    Print setup instructions for JWT keys
    """
    instructions = """
    JWT SETUP INSTRUCTIONS
    =====================
    
    To set up proper JWT keys for Epic integration:
    
    1. Generate RSA private keys (2048-bit) locally:
       openssl genrsa -out np-2025-08-a.key 2048
       openssl genrsa -out p-2025-08-a.key 2048
    
    2. Add these keys to Replit Secrets (in sidebar → Secrets):
       
       For Non-Production:
       Key: NP_KEY_2025_08_A
       Value: [paste entire contents of np-2025-08-a.key file]
       
       For Production:
       Key: P_KEY_2025_08_A  
       Value: [paste entire contents of p-2025-08-a.key file]
    
    3. Key rotation (optional - for when you need to rotate keys):
       Add additional keys with different suffixes:
       NP_KEY_2025_09_A (new non-prod key)
       P_KEY_2025_09_A (new prod key)
    
    4. Your JWKS URLs for Epic registration:
       Non-Production: https://healthprep-v-201.com/nonprod/.well-known/jwks.json
       Production: https://healthprep-v-201.com/.well-known/jwks.json
       
       Note: JWKS_BASE_URL environment variable can override the base domain.
    
    5. When creating client assertions, the system will automatically:
       - Use the first available key from environment variables
       - Generate a fallback key if no environment keys are found
       - Set the correct 'kid' (key ID) in the JWT header
    
    Key Naming Convention:
    - Non-prod keys: NP_KEY_[time_period]_[identifier]
    - Prod keys: P_KEY_[time_period]_[identifier] 
    - Example: NP_KEY_2025_08_A, P_KEY_2025_08_A
    
    The 'kid' value in JWTs will be the suffix after removing the prefix:
    - NP_KEY_2025_08_A → kid: "2025_08_A"
    - P_KEY_2025_08_A → kid: "2025_08_A"
    """
    print(instructions)

if __name__ == "__main__":
    setup_instructions()
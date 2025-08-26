#!/usr/bin/env python3
"""
Key rotation utility for HealthPrep JWT keys
Prints public JWK from private key PEM for adding to JWKS
"""

import json
import base64
import sys
from cryptography.hazmat.primitives import serialization

def b64u(b: bytes) -> str:
    """URL-safe base64 encoding without padding"""
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/print_public_jwk.py <kid> < private_key.pem")
        print("Example: python tools/print_public_jwk.py 2025_08_B < new_private_key.pem")
        sys.exit(1)
    
    kid = sys.argv[1]
    
    try:
        # Read PEM from stdin
        pem_content = sys.stdin.read().encode()
        
        # Load private key
        key = serialization.load_pem_private_key(pem_content, password=None)
        pub = key.public_key().public_numbers()
        
        # Convert to JWK format
        n_bytes = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
        e_bytes = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
        
        jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "n": b64u(n_bytes),
            "e": b64u(e_bytes)
        }
        
        # Print JWK
        print(json.dumps(jwk, indent=2))
        
        # Print usage instructions
        print("\n# Usage Instructions:", file=sys.stderr)
        print(f"# 1. Add this JWK to your JWKS endpoint alongside existing keys", file=sys.stderr)
        print(f"# 2. Update your environment variables:", file=sys.stderr)
        print(f"#    NP_KEY_{kid}=<private_key_pem>  (for non-prod)", file=sys.stderr)
        print(f"#    P_KEY_{kid}=<private_key_pem>   (for prod)", file=sys.stderr)
        print(f"# 3. Start signing JWTs with kid='{kid}'", file=sys.stderr)
        print(f"# 4. After token TTL expires, remove old keys", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
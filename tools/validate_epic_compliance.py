#!/usr/bin/env python3
"""
Epic SMART on FHIR Compliance Validation Tool
Validates all February 2024 Epic requirements for JWKS endpoints
"""

import requests
import json
import time
from typing import Dict, List, Tuple
import sys

class EpicComplianceValidator:
    """Validates Epic SMART on FHIR compliance requirements"""
    
    def __init__(self, base_url: str = None):
        # Use environment variable or parameter, with production domain as default
        import os
        if base_url is None:
            base_url = os.environ.get('JWKS_BASE_URL', 'https://healthprep-v-201.com')
        self.base_url = base_url.rstrip('/')
        self.results = []
    
    def log_result(self, test_name: str, passed: bool, message: str, details: Dict = None):
        """Log validation result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'details': details or {}
        }
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name} - {message}")
        if details:
            for key, value in details.items():
                print(f"    {key}: {value}")
    
    def test_jwks_endpoint(self, endpoint: str, expected_cache_max_age: int = None) -> bool:
        """Test JWKS endpoint compliance"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time
            
            # Test 1: HTTP 200 Status
            if response.status_code != 200:
                self.log_result(f"JWKS Status ({endpoint})", False, 
                              f"Expected 200, got {response.status_code}")
                return False
            
            # Test 2: Response Time (< 100ms for Epic)
            if response_time > 0.1:
                self.log_result(f"JWKS Response Time ({endpoint})", False,
                              f"Too slow: {response_time:.3f}s (max 0.1s)")
                return False
            
            # Test 3: Content Type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('application/json'):
                self.log_result(f"JWKS Content-Type ({endpoint})", False,
                              f"Expected application/json, got {content_type}")
                return False
            
            # Test 4: Valid JSON Structure
            try:
                jwks_data = response.json()
                if 'keys' not in jwks_data:
                    self.log_result(f"JWKS Structure ({endpoint})", False,
                                  "Missing 'keys' array in JWKS")
                    return False
                    
                if not isinstance(jwks_data['keys'], list):
                    self.log_result(f"JWKS Structure ({endpoint})", False,
                                  "'keys' is not an array")
                    return False
                    
                if len(jwks_data['keys']) == 0:
                    self.log_result(f"JWKS Structure ({endpoint})", False,
                                  "No keys found in JWKS")
                    return False
                    
            except json.JSONDecodeError as e:
                self.log_result(f"JWKS JSON ({endpoint})", False,
                              f"Invalid JSON: {e}")
                return False
            
            # Test 5: Valid RSA Key Format
            key = jwks_data['keys'][0]
            required_fields = ['kty', 'use', 'alg', 'kid', 'n', 'e']
            for field in required_fields:
                if field not in key:
                    self.log_result(f"JWKS Key Format ({endpoint})", False,
                                  f"Missing required field: {field}")
                    return False
            
            if key['kty'] != 'RSA':
                self.log_result(f"JWKS Key Type ({endpoint})", False,
                              f"Expected RSA, got {key['kty']}")
                return False
            
            if key['alg'] != 'RS256':
                self.log_result(f"JWKS Algorithm ({endpoint})", False,
                              f"Expected RS256, got {key['alg']}")
                return False
            
            # Test 6: Cache Headers
            cache_control = response.headers.get('cache-control', '')
            if expected_cache_max_age:
                if f"max-age={expected_cache_max_age}" not in cache_control:
                    self.log_result(f"JWKS Cache Headers ({endpoint})", False,
                                  f"Expected max-age={expected_cache_max_age}, got {cache_control}")
                    return False
            
            # Test 7: Security Headers
            if 'x-content-type-options' not in response.headers:
                self.log_result(f"JWKS Security Headers ({endpoint})", False,
                              "Missing X-Content-Type-Options header")
                return False
            
            self.log_result(f"JWKS Endpoint ({endpoint})", True,
                          f"All tests passed ({response_time:.3f}s)", {
                'status_code': response.status_code,
                'response_time': f"{response_time:.3f}s",
                'content_type': content_type,
                'cache_control': cache_control,
                'keys_count': len(jwks_data['keys']),
                'kid': key['kid']
            })
            return True
            
        except requests.RequestException as e:
            self.log_result(f"JWKS Network ({endpoint})", False,
                          f"Network error: {e}")
            return False
    
    def test_smart_configuration(self) -> bool:
        """Test SMART on FHIR configuration endpoint"""
        endpoint = "/.well-known/smart-configuration"
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                self.log_result("SMART Configuration", False,
                              f"Expected 200, got {response.status_code}")
                return False
            
            try:
                config = response.json()
                required_fields = ['authorization_endpoint', 'token_endpoint', 'capabilities']
                for field in required_fields:
                    if field not in config:
                        self.log_result("SMART Configuration", False,
                                      f"Missing required field: {field}")
                        return False
                
                self.log_result("SMART Configuration", True, "Valid configuration")
                return True
                
            except json.JSONDecodeError as e:
                self.log_result("SMART Configuration", False,
                              f"Invalid JSON: {e}")
                return False
                
        except requests.RequestException as e:
            self.log_result("SMART Configuration", False,
                          f"Network error: {e}")
            return False
    
    def test_static_fallbacks(self) -> bool:
        """Test static fallback endpoints"""
        endpoints = [
            "/static/.well-known/jwks.json",
            "/static/nonprod/.well-known/jwks.json"
        ]
        
        all_passed = True
        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    try:
                        jwks_data = response.json()
                        if 'keys' in jwks_data and len(jwks_data['keys']) > 0:
                            self.log_result(f"Static Fallback ({endpoint})", True,
                                          "Fallback available")
                        else:
                            self.log_result(f"Static Fallback ({endpoint})", False,
                                          "Invalid fallback JWKS")
                            all_passed = False
                    except json.JSONDecodeError:
                        self.log_result(f"Static Fallback ({endpoint})", False,
                                      "Invalid JSON in fallback")
                        all_passed = False
                else:
                    self.log_result(f"Static Fallback ({endpoint})", False,
                                  f"Status {response.status_code}")
                    all_passed = False
            except requests.RequestException as e:
                self.log_result(f"Static Fallback ({endpoint})", False,
                              f"Network error: {e}")
                all_passed = False
        
        return all_passed
    
    def run_full_validation(self) -> bool:
        """Run complete Epic compliance validation"""
        print(f"\n🔍 Epic SMART on FHIR Compliance Validation")
        print(f"Target: {self.base_url}")
        print("=" * 60)
        
        all_passed = True
        
        # Test SMART Configuration
        all_passed &= self.test_smart_configuration()
        
        # Test Production JWKS (24h cache)
        all_passed &= self.test_jwks_endpoint("/.well-known/jwks.json", 86400)
        
        # Test Non-Production JWKS (1h cache)  
        all_passed &= self.test_jwks_endpoint("/nonprod/.well-known/jwks.json", 3600)
        
        # Test Static Fallbacks
        all_passed &= self.test_static_fallbacks()
        
        print("\n" + "=" * 60)
        passed_count = sum(1 for r in self.results if r['passed'])
        total_count = len(self.results)
        
        if all_passed:
            print(f"🎉 ALL TESTS PASSED ({passed_count}/{total_count})")
            print("✅ Epic February 2024 compliance requirements met!")
            print("✅ Ready for Epic App Orchard registration!")
        else:
            print(f"❌ SOME TESTS FAILED ({passed_count}/{total_count})")
            print("❌ Fix issues before Epic registration")
        
        return all_passed

def main():
    """Main validation entry point"""
    import os
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        # Use environment variable or default to production domain
        base_url = os.environ.get('JWKS_BASE_URL', 'https://healthprep-v-201.com')
    
    validator = EpicComplianceValidator(base_url)
    success = validator.run_full_validation()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
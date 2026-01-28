#!/usr/bin/env python3
"""
Security Audit Script for HealthPrep
Validates security configurations and detects potential vulnerabilities.

Run this script as part of CI/CD pipeline or before deployment:
    python scripts/security_audit.py

Exit codes:
    0: All security checks passed
    1: Critical security issues found
    2: Warning-level issues found (production deployment discouraged)
"""

import os
import sys
import re
from pathlib import Path

CRITICAL_ISSUES = []
WARNINGS = []


def check_file_contains(filepath: str, patterns: list, should_exist: bool = True) -> list:
    """Check if file contains specific patterns"""
    findings = []
    try:
        content = Path(filepath).read_text()
        for pattern, description, severity in patterns:
            if re.search(pattern, content):
                if should_exist:
                    pass  # Pattern found as expected
                else:
                    findings.append((severity, description, filepath))
            else:
                if should_exist:
                    findings.append((severity, description, filepath))
    except FileNotFoundError:
        findings.append(('warning', f'File not found: {filepath}', filepath))
    return findings


def audit_cors_configuration():
    """Check CORS is not configured to allow all origins in production code"""
    print("Checking CORS configuration...")
    
    patterns = [
        (r'"origins":\s*"\*"', 'CORS allows all origins - use environment-based whitelist', 'critical'),
        (r"'origins':\s*'\*'", 'CORS allows all origins - use environment-based whitelist', 'critical'),
    ]
    
    findings = check_file_contains('app.py', patterns, should_exist=False)
    
    for severity, msg, filepath in findings:
        if severity == 'critical':
            CRITICAL_ISSUES.append(f"[{filepath}] {msg}")
        else:
            WARNINGS.append(f"[{filepath}] {msg}")


def audit_hardcoded_secrets():
    """Check for hardcoded secrets and credentials"""
    print("Checking for hardcoded secrets...")
    
    patterns = [
        (r'(?i)(password|secret|api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']', 
         'Potential hardcoded secret/password', 'critical'),
        (r'sk_live_[a-zA-Z0-9]{24,}', 'Hardcoded Stripe live key', 'critical'),
        (r'sk_test_[a-zA-Z0-9]{24,}', 'Hardcoded Stripe test key', 'warning'),
    ]
    
    files_to_check = list(Path('.').rglob('*.py'))
    excluded = [
        'node_modules', 'venv', '__pycache__', '.git', 
        'scripts/security_audit.py', '.cache', '.pythonlibs',
        'archive', 'migrations', 'tests', '.upm'
    ]
    
    for filepath in files_to_check:
        if any(ex in str(filepath) for ex in excluded):
            continue
        
        findings = check_file_contains(str(filepath), patterns, should_exist=False)
        for severity, msg, fp in findings:
            if severity == 'critical':
                CRITICAL_ISSUES.append(f"[{fp}] {msg}")
            else:
                WARNINGS.append(f"[{fp}] {msg}")


def audit_production_requirements():
    """Check that production security requirements are enforced"""
    print("Checking production security requirements...")
    
    # Check encryption enforcement
    encryption_patterns = [
        (r'ENCRYPTION_KEY.*production.*raise|raise.*ENCRYPTION_KEY', 
         'ENCRYPTION_KEY must be enforced in production', 'critical'),
    ]
    
    if not Path('utils/encryption.py').exists():
        CRITICAL_ISSUES.append("Missing encryption utility: utils/encryption.py")
    else:
        content = Path('utils/encryption.py').read_text()
        if 'is_production' not in content or 'raise' not in content:
            WARNINGS.append("[utils/encryption.py] ENCRYPTION_KEY enforcement may not be production-ready")
    
    # Check SQLite fallback prevention
    if Path('app.py').exists():
        content = Path('app.py').read_text()
        if 'SQLite is not allowed in production' not in content:
            WARNINGS.append("[app.py] SQLite fallback may not be blocked in production")


def audit_security_headers():
    """Check security headers are properly configured"""
    print("Checking security headers...")
    
    required_headers = [
        'Strict-Transport-Security',
        'X-Frame-Options',
        'X-Content-Type-Options',
        'Content-Security-Policy',
        'Referrer-Policy',
    ]
    
    if Path('utils/security_headers.py').exists():
        content = Path('utils/security_headers.py').read_text()
        for header in required_headers:
            if header not in content:
                WARNINGS.append(f"[utils/security_headers.py] Missing header: {header}")
    else:
        CRITICAL_ISSUES.append("Missing security headers utility: utils/security_headers.py")


def audit_rate_limiting():
    """Check rate limiting is implemented"""
    print("Checking rate limiting...")
    
    if Path('utils/security.py').exists():
        content = Path('utils/security.py').read_text()
        if 'RateLimiter' not in content:
            WARNINGS.append("[utils/security.py] Rate limiting class not found")
        if 'redis' not in content.lower():
            WARNINGS.append("[utils/security.py] Redis rate limiting not implemented (required for multi-instance)")
    else:
        CRITICAL_ISSUES.append("Missing security utility: utils/security.py")


def audit_phi_protection():
    """Check PHI filtering is implemented"""
    print("Checking PHI protection...")
    
    if Path('ocr/phi_filter.py').exists():
        content = Path('ocr/phi_filter.py').read_text()
        required_patterns = ['ssn', 'phone', 'email', 'mrn', 'REDACTED']
        for pattern in required_patterns:
            if pattern.lower() not in content.lower():
                WARNINGS.append(f"[ocr/phi_filter.py] PHI filter may be missing: {pattern}")
    else:
        CRITICAL_ISSUES.append("Missing PHI filter: ocr/phi_filter.py")


def audit_csrf_protection():
    """Check CSRF protection is enabled"""
    print("Checking CSRF protection...")
    
    if Path('app.py').exists():
        content = Path('app.py').read_text()
        if 'CSRFProtect' not in content:
            CRITICAL_ISSUES.append("[app.py] CSRF protection not imported")
        if 'csrf.init_app' not in content:
            CRITICAL_ISSUES.append("[app.py] CSRF protection not initialized")


def print_results():
    """Print audit results"""
    print("\n" + "=" * 60)
    print("SECURITY AUDIT RESULTS")
    print("=" * 60)
    
    if CRITICAL_ISSUES:
        print(f"\n🚨 CRITICAL ISSUES ({len(CRITICAL_ISSUES)}):")
        for issue in CRITICAL_ISSUES:
            print(f"   ❌ {issue}")
    
    if WARNINGS:
        print(f"\n⚠️  WARNINGS ({len(WARNINGS)}):")
        for warning in WARNINGS:
            print(f"   ⚠️  {warning}")
    
    if not CRITICAL_ISSUES and not WARNINGS:
        print("\n✅ All security checks passed!")
        return 0
    elif CRITICAL_ISSUES:
        print("\n❌ CRITICAL issues found - DO NOT deploy to production")
        return 1
    else:
        print("\n⚠️  Warnings found - review before production deployment")
        return 2


def main():
    """Run all security audits"""
    print("=" * 60)
    print("HealthPrep Security Audit")
    print("=" * 60 + "\n")
    
    audit_cors_configuration()
    audit_hardcoded_secrets()
    audit_production_requirements()
    audit_security_headers()
    audit_rate_limiting()
    audit_phi_protection()
    audit_csrf_protection()
    
    exit_code = print_results()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

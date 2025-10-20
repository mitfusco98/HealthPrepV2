"""
Secrets and environment variable validation

Validates that all required environment variables are present on application startup.
Fails fast with helpful error messages if critical secrets are missing.
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SecretsValidationError(Exception):
    """Raised when required secrets are missing or invalid"""
    pass


class SecretsValidator:
    """
    Validates required environment variables and secrets on application startup
    """
    
    # Required secrets for all environments
    REQUIRED_SECRETS = [
        'SECRET_KEY',
        'DATABASE_URL',
    ]
    
    # Optional secrets with warnings if missing
    OPTIONAL_SECRETS = [
        'ENCRYPTION_KEY',  # Required for Epic credential encryption
    ]
    
    # Production-only required secrets
    PRODUCTION_SECRETS = [
        'ENCRYPTION_KEY',  # MUST have encryption in production
    ]
    
    @staticmethod
    def validate_all(environment: str = 'development') -> None:
        """
        Validate all required secrets are present
        
        Args:
            environment: Current environment ('development', 'production', 'testing')
        
        Raises:
            SecretsValidationError: If required secrets are missing
        """
        missing_secrets = []
        warnings = []
        
        # Check required secrets
        for secret in SecretsValidator.REQUIRED_SECRETS:
            if not os.environ.get(secret):
                missing_secrets.append(secret)
        
        # Check production-specific secrets
        if environment == 'production':
            for secret in SecretsValidator.PRODUCTION_SECRETS:
                if not os.environ.get(secret):
                    missing_secrets.append(secret)
        
        # Check optional secrets (warnings only)
        for secret in SecretsValidator.OPTIONAL_SECRETS:
            if not os.environ.get(secret):
                if secret not in SecretsValidator.PRODUCTION_SECRETS or environment != 'production':
                    warnings.append(secret)
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"Optional secret {warning} is not set - some features may be disabled")
        
        # Fail if required secrets are missing
        if missing_secrets:
            error_msg = (
                f"Missing required environment variables: {', '.join(missing_secrets)}\n\n"
                f"Required secrets:\n"
            )
            
            for secret in missing_secrets:
                hint = SecretsValidator._get_secret_hint(secret)
                error_msg += f"  - {secret}: {hint}\n"
            
            error_msg += "\nAdd these secrets to your environment before starting the application."
            raise SecretsValidationError(error_msg)
        
        logger.info(f"Secrets validation passed for {environment} environment")
    
    @staticmethod
    def _get_secret_hint(secret_name: str) -> str:
        """Get a helpful hint for generating/obtaining a secret"""
        hints = {
            'SECRET_KEY': "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'",
            'ENCRYPTION_KEY': "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
            'DATABASE_URL': "PostgreSQL connection string (e.g., postgresql://user:pass@host/db)",
        }
        return hints.get(secret_name, "Set this environment variable")
    
    @staticmethod
    def validate_secret_format(secret_name: str, value: str) -> bool:
        """
        Validate that a secret has the correct format
        
        Args:
            secret_name: Name of the secret to validate
            value: Value to validate
        
        Returns:
            True if valid, False otherwise
        """
        if secret_name == 'SECRET_KEY':
            # Should be at least 32 characters for security
            if len(value) < 32:
                logger.warning(f"{secret_name} should be at least 32 characters for security")
                return False
        
        elif secret_name == 'ENCRYPTION_KEY':
            # Should be a valid Fernet key (44 characters, base64-encoded)
            if len(value) != 44:
                logger.warning(f"{secret_name} should be 44 characters (valid Fernet key)")
                return False
        
        elif secret_name == 'DATABASE_URL':
            # Should start with postgresql:// or postgres://
            if not (value.startswith('postgresql://') or value.startswith('postgres://')):
                logger.warning(f"{secret_name} should be a PostgreSQL connection string")
                return False
        
        return True
    
    @staticmethod
    def get_validation_report() -> Dict[str, any]:
        """
        Get a report of all secrets and their status
        
        Returns:
            Dictionary with secret names and validation status
        """
        report = {
            'required': {},
            'optional': {},
            'production_only': {}
        }
        
        for secret in SecretsValidator.REQUIRED_SECRETS:
            value = os.environ.get(secret)
            report['required'][secret] = {
                'present': bool(value),
                'valid': SecretsValidator.validate_secret_format(secret, value) if value else False
            }
        
        for secret in SecretsValidator.OPTIONAL_SECRETS:
            value = os.environ.get(secret)
            report['optional'][secret] = {
                'present': bool(value),
                'valid': SecretsValidator.validate_secret_format(secret, value) if value else False
            }
        
        for secret in SecretsValidator.PRODUCTION_SECRETS:
            value = os.environ.get(secret)
            report['production_only'][secret] = {
                'present': bool(value),
                'valid': SecretsValidator.validate_secret_format(secret, value) if value else False
            }
        
        return report


def validate_secrets_on_startup(environment: str = 'development') -> None:
    """
    Convenience function to validate secrets on application startup
    
    Args:
        environment: Current environment
    
    Raises:
        SecretsValidationError: If validation fails
    """
    SecretsValidator.validate_all(environment)

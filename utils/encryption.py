"""
Field-level encryption utilities for sensitive data

Uses Fernet symmetric encryption for encrypting sensitive database fields:
- Epic OAuth credentials (client secrets, access/refresh tokens)
- Any other sensitive configuration data

Encryption key must be provided via ENCRYPTION_KEY environment variable.
Key should be generated using: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive database fields
    """
    
    def __init__(self):
        self._cipher = None
        self._key_loaded = False
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize Fernet cipher from environment variable"""
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        
        if not encryption_key:
            logger.warning(
                "ENCRYPTION_KEY not set - encryption disabled. "
                "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
            return
        
        try:
            # Encryption key should be a base64-encoded 32-byte key
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            
            self._cipher = Fernet(encryption_key)
            self._key_loaded = True
            logger.info("Encryption service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise EncryptionError(f"Invalid encryption key: {str(e)}")
    
    def is_enabled(self) -> bool:
        """Check if encryption is enabled"""
        return self._key_loaded and self._cipher is not None
    
    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a plaintext string
        
        Args:
            plaintext: String to encrypt (can be None)
        
        Returns:
            Base64-encoded encrypted string, or None if input is None
        
        Raises:
            EncryptionError: If encryption fails or service not initialized
        """
        if plaintext is None:
            return None
        
        if not self.is_enabled():
            logger.warning("Encryption not enabled - storing value in plaintext")
            return plaintext
        
        try:
            plaintext_bytes: bytes
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext
            
            encrypted_bytes = self._cipher.encrypt(plaintext_bytes)  # type: ignore
            return encrypted_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypt an encrypted string
        
        Args:
            ciphertext: Base64-encoded encrypted string (can be None)
        
        Returns:
            Decrypted plaintext string, or None if input is None
        
        Raises:
            EncryptionError: If decryption fails
        """
        if ciphertext is None:
            return None
        
        if not self.is_enabled():
            logger.warning("Encryption not enabled - returning value as-is")
            return str(ciphertext) if ciphertext else None
        
        try:
            # Validate input type
            if not isinstance(ciphertext, (str, bytes)):
                logger.error(f"Invalid ciphertext type: {type(ciphertext)}. Expected str or bytes.")
                raise EncryptionError(f"Invalid ciphertext type: {type(ciphertext).__name__}")
            
            ciphertext_bytes: bytes
            if isinstance(ciphertext, str):
                ciphertext_bytes = ciphertext.encode('utf-8')
            else:
                ciphertext_bytes = ciphertext
            
            decrypted_bytes = self._cipher.decrypt(ciphertext_bytes)  # type: ignore
            return decrypted_bytes.decode('utf-8')
            
        except InvalidToken:
            logger.error("Decryption failed - invalid token or corrupted data")
            raise EncryptionError("Failed to decrypt data - token is invalid or data is corrupted")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise EncryptionError(f"Failed to decrypt data: {str(e)}")
    
    def rotate_key(self, old_key: str, new_key: str, encrypted_value: str) -> str:
        """
        Rotate encryption key by decrypting with old key and re-encrypting with new key
        
        Args:
            old_key: Previous encryption key
            new_key: New encryption key to use
            encrypted_value: Value encrypted with old key
        
        Returns:
            Value re-encrypted with new key
        """
        try:
            # Decrypt with old key
            old_cipher = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
            plaintext = old_cipher.decrypt(
                encrypted_value.encode() if isinstance(encrypted_value, str) else encrypted_value
            )
            
            # Encrypt with new key
            new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)
            new_encrypted = new_cipher.encrypt(plaintext)
            
            return new_encrypted.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Key rotation failed: {str(e)}")
            raise EncryptionError(f"Failed to rotate encryption key: {str(e)}")


# Global encryption service instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance"""
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service


# Convenience functions
def encrypt_field(value: Optional[str]) -> Optional[str]:
    """Encrypt a database field value"""
    return get_encryption_service().encrypt(value)


def decrypt_field(value: Optional[str]) -> Optional[str]:
    """Decrypt a database field value"""
    return get_encryption_service().decrypt(value)


def is_encryption_enabled() -> bool:
    """Check if encryption is currently enabled"""
    return get_encryption_service().is_enabled()

"""Encryption utilities for Renine.

Provides Fernet symmetric encryption for sensitive fields stored
in local databases (passwords, financial data, etc.).

The encryption key is loaded from the FERNET_KEY environment variable.
This module is never imported by external API call paths.

Inputs:
    - Plaintext strings to encrypt.
    - Ciphertext bytes to decrypt.
    - FERNET_KEY from .env via python-dotenv.

Outputs:
    - Encrypted bytes (for storage).
    - Decrypted strings (for local use only).
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from renine.core.exceptions import EncryptionError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_fernet() -> Fernet:
    """Create a Fernet instance from the environment key.

    Returns:
        Configured Fernet encryption instance.

    Raises:
        EncryptionError: If FERNET_KEY is not set or is invalid.
    """
    key = os.environ.get("FERNET_KEY")
    if not key:
        raise EncryptionError(
            "FERNET_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise EncryptionError(f"Invalid FERNET_KEY: {e}") from e


def encrypt(plaintext: str) -> bytes:
    """Encrypt a plaintext string using Fernet symmetric encryption.

    Args:
        plaintext: The string to encrypt.

    Returns:
        Encrypted bytes suitable for database storage.

    Raises:
        EncryptionError: If encryption fails.
    """
    try:
        f = _get_fernet()
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        logger.debug("data_encrypted", length=len(plaintext))
        return encrypted
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def decrypt(ciphertext: bytes) -> str:
    """Decrypt Fernet-encrypted bytes back to plaintext.

    Args:
        ciphertext: Encrypted bytes from a previous encrypt() call.

    Returns:
        Decrypted plaintext string.

    Raises:
        EncryptionError: If decryption fails (wrong key, corrupted data).
    """
    try:
        f = _get_fernet()
        decrypted = f.decrypt(ciphertext)
        logger.debug("data_decrypted")
        return decrypted.decode("utf-8")
    except InvalidToken as e:
        raise EncryptionError(
            "Decryption failed — invalid key or corrupted data."
        ) from e
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {e}") from e


def generate_key() -> str:
    """Generate a new Fernet encryption key.

    Returns:
        URL-safe base64-encoded key string.
    """
    key = Fernet.generate_key().decode("utf-8")
    logger.info("new_fernet_key_generated")
    return key

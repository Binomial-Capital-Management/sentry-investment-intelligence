"""
Simple cryptographic helpers for symmetric encryption.
Encapsulates Fernet usage so callers do not import cryptography directly.
"""

from __future__ import annotations

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet(key: str) -> Fernet:
    """Build a Fernet instance from the provided key."""
    if not key:
        raise ValueError("Encryption key is required for Google Drive integration")
    return Fernet(key)


def encrypt_string(value: str, key: str) -> str:
    """Encrypt a string value and return a safe token."""
    if value is None:
        raise ValueError("Cannot encrypt None value")
    fernet = _get_fernet(key)
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_string(token: str, key: str) -> Optional[str]:
    """Decrypt a string token. Returns None when decryption fails."""
    if not token:
        return None
    try:
        fernet = _get_fernet(key)
        value = fernet.decrypt(token.encode("utf-8"))
        return value.decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt token: invalid encryption key or corrupted payload")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Unexpected error decrypting token: {exc}")
    return None

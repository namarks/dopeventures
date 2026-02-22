"""
Token encryption for Dopetracks database.

Uses Fernet symmetric encryption to protect tokens at rest.
The encryption key is stored in a file alongside the SQLite database,
readable only by the current user (chmod 600).
"""
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

logger = logging.getLogger(__name__)

_KEY_FILENAME = "token.key"
_fernet_instance: Optional[Fernet] = None


def _key_path() -> Path:
    """Return path to the encryption key file (~/.dopetracks/token.key)."""
    return Path.home() / ".dopetracks" / _KEY_FILENAME


def _load_or_create_key() -> bytes:
    """Load the Fernet key from disk, or generate and persist a new one."""
    kp = _key_path()
    if kp.exists():
        return kp.read_bytes().strip()

    key = Fernet.generate_key()
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_bytes(key)
    # Restrict to owner-only read/write
    os.chmod(kp, 0o600)
    logger.info("Generated new token encryption key at %s", kp)
    return key


def get_fernet() -> Fernet:
    """Return a cached Fernet instance."""
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(_load_or_create_key())
    return _fernet_instance


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy type that transparently encrypts/decrypts text values
    using Fernet. Stored as a base64-encoded ciphertext string in the DB.
    Gracefully handles legacy plaintext values from before encryption was added.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            # Legacy plaintext value — return as-is so existing tokens still work.
            # They will be re-encrypted on next write (token refresh / re-auth).
            logger.debug("Token column contains unencrypted value; returning as plaintext")
            return value

"""
helpers/encryption.py

AES-Fernet symmetric encryption for OAuth tokens stored in DB.

Usage:
    encrypted = encrypt_token("ya29.abc123...")
    plain     = decrypt_token(encrypted)

Requires env var:
    ENCRYPTION_KEY  — 32-byte URL-safe base64 Fernet key.

Generate a key once and store it in your secrets manager:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
"""

import os
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status


def get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plain: str) -> str:
    """
    Encrypt a plaintext string and return a URL-safe base64 ciphertext string.
    Raises ValueError if plain is empty.
    """
    if not plain or not plain.strip():
        raise ValueError("Cannot encrypt an empty token.")
    return get_fernet().encrypt(plain.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a ciphertext string back to plaintext.
    Raises HTTP 401 if the ciphertext has been tampered with or the key changed.
    """
    try:
        return get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Token decryption failed — the stored token is invalid or the "
                "encryption key changed. Please reconnect your Google account."
            ),
        )
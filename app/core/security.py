"""
Security utilities for the AI Gateway Perimetral.

Responsibilities:
    - Client Bearer token validation using constant-time SHA-256 comparison.
    - Cryptographic canary token generation for egress integrity tracking.
"""

import hashlib
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

# HTTPBearer scheme used to extract the Authorization header.
_bearer_scheme = HTTPBearer(auto_error=True)


def hash_token(raw_token: str) -> str:
    """
    Computes the SHA-256 hex digest of a raw token string.

    This function is used both to pre-compute hashes for the .env file
    and to hash incoming tokens before comparison.

    Args:
        raw_token: The plain-text token string.

    Returns:
        A lowercase hexadecimal string representing the SHA-256 digest.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_client_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI dependency that validates the client's Bearer token.

    Validation is performed using a constant-time comparison (secrets.compare_digest)
    to prevent timing-based side-channel attacks. The raw token is never stored;
    only its SHA-256 hash is compared against the pre-approved hashes in the
    configuration.

    Args:
        credentials: Extracted Bearer token from the Authorization header.
        settings: Application settings injected by FastAPI.

    Returns:
        The raw token string if authentication succeeds.

    Raises:
        HTTPException(401): When authentication is required and the token is
                            missing, malformed, or not in the approved list.
    """
    if not settings.gateway_auth_required:
        return credentials.credentials

    raw_token = credentials.credentials
    incoming_hash = hash_token(raw_token)

    # Compare against all approved hashes using constant-time comparison
    # to prevent timing attacks that could reveal valid hash prefixes.
    is_valid = any(
        secrets.compare_digest(incoming_hash, approved_hash)
        for approved_hash in settings.allowed_hashes_set
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unauthorized client token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return raw_token


def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI dependency that validates the admin Bearer token.

    Used to protect SOC / audit management endpoints:
        - /v1/notifications/recipients
        - /v1/audit/*
        - /v1/gateway/reset-vault

    Validation is performed using constant-time SHA-256 comparison to prevent
    timing-based side-channel attacks. Admin tokens are stored only as hashes
    in ALLOWED_ADMIN_API_KEYS_HASHES.

    Args:
        credentials: Extracted Bearer token from the Authorization header.
        settings: Application settings injected by FastAPI.

    Returns:
        The raw token string if authentication succeeds.

    Raises:
        HTTPException(401): When the token is missing or malformed.
        HTTPException(403): When the token is valid but lacks admin privileges.
    """
    if not settings.gateway_auth_required:
        return credentials.credentials

    raw_token = credentials.credentials
    incoming_hash = hash_token(raw_token)

    is_valid = any(
        secrets.compare_digest(incoming_hash, approved_hash)
        for approved_hash in settings.allowed_admin_hashes_set
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required. Invalid or unauthorized admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return raw_token


def generate_canary_token(settings: Settings) -> str:
    """
    Generates a cryptographically secure canary token for a single request.

    The token is constructed as: <prefix><hex_random_bytes>
    It is injected into the LLM prompt as a secret that the model must
    never echo back to the user. If it appears in the LLM response,
    Layer 5 (Egress Scan) treats it as a context leakage event.

    Args:
        settings: Application settings providing the prefix and entropy size.

    Returns:
        A unique canary token string, e.g. "BnkCanary_3f8a1c72d4e9b501".
    """
    random_hex = secrets.token_hex(settings.canary_token_entropy_bytes)
    return f"{settings.canary_prefix}{random_hex}"

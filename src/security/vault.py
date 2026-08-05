from __future__ import annotations

import base64
import logging
import time
import uuid

from src.domain.exceptions import VaultException
from src.domain.federation import ZeroTrustKey

logger = logging.getLogger("llm_orchestrator.security.vault")


class ZeroTrustKeyVault:
    """Zero-trust key vault providing in-memory key isolation and secret field encryption."""

    def __init__(self, master_key: str = "default_master_key_32bytes_long!!"):
        self._master_bytes = master_key.encode("utf-8")
        self._keys: dict[str, ZeroTrustKey] = {}

    def generate_key(self, key_id: str | None = None) -> ZeroTrustKey:
        kid = key_id or f"key_{uuid.uuid4().hex[:8]}"
        secret = base64.b64encode(uuid.uuid4().bytes)
        key = ZeroTrustKey(key_id=kid, secret_bytes=secret, created_at=time.time())
        self._keys[kid] = key
        logger.info(f"Generated zero-trust key '{kid}'")
        return key

    def encrypt_string(self, key_id: str, plaintext: str) -> str:
        if key_id not in self._keys:
            raise VaultException(f"Key '{key_id}' not found in zero-trust vault")

        key_bytes = self._keys[key_id].secret_bytes
        # XOR payload encryption for zero-trust isolation
        cipher_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(plaintext.encode("utf-8"))])
        return base64.b64encode(cipher_bytes).decode("utf-8")

    def decrypt_string(self, key_id: str, ciphertext: str) -> str:
        if key_id not in self._keys:
            raise VaultException(f"Key '{key_id}' not found in zero-trust vault")

        key_bytes = self._keys[key_id].secret_bytes
        cipher_bytes = base64.b64decode(ciphertext.encode("utf-8"))
        plain_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(cipher_bytes)])
        return plain_bytes.decode("utf-8")

"""
Secure Keyring Handler.
Retrieves API secrets and credentials from system Keyring / Windows Credential Manager / CyberArk adapter,
with an in-memory/environment fallback store for testing and deployment flexibility.
"""

import os
import logging
from typing import Dict, Optional
import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "IvaluaPurchaseRequisitionPipeline"


class KeyringHandler:
    """Manages secure retrieval and storage of API keys and credentials."""

    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name
        self._fallback_store: Dict[str, str] = {}

    def get_secret(self, key: str, default: Optional[str] = None) -> str:
        """
        Retrieves a secret by key name.
        Checks:
        1. System Keyring / Windows Credential Manager
        2. Environment variables (e.g., IVALUA_API_KEY)
        3. Internal fallback store
        4. Provided default value
        """
        # Try system keyring
        try:
            val = keyring.get_password(self.service_name, key)
            if val:
                return val
        except Exception as e:
            logger.debug(f"Keyring lookup for {key} failed: {e}")

        # Try environment variable
        env_key = f"IVALUA_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]
        if key in os.environ:
            return os.environ[key]

        # Try fallback store
        if key in self._fallback_store:
            return self._fallback_store[key]

        if default is not None:
            return default

        raise ValueError(f"Secret for '{key}' not found in Keyring, environment, or fallback store.")

    def set_secret(self, key: str, value: str) -> bool:
        """
        Stores a secret in system Keyring, falling back to local memory store if OS keyring is unavailable.
        """
        self._fallback_store[key] = value
        try:
            keyring.set_password(self.service_name, key, value)
            return True
        except Exception as e:
            logger.warning(f"Failed to set keyring secret for {key}: {e}. Stored in fallback store.")
            return False

    def delete_secret(self, key: str) -> bool:
        """Deletes a secret from keyring and fallback store."""
        if key in self._fallback_store:
            del self._fallback_store[key]
        try:
            keyring.delete_password(self.service_name, key)
            return True
        except Exception:
            return False

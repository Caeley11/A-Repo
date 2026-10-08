"""
Tests for Secure Keyring Handler (`src/keyring_handler.py`).
"""

import os
import pytest
from src.keyring_handler import KeyringHandler


def test_keyring_fallback_and_environment(monkeypatch):
    kh = KeyringHandler(service_name="TestService")

    # Set secret in fallback store
    kh.set_secret("db_password", "SecretPass123!")
    assert kh.get_secret("db_password") == "SecretPass123!"

    # Test environment variable override
    monkeypatch.setenv("IVALUA_API_TOKEN", "EnvToken999")
    assert kh.get_secret("api_token") == "EnvToken999"

    # Test default value
    assert kh.get_secret("non_existent_key", default="DefaultVal") == "DefaultVal"

    # Test missing secret raises ValueError
    with pytest.raises(ValueError):
        kh.get_secret("definitely_missing_secret_key")


def test_keyring_delete_secret():
    kh = KeyringHandler(service_name="TestService")
    kh.set_secret("temp_token", "abc123xyz")
    assert kh.get_secret("temp_token") == "abc123xyz"

    kh.delete_secret("temp_token")
    with pytest.raises(ValueError):
        kh.get_secret("temp_token")

import pytest

from src.domain.exceptions import VaultException
from src.security.vault import ZeroTrustKeyVault


def test_zero_trust_key_vault():
    vault = ZeroTrustKeyVault()

    key = vault.generate_key("k_secret_01")
    assert key.key_id == "k_secret_01"

    plaintext = "Sensitive Enterprise API Secret Key"
    ciphertext = vault.encrypt_string("k_secret_01", plaintext)
    assert ciphertext != plaintext

    decrypted = vault.decrypt_string("k_secret_01", ciphertext)
    assert decrypted == plaintext

    with pytest.raises(VaultException, match="not found"):
        vault.encrypt_string("missing_key", "test")

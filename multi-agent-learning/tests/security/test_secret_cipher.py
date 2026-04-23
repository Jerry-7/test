from security.secret_cipher import SecretCipher


def test_secret_cipher_round_trips_plaintext():
    cipher = SecretCipher("local-dev-master-key")

    encrypted = cipher.encrypt("sk-test-123456")

    assert encrypted != "sk-test-123456"
    assert cipher.decrypt(encrypted) == "sk-test-123456"

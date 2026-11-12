"""Stateless password helpers. This module owns no users, roles, sessions or database."""
import base64, hashlib, hmac, secrets

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

def hash_password(password: str) -> str:
    salt=secrets.token_bytes(16); rounds=310_000
    digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64(salt)}${_b64(digest)}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, digest=encoded.split('$')
        if scheme!='pbkdf2_sha256': return False
        candidate=hashlib.pbkdf2_hmac('sha256',password.encode(),_unb64(salt),int(rounds))
        return hmac.compare_digest(candidate,_unb64(digest))
    except Exception:
        return False

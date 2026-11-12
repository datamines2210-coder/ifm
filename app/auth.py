import base64, hashlib, hmac, json, secrets, time
from .config import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, digest = encoded.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), _unb64(salt), int(rounds))
        return hmac.compare_digest(candidate, _unb64(digest))
    except Exception:
        return False


def _secret() -> bytes:
    return settings.auth_secret.encode()


def create_token(user_id: str, email: str, expires_in: int = 60 * 60 * 24 * 7, role: str = "customer") -> str:
    # Session state is persisted separately so the server can enforce idle expiry.
    session_id = secrets.token_urlsafe(24)
    now = int(time.time())
    try:
        from .db import create_auth_session
        create_auth_session(session_id, user_id, email, role, now, now + expires_in)
    except Exception:
        # Token creation must remain available during early application bootstrap/tests.
        pass
    header = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    payload = _b64(json.dumps({'sub': user_id, 'email': email, 'role': role, 'sid': session_id, 'iat': now, 'exp': now + expires_in}, separators=(',', ':')).encode())
    signing = f'{header}.{payload}'.encode()
    sig = _b64(hmac.new(_secret(), signing, hashlib.sha256).digest())
    return f'{header}.{payload}.{sig}'


def decode_token(token: str) -> dict | None:
    try:
        header, payload, sig = token.split('.')
        expected = _b64(hmac.new(_secret(), f'{header}.{payload}'.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get('exp', 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def touch_session(token_data: dict, ip_address: str = "", user_agent: str = "") -> bool:
    sid = token_data.get("sid")
    if not sid:
        return False
    try:
        from .db import touch_auth_session
        return touch_auth_session(sid, int(time.time()), ip_address, user_agent)
    except Exception:
        return False

def revoke_session(token_data: dict) -> None:
    sid = token_data.get("sid")
    if not sid:
        return
    try:
        from .db import revoke_auth_session
        revoke_auth_session(sid, int(time.time()))
    except Exception:
        pass

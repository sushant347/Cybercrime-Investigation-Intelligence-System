"""Admin role — shared-password authentication, no database, no user accounts.

An investigator uses the engine anonymously. An **administrator** additionally
proves knowledge of a shared password (``settings.ADMIN_PASSWORD``, default
``hello123``, override with ``CIIS_ADMIN_PASSWORD``) and receives a signed,
expiring token. The token is a cryptographic signature produced with Django's
``SECRET_KEY`` - it is *stateless*, so no session table or database is needed:
validity is proven by verifying the signature and its age.

Admin capabilities: list every case (normally private) and delete a case.
"""

from __future__ import annotations

import hmac

from django.conf import settings
from django.core import signing

_SALT = "ciis.admin.token"


def password_is_correct(password: str) -> bool:
    """Constant-time comparison against the configured admin password."""
    expected = str(getattr(settings, "ADMIN_PASSWORD", "") or "")
    if not expected:
        return False
    return hmac.compare_digest(str(password or ""), expected)


def issue_token() -> str:
    """Signed, timestamped admin token (verified by :func:`token_is_valid`)."""
    return signing.dumps({"role": "admin"}, salt=_SALT)


def token_is_valid(token: str) -> bool:
    """True when ``token`` is a genuine, unexpired admin token."""
    if not token:
        return False
    max_age = int(getattr(settings, "ADMIN_TOKEN_MAX_AGE", 8 * 3600))
    try:
        data = signing.loads(token, salt=_SALT, max_age=max_age)
    except signing.BadSignature:
        return False
    return isinstance(data, dict) and data.get("role") == "admin"

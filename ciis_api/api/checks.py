"""Deployment safety checks, run by ``manage.py check`` and every ``runserver``.

This platform is deliberately **open access**: there are no user accounts, and
an investigator reaches a case by knowing its reference (see SECURITY.md). That
is a defensible choice for a single-operator forensic workstation and an
indefensible one for anything reachable from a network, so the difference
between those two deployments must not be silent.

Django's system-check framework is the right place for this: the messages
appear on every start, they carry stable ids that can be silenced deliberately
via ``SILENCED_SYSTEM_CHECKS``, and nothing here changes behaviour. A warning
an operator chooses to ignore is a decision; a risk nobody mentioned is an
accident.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning as CheckWarning, register

#: Hosts that mean "this machine only". Anything else is reachable by someone
#: other than the person sitting at the keyboard.
_LOCAL_ONLY = {"localhost", "127.0.0.1", "::1", "testserver"}

#: Shipped default in settings.py. Present so a fresh clone runs; catastrophic
#: if it survives into a deployment, because the admin surface deletes cases.
_DEFAULT_ADMIN_PASSWORD = "hello123"


def _is_networked() -> bool:
    """True when ALLOWED_HOSTS admits anything beyond this machine."""
    hosts = {h.strip().lower() for h in settings.ALLOWED_HOSTS if h.strip()}
    return bool(hosts - _LOCAL_ONLY)


@register()
def check_admin_password(app_configs, **kwargs):
    """The admin surface can delete cases; its password must not be the default."""
    if getattr(settings, "ADMIN_PASSWORD", "") != _DEFAULT_ADMIN_PASSWORD:
        return []

    message = (
        "CIIS_ADMIN_PASSWORD is still the shipped default. The admin surface "
        "can delete cases and reset storage."
    )
    hint = "Set CIIS_ADMIN_PASSWORD to a value chosen for this deployment."

    # On a networked or production deployment this is not advice.
    if _is_networked() or not settings.DEBUG:
        return [Error(message, hint=hint, id="ciis.E001")]
    return [CheckWarning(
        message + " Acceptable only because this instance is bound to "
        "localhost with DEBUG on.", hint=hint, id="ciis.W001")]


@register()
def check_open_access_exposure(app_configs, **kwargs):
    """Open access is a workstation posture, not a network one."""
    if not _is_networked():
        return []
    return [CheckWarning(
        "The API has no authentication - every case, evidence item and report "
        f"is readable by anyone who can reach it - and ALLOWED_HOSTS "
        f"({', '.join(settings.ALLOWED_HOSTS)}) admits hosts beyond this "
        "machine.",
        hint=("Keep the service on localhost, or place it behind an "
              "authenticating reverse proxy or VPN. See SECURITY.md."),
        id="ciis.W002")]


@register()
def check_debug_not_on_in_the_open(app_configs, **kwargs):
    """DEBUG leaks stack traces, settings and SQL to whoever triggers an error."""
    if not settings.DEBUG or not _is_networked():
        return []
    return [Error(
        "DEBUG is on and ALLOWED_HOSTS admits non-local hosts. Django will "
        "serve tracebacks and configuration to anyone who can cause an error.",
        hint="Set CIIS_DEBUG=0 for any deployment reachable from a network.",
        id="ciis.E002")]

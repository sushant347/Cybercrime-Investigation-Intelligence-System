"""Deployment posture checks.

The platform is open access by design. That is defensible on a single-operator
workstation and indefensible on a network, and the difference must not be
silent - so these checks escalate from advisory to blocking as the deployment
becomes reachable.
"""

from __future__ import annotations

import pytest

from api.checks import (
    check_admin_password,
    check_debug_not_on_in_the_open,
    check_open_access_exposure,
)

LOCAL = ["localhost", "127.0.0.1", "testserver"]
NETWORKED = ["ciis.example.gov.np"]


def ids(results):
    return {r.id for r in results}


# ------------------------------------------------------------ admin password

def test_default_password_on_localhost_is_a_warning(settings):
    settings.ALLOWED_HOSTS = LOCAL
    settings.DEBUG = True
    settings.ADMIN_PASSWORD = "hello123"

    results = check_admin_password(None)
    assert ids(results) == {"ciis.W001"}
    assert results[0].level < 40, "localhost default should not block startup"


def test_default_password_on_a_network_is_an_error(settings):
    """Admin can delete cases; on a reachable host this must stop the server."""
    settings.ALLOWED_HOSTS = NETWORKED
    settings.DEBUG = True
    settings.ADMIN_PASSWORD = "hello123"

    results = check_admin_password(None)
    assert ids(results) == {"ciis.E001"}
    assert results[0].level >= 40, "must be an Error so runserver refuses"


def test_default_password_in_production_is_an_error_even_on_localhost(settings):
    settings.ALLOWED_HOSTS = LOCAL
    settings.DEBUG = False
    settings.ADMIN_PASSWORD = "hello123"

    assert ids(check_admin_password(None)) == {"ciis.E001"}


def test_a_chosen_password_raises_nothing(settings):
    settings.ALLOWED_HOSTS = NETWORKED
    settings.ADMIN_PASSWORD = "something-this-deployment-chose"

    assert check_admin_password(None) == []


# ----------------------------------------------------------- open access

def test_open_access_is_silent_on_localhost(settings):
    settings.ALLOWED_HOSTS = LOCAL
    assert check_open_access_exposure(None) == []


def test_open_access_warns_once_reachable(settings):
    settings.ALLOWED_HOSTS = NETWORKED
    results = check_open_access_exposure(None)
    assert ids(results) == {"ciis.W002"}
    assert "no authentication" in results[0].msg


@pytest.mark.parametrize("host", ["*", "0.0.0.0", "10.0.0.5"])
def test_wildcards_and_bind_all_count_as_reachable(settings, host):
    settings.ALLOWED_HOSTS = [host]
    assert ids(check_open_access_exposure(None)) == {"ciis.W002"}


# ----------------------------------------------------------------- DEBUG

def test_debug_on_a_network_is_an_error(settings):
    settings.ALLOWED_HOSTS = NETWORKED
    settings.DEBUG = True
    results = check_debug_not_on_in_the_open(None)
    assert ids(results) == {"ciis.E002"}
    assert results[0].level >= 40


def test_debug_on_localhost_is_fine(settings):
    settings.ALLOWED_HOSTS = LOCAL
    settings.DEBUG = True
    assert check_debug_not_on_in_the_open(None) == []


def test_debug_off_on_a_network_is_fine(settings):
    settings.ALLOWED_HOSTS = NETWORKED
    settings.DEBUG = False
    assert check_debug_not_on_in_the_open(None) == []

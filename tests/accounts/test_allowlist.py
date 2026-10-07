import pytest
from django.core.exceptions import ValidationError

from hrcek.accounts import allowlist
from hrcek.accounts.allowlist import is_signup_allowed
from hrcek.accounts.models import AllowedDomain, AllowedEmail

pytestmark = pytest.mark.django_db


def test_an_empty_allowlist_denies_everyone():
    # A freshly deployed Hrcek must not be an open registration form.
    assert is_signup_allowed("nina@example.com") is False


def test_an_exactly_listed_email_is_allowed():
    AllowedEmail.objects.create(email="nina@example.com")
    assert is_signup_allowed("nina@example.com") is True


def test_a_listed_email_matches_regardless_of_case():
    AllowedEmail.objects.create(email="Nina@Example.com")
    assert is_signup_allowed("NINA@EXAMPLE.COM") is True


def test_an_unlisted_email_is_denied():
    AllowedEmail.objects.create(email="nina@example.com")
    assert is_signup_allowed("marko@example.com") is False


def test_a_listed_domain_admits_any_address_on_it():
    AllowedDomain.objects.create(domain="example.com")
    assert is_signup_allowed("anyone@example.com") is True


def test_domain_matching_is_exact_not_a_suffix():
    AllowedDomain.objects.create(domain="example.com")
    # Suffix matching here would let anyone who owns notexample.com in.
    assert is_signup_allowed("attacker@notexample.com") is False
    assert is_signup_allowed("someone@mail.example.com") is False


def test_a_malformed_address_is_denied():
    AllowedDomain.objects.create(domain="example.com")
    assert is_signup_allowed("not-an-address") is False
    assert is_signup_allowed("") is False


def test_a_domain_may_not_contain_an_at_sign():
    with pytest.raises(ValidationError):
        AllowedDomain(domain="@example.com").full_clean()


def test_a_domain_must_look_like_a_domain():
    with pytest.raises(ValidationError):
        AllowedDomain(domain="localhost").full_clean()


def test_domains_are_stored_normalised():
    domain = AllowedDomain.objects.create(domain="  Example.COM ")
    assert domain.domain == "example.com"


def test_the_allowlist_is_closed_when_both_tables_are_empty():
    assert allowlist.is_open() is False


def test_one_allowed_domain_opens_it():
    AllowedDomain.objects.create(domain="example.com")
    assert allowlist.is_open() is True


def test_one_allowed_address_opens_it():
    AllowedEmail.objects.create(email="ana@example.org")
    assert allowlist.is_open() is True

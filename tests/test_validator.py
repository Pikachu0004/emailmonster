import pytest
from devengers_engine.parsers.validator import (
    is_valid_email,
    sanitize_email,
    format_proper_name,
    extract_first_name,
    validate_and_normalize_contact,
)


def test_is_valid_email():
    assert is_valid_email("event@devengers.org") is True
    assert is_valid_email("kishan.sharma+test@domain.co.in") is True
    assert is_valid_email("plainaddress") is False
    assert is_valid_email("@missingusername.com") is False
    assert is_valid_email("missingdomain@.com") is False
    assert is_valid_email("") is False
    assert is_valid_email(None) is False


def test_sanitize_email():
    assert sanitize_email("  EVENT@DEVENGERS.ORG\n") == "event@devengers.org"
    assert sanitize_email("mailto:support@devengers.org") == "support@devengers.org"
    assert sanitize_email("\r\tuser@domain.com  ") == "user@domain.com"


def test_format_proper_name():
    assert format_proper_name("kishan sharma") == "Kishan Sharma"
    assert format_proper_name("JOHN DOE") == "John Doe"
    assert format_proper_name("mary-jane watson") == "Mary-Jane Watson"
    assert format_proper_name("o'connor") == "O'Connor"
    assert format_proper_name("") == ""


def test_extract_first_name():
    assert extract_first_name("Kishan Sharma") == "Kishan"
    assert extract_first_name("Dr. Bruce Banner") == "Bruce"
    assert extract_first_name("Tony") == "Tony"
    assert extract_first_name("", fallback="Explorer") == "Explorer"


def test_validate_and_normalize_contact():
    raw = {
        "email": "  ALICE@EXAMPLE.COM \n",
        "name": "alice wonderland",
        "extra_data": {"role": "Designer"},
    }
    is_valid, norm, err = validate_and_normalize_contact(raw)
    assert is_valid is True
    assert norm["email"] == "alice@example.com"
    assert norm["name"] == "Alice Wonderland"
    assert norm["first_name"] == "Alice"
    assert norm["extra_data"]["role"] == "Designer"

    # Invalid email test
    bad = {"email": "invalid-email", "name": "Bob"}
    is_valid, norm, err = validate_and_normalize_contact(bad)
    assert is_valid is False
    assert norm is None
    assert "Invalid email" in err

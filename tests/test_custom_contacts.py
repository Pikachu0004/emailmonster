import pytest
from pathlib import Path
from devengers_engine.config import settings
from devengers_engine.database.db import init_db
from devengers_engine.database.repository import ContactRepository
from devengers_engine.parsers.validator import validate_and_normalize_contact

@pytest.fixture(autouse=True)
def setup_isolated_db(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "test_custom_contacts.db"
    monkeypatch.setattr(settings, "database_path", str(test_db))
    monkeypatch.setattr(settings, "dry_run", True)
    init_db()
    yield test_db

def test_manual_contact_normalization():
    item = {"name": "Kishan Sharma", "email": "kishan@devengers.org"}
    ok, norm, err = validate_and_normalize_contact(item)
    assert ok is True
    assert norm["name"] == "Kishan Sharma"
    assert norm["first_name"] == "Kishan"
    assert norm["email"] == "kishan@devengers.org"

def test_manual_contact_bulk_upsert():
    contacts = [
        {"name": "Devenger One", "email": "one@devengers.org", "first_name": "One"},
        {"name": "Devenger Two", "email": "two@devengers.org", "first_name": "Two"},
    ]
    inserted, updated = ContactRepository.bulk_upsert(contacts, source_file="custom_entry")
    assert inserted == 2

    # Duplicate should update, not insert
    inserted2, updated2 = ContactRepository.bulk_upsert([{"name": "Updated One", "email": "one@devengers.org", "first_name": "Updated"}], source_file="custom_entry")
    assert inserted2 == 0
    assert updated2 == 1

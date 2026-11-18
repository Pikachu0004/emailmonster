import pytest
import sqlite3
from pathlib import Path
from devengers_engine.config import settings
from devengers_engine.database.db import init_db, get_db_connection
from devengers_engine.database.repository import (
    ContactRepository,
    SendLogRepository,
    CampaignRepository,
)
from devengers_engine.dispatcher.sender import dispatcher


@pytest.fixture(autouse=True)
def setup_isolated_db(tmp_path: Path, monkeypatch):
    """Sets up a temporary SQLite database for clean test isolation."""
    test_db = tmp_path / "test_email_bot.db"
    monkeypatch.setattr(settings, "database_path", str(test_db))
    monkeypatch.setattr(settings, "dry_run", True)
    monkeypatch.setattr(settings, "daily_send_limit", 300)
    # Faster jitter for tests
    monkeypatch.setattr(settings, "send_delay_seconds_min", 0.0)
    monkeypatch.setattr(settings, "send_delay_seconds_max", 0.0)
    monkeypatch.setattr(settings, "batch_pause_seconds", 0.0)
    init_db()
    yield test_db


def test_fifo_ordering_and_zero_duplicate_continuation():
    """
    Validates:
    1. First batch of contacts is dispatched from first to last (FIFO).
    2. Next day / next run automatically skips the already-sent contacts and begins at contact N+1.
    """
    # 1. Ingest 10 contacts in sequential order
    contacts = [
        {"name": f"User {i}", "email": f"user{i}@devengers.org", "first_name": f"User{i}"}
        for i in range(1, 11)
    ]
    inserted, updated = ContactRepository.bulk_upsert(contacts, source_file="batch1.xlsx")
    assert inserted == 10

    # 2. Verify FIFO order from first to last
    pending = ContactRepository.get_unemailed_contacts()
    assert len(pending) == 10
    assert pending[0]["email"] == "user1@devengers.org"
    assert pending[9]["email"] == "user10@devengers.org"

    # 3. Simulate Day 1: Send batch of 4 emails
    campaign_id = CampaignRepository.create_campaign("Day 1 Batch", "Invite", "event_invite")
    result_day1 = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id,
        template_name="event_invite",
        limit=4,
    )
    assert result_day1["sent_count"] == 4
    assert SendLogRepository.get_daily_sent_count() == 4

    # 4. Verify Day 2: The 4 already emailed contacts MUST NOT be repeated!
    pending_day2 = ContactRepository.get_unemailed_contacts()
    assert len(pending_day2) == 6
    # Day 2 must start from user5@devengers.org (strictly FIFO continuation)!
    assert pending_day2[0]["email"] == "user5@devengers.org"
    assert pending_day2[5]["email"] == "user10@devengers.org"

    # 5. Simulate Day 2 dispatch: Send remaining 6
    campaign_id_2 = CampaignRepository.create_campaign("Day 2 Batch", "Invite", "event_invite")
    result_day2 = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id_2,
        template_name="event_invite",
        limit=6,
    )
    assert result_day2["sent_count"] == 6

    # 6. Verify ledger is now 100% complete
    pending_final = ContactRepository.get_unemailed_contacts()
    assert len(pending_final) == 0


def test_hard_daily_quota_enforcement(monkeypatch):
    """Verifies that dispatch halts when daily quota is exhausted."""
    # Set quota to 3 with 0 buffer for this specific boundary test
    monkeypatch.setattr(settings, "daily_send_limit", 3)
    monkeypatch.setattr(settings, "otp_reserve_buffer", 0)

    contacts = [
        {"name": f"Member {i}", "email": f"member{i}@devengers.org"}
        for i in range(1, 6)
    ]
    ContactRepository.bulk_upsert(contacts)

    campaign_id = CampaignRepository.create_campaign("Quota Test", "Subject", "event_invite")
    result = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id,
        template_name="event_invite",
        limit=10, # Requesting more than daily limit
    )

    # Exactly 3 should be sent today
    assert result["sent_count"] == 3
    assert SendLogRepository.get_daily_sent_count() == 3
    assert SendLogRepository.get_remaining_daily_quota() == 0

    # Attempting to send again on the same day must be rejected by quota limiter
    result_blocked = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id,
        template_name="event_invite",
        limit=5,
    )
    assert result_blocked["success"] is False
    assert result_blocked["reason"] == "DAILY_LIMIT_REACHED"
    assert result_blocked["sent_count"] == 0

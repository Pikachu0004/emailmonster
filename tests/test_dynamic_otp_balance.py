import pytest
from pathlib import Path
from devengers_engine.config import settings
from devengers_engine.database.db import init_db
from devengers_engine.database.repository import ContactRepository, CampaignRepository
from devengers_engine.dispatcher.quota_sync import DynamicQuotaManager
from devengers_engine.dispatcher.sender import dispatcher


@pytest.fixture(autouse=True)
def setup_isolated_test_env(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "test_dynamic_otp.db"
    monkeypatch.setattr(settings, "database_path", str(test_db))
    monkeypatch.setattr(settings, "dry_run", True)
    monkeypatch.setattr(settings, "daily_send_limit", 300)
    monkeypatch.setattr(settings, "otp_reserve_buffer", 10)
    monkeypatch.setattr(settings, "send_delay_seconds_min", 0.0)
    monkeypatch.setattr(settings, "send_delay_seconds_max", 0.0)
    monkeypatch.setattr(settings, "batch_pause_seconds", 0.0)
    init_db()
    yield test_db


def test_dynamic_otp_usage_200_leaves_90(monkeypatch):
    """
    Scenario: Website sends 200 OTP emails from morning until 6 PM.
    Expected:
      Total: 300
      Used by OTP: 200
      OTP Buffer reserved: 10
      Allowed for Bot: 300 - 200 - 10 = 90 emails!
    """
    # Mock Brevo API returning 200 requests
    monkeypatch.setattr(
        DynamicQuotaManager,
        "fetch_today_account_usage_from_brevo",
        classmethod(lambda cls: 200),
    )

    quota = DynamicQuotaManager.calculate_dynamic_quota()
    assert quota["total_account_limit"] == 300
    assert quota["total_used_today"] == 200
    assert quota["used_by_otp_today"] == 200
    assert quota["otp_reserve_buffer"] == 10
    assert quota["safe_to_send_now"] == 90

    # Ingest 150 contacts
    contacts = [{"name": f"User {i}", "email": f"u{i}@test.com"} for i in range(1, 151)]
    ContactRepository.bulk_upsert(contacts)

    # Dispatch should dynamically send exactly 90, protecting the 10 OTP buffer
    campaign_id = CampaignRepository.create_campaign("OTP Auto Adjust", "Invite", "event_invite")
    result = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id,
        template_name="event_invite",
        limit=300, # User asks for 300, but bot must cap at 90
    )

    assert result["sent_count"] == 90


def test_otp_buffer_protects_low_credits(monkeypatch):
    """
    Scenario: Website sends 295 OTPs.
    Only 5 credits left, which is below the 10 OTP safety buffer.
    Bot must halt and NOT send any emails.
    """
    monkeypatch.setattr(
        DynamicQuotaManager,
        "fetch_today_account_usage_from_brevo",
        classmethod(lambda cls: 295),
    )

    quota = DynamicQuotaManager.calculate_dynamic_quota()
    assert quota["safe_to_send_now"] == 0

    contacts = [{"name": "User 1", "email": "u1@test.com"}]
    ContactRepository.bulk_upsert(contacts)

    campaign_id = CampaignRepository.create_campaign("Low Credits Test", "Invite", "event_invite")
    result = dispatcher.run_queue_dispatch(
        campaign_id=campaign_id,
        template_name="event_invite",
        limit=10,
    )
    assert result["success"] is False
    assert result["reason"] == "DAILY_LIMIT_REACHED"
    assert result["sent_count"] == 0

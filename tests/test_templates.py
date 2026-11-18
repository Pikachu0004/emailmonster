import pytest
from devengers_engine.templates.engine import template_engine
from devengers_engine.config import settings


def test_event_invite_rendering():
    context = {
        "name": "Kishan Sharma",
        "first_name": "Kishan",
        "email": "kishan@devengers.org",
        "event_name": "Devengers AI Hackathon 2026",
        "event_date": "Sunday, Nov 30",
        "event_time": "10:00 AM IST",
        "event_location": "Online / Discord",
        "cta_url": "https://devengers.org/hackathon",
        "cta_text": "Confirm Registration",
    }
    subj, html, text = template_engine.render(
        template_name="event_invite",
        context=context,
        custom_subject="Invitation for {{first_name}} to {{event_name}}",
    )

    assert subj == "Invitation for Kishan to Devengers AI Hackathon 2026"
    assert "Kishan" in html
    assert "Devengers AI Hackathon 2026" in html
    assert "support@devengers.org" in html
    assert "event@devengers.org" in html
    assert "Confirm Registration" in html

    # Plain text checks
    assert "DEVENGERS OFFICIAL INVITATION" in text
    assert "support@devengers.org" in text
    assert "https://devengers.org/hackathon" in text


def test_certificate_rendering():
    context = {
        "name": "Sarah Connor",
        "first_name": "Sarah",
        "email": "sarah@resistance.org",
        "event_name": "Cybernetics Workshop",
        "cta_url": "https://devengers.org/certs/123",
    }
    subj, html, text = template_engine.render(
        template_name="certificate",
        context=context,
    )
    assert "Certificate" in html
    assert "Sarah Connor" in html
    assert "https://devengers.org/certs/123" in html

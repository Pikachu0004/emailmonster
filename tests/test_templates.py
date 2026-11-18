import pytest
from devengers_engine.templates.engine import template_engine
from devengers_engine.config import settings


def test_event_invite_rendering():
    context = {
        "name": "Kishan Sharma",
        "first_name": "Kishan",
        "email": "kishan@devengers.org",
        "cta_url": "https://whatsapp.com/channel/0029VbCVGAd8KMql7Ie3ew43",
        "cta_text": "JOIN DEVENGERS NOW",
    }
    subj, html, text = template_engine.render(
        template_name="event_invite",
        context=context,
    )

    assert "Congratulations" in subj
    assert "Kishan" in html
    assert "JOIN DEVENGERS NOW" in html
    assert "https://whatsapp.com/channel/0029VbCVGAd8KMql7Ie3ew43" in html
    assert "support@devengers.org" in html
    assert "event@devengers.org" in html

    # Plain text checks
    assert "Congratulations! You're Invited to Join DEVENGERS!" in text
    assert "support@devengers.org" in text
    assert "https://whatsapp.com/channel/0029VbCVGAd8KMql7Ie3ew43" in text


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

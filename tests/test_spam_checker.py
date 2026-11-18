import pytest
from devengers_engine.deliverability.spam_checker import SpamChecker


def test_clean_email_high_score():
    subject = "Your Invitation to Devengers Tech Summit 2026"
    html = "<p>Hi Kishan, join us for our collaborative engineering summit. Reply to support@devengers.org for help. Unsubscribe anytime.</p>"
    text = "Hi Kishan, join us for our collaborative engineering summit. Reply to support@devengers.org for help. Unsubscribe anytime."

    result = SpamChecker.evaluate(subject, html, text)
    assert result["score"] >= 90
    assert result["rating"] == "Excellent"
    assert len(result["issues"]) == 0


def test_spammy_email_low_score():
    subject = "WIN FREE CASH NOW!!! LIMITED TIME DEAL $$$"
    html = "<p>CONGRATULATIONS WINNER MAKE MONEY ACT NOW NO RISK</p>"
    text = ""  # Missing plain text

    result = SpamChecker.evaluate(subject, html, text)
    assert result["score"] < 60
    assert result["rating"] == "High Spam Risk"
    assert len(result["issues"]) >= 3

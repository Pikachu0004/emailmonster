import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from devengers_engine.config import settings
from devengers_engine.database.repository import SendLogRepository


class DynamicQuotaManager:
    """
    Dynamically balances shared 300 daily email credits between website OTPs and the Email Bot.
    Queries Brevo live API to detect credits used by the website from morning till 6 PM,
    reserves an OTP safety buffer (default: 10 emails), and adjusts bot batch size automatically.
    """

    BREVO_API_URL = "https://api.brevo.com/v3"

    @classmethod
    def get_brevo_api_key(cls) -> Optional[str]:
        """Resolves Brevo API Key from settings or SMTP password if xkeysib format."""
        if settings.brevo_api_key:
            return settings.brevo_api_key.strip()
        # Brevo API keys typically start with 'xkeysib-'
        if settings.smtp_password and settings.smtp_password.startswith("xkeysib-"):
            return settings.smtp_password.strip()
        return None

    @classmethod
    def fetch_today_account_usage_from_brevo(cls) -> Optional[int]:
        """
        Queries Brevo Transactional Statistics API for today's total sends (including website OTPs).
        Returns total requests sent today across the Brevo account, or None if API key not available.
        """
        api_key = cls.get_brevo_api_key()
        if not api_key:
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = f"{cls.BREVO_API_URL}/smtp/statistics/aggregatedReport?startDate={today_str}&endDate={today_str}"

        req = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "User-Agent": "DevengersMailEngine/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=8.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    # 'requests' is total transactional emails requested today across account
                    return int(data.get("requests", 0))
        except (urllib.error.URLError, Exception) as e:
            # Fall back gracefully to local ledger if network/API fails
            return None

        return None

    @classmethod
    def calculate_dynamic_quota(cls) -> Dict[str, Any]:
        """
        Calculates exact number of emails the bot can safely send right now.
        Formula:
          Total Account Limit (300)
          - Credits Used by OTP/Website so far today
          - Bot Sends already executed today
          - Reserved Safety Buffer for OTPs (default 10)
          = Safe Dispatch Allowance
        """
        today_bot_sent = SendLogRepository.get_daily_sent_count()
        total_account_limit = settings.daily_send_limit # 300
        otp_buffer = settings.otp_reserve_buffer # 10

        # Attempt live Brevo account check
        live_account_sent = cls.fetch_today_account_usage_from_brevo()

        if live_account_sent is not None:
            # Live API succeeded: account_sent includes both website OTPs and any bot sends
            # Used by OTP = live_account_sent - today_bot_sent
            otp_used_today = max(0, live_account_sent - today_bot_sent)
            total_used_today = live_account_sent
            source = "brevo_live_api"
        else:
            # API key not set or Brevo offline: rely on local bot ledger + default buffer
            otp_used_today = 0
            total_used_today = today_bot_sent
            source = "local_ledger"

        # Calculate remaining credits safe for bot
        remaining_total_credits = max(0, total_account_limit - total_used_today)
        # Protect the OTP buffer
        safe_to_send_now = max(0, remaining_total_credits - otp_buffer)

        return {
            "total_account_limit": total_account_limit,
            "total_used_today": total_used_today,
            "used_by_otp_today": otp_used_today,
            "used_by_bot_today": today_bot_sent,
            "otp_reserve_buffer": otp_buffer,
            "remaining_total_credits": remaining_total_credits,
            "safe_to_send_now": safe_to_send_now,
            "source": source,
        }

import time
import random
from typing import Tuple
from devengers_engine.config import settings
from devengers_engine.database.repository import SendLogRepository
from devengers_engine.dispatcher.quota_sync import DynamicQuotaManager


class DailyQuotaLimiter:
    """Manages dynamic credit balancing between website OTPs and Email Bot (reserving 10 for OTP)."""

    def __init__(self):
        self.sent_in_current_batch = 0

    def can_send_today(self) -> Tuple[bool, int, int]:
        """
        Checks if we have quota remaining today after accounting for website OTP usage
        and preserving the OTP buffer (default 10 credits reserved).
        Returns: (can_send, total_account_used_today, safe_to_send_now)
        """
        quota_info = DynamicQuotaManager.calculate_dynamic_quota()
        safe_to_send = quota_info["safe_to_send_now"]
        return (safe_to_send > 0), quota_info["total_used_today"], safe_to_send

    def wait_pace(self) -> float:
        """
        Applies a random jitter delay between individual sends to prevent triggering Zoho rate tripwires.
        Also pauses for a longer batch pause every `settings.batch_size` emails.
        Returns the duration slept in seconds.
        """
        self.sent_in_current_batch += 1

        # Check if we reached batch threshold
        if self.sent_in_current_batch >= settings.batch_size:
            self.sent_in_current_batch = 0
            pause = settings.batch_pause_seconds
            time.sleep(pause)
            return pause

        # Jitter delay
        jitter = random.uniform(settings.send_delay_seconds_min, settings.send_delay_seconds_max)
        time.sleep(jitter)
        return jitter

    def reset_batch_counter(self):
        self.sent_in_current_batch = 0

import time
import random
from typing import Tuple
from devengers_engine.config import settings
from devengers_engine.database.repository import SendLogRepository


class DailyQuotaLimiter:
    """Manages the strict 300 daily limit for Zoho Mail free tier and human-like send pacing."""

    def __init__(self):
        self.sent_in_current_batch = 0

    def can_send_today(self) -> Tuple[bool, int, int]:
        """
        Checks if we have quota remaining today.
        Returns: (can_send, sent_today, remaining_quota)
        """
        sent_today = SendLogRepository.get_daily_sent_count()
        remaining = max(0, settings.daily_send_limit - sent_today)
        return (remaining > 0), sent_today, remaining

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

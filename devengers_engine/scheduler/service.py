import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from devengers_engine.config import settings
from devengers_engine.database.repository import ContactRepository, CampaignRepository
from devengers_engine.dispatcher.quota_sync import DynamicQuotaManager
from devengers_engine.dispatcher.sender import dispatcher

logger = logging.getLogger("devengers.scheduler")


class AutomatedScheduler:
    """
    Background scheduler running inside the Web Service.
    Automatically executes the 300/day batch every day at 18:00 IST (Asia/Kolkata).
    Calculates website OTP credit usage and preserves the 10-email OTP reserve buffer.
    """

    def __init__(self):
        self.is_running = False
        self.last_run_date: Optional[str] = None
        self.task: Optional[asyncio.Task] = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._scheduler_loop())
            logger.info("Automated daily 18:00 IST scheduler loop started.")

    def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()

    async def _scheduler_loop(self):
        ist_tz = ZoneInfo("Asia/Kolkata")
        target_hour = 18
        target_minute = 0

        while self.is_running:
            try:
                now_ist = datetime.now(ist_tz)
                today_str = now_ist.strftime("%Y-%m-%d")

                # Check if current time in IST is 18:00 and hasn't run yet today
                if now_ist.hour == target_hour and now_ist.minute == target_minute and self.last_run_date != today_str:
                    logger.info(f"⏰ [18:00 IST Trigger] Initiating automated daily dispatch for {today_str}...")
                    self.last_run_date = today_str
                    
                    # Run in background executor so it doesn't block FastAPI event loop
                    await asyncio.to_thread(self._execute_daily_dispatch)

                # Sleep 30 seconds before checking time again
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {str(e)}")
                await asyncio.sleep(30)

    def _execute_daily_dispatch(self):
        try:
            quota = DynamicQuotaManager.calculate_dynamic_quota()
            safe_to_send = quota["safe_to_send_now"]
            total_used = quota["total_used_today"]
            otp_used = quota["used_by_otp_today"]
            buffer = quota["otp_reserve_buffer"]

            if safe_to_send <= 0:
                logger.warning(
                    f"⚠️ [Scheduler] Halt: Account used {total_used} emails today ({otp_used} OTPs). "
                    f"Remaining {buffer} strictly reserved for website OTPs. Skipping today's run."
                )
                return

            candidates = ContactRepository.get_unemailed_contacts(limit=safe_to_send)
            if not candidates:
                logger.info("✓ [Scheduler] All contacts have already been emailed. No pending members.")
                return

            logger.info(
                f"⚡ [Scheduler] Dispatching {len(candidates)} emails in FIFO order. "
                f"(Account used {total_used} today, leaving {buffer} for website OTPs)."
            )

            campaign_id = CampaignRepository.create_campaign(
                name=f"Autopilot {datetime.now().strftime('%Y-%m-%d')} Batch",
                subject="Congratulations! You're Invited to Join DEVENGERS",
                template_name="event_invite",
                total_queued=len(candidates),
            )

            result = dispatcher.run_queue_dispatch(
                campaign_id=campaign_id,
                template_name="event_invite",
                custom_subject="Congratulations {{first_name}}! You're Invited to Join DEVENGERS",
                template_vars={
                    "cta_url": "https://whatsapp.com/channel/0029VbCVGAd8KMql7Ie3ew43",
                    "cta_text": "JOIN DEVENGERS NOW",
                },
                limit=safe_to_send,
            )
            logger.info(f"✓ [Scheduler] Finished: {result['message']}")

        except Exception as e:
            logger.error(f"Failed to execute daily dispatch: {str(e)}")


scheduler_service = AutomatedScheduler()

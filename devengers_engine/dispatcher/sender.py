import smtplib
import socket
from typing import Dict, Any, Optional, Callable, List, Tuple

from devengers_engine.config import settings
from devengers_engine.database.repository import (
    ContactRepository,
    SendLogRepository,
    CampaignRepository,
)
from devengers_engine.deliverability.headers import build_mime_message
from devengers_engine.dispatcher.rate_limiter import DailyQuotaLimiter
from devengers_engine.templates.engine import template_engine


class MailDispatcher:
    """Core email dispatch engine connected to Zoho SMTP with deduplication and 300/day quota control."""

    def __init__(self):
        self.quota_limiter = DailyQuotaLimiter()

    def create_smtp_connection(self) -> smtplib.SMTP:
        """Establishes an authenticated connection to Zoho SMTP."""
        if settings.smtp_use_ssl:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=25.0)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25.0)
            if settings.smtp_use_tls:
                server.starttls()

        server.ehlo()
        if settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        return server

    def verify_smtp_connection(self) -> Tuple[bool, str]:
        """Tests SMTP credentials and network connectivity."""
        if settings.dry_run:
            return True, "Dry-run mode is active (credentials verification simulated successfully)."

        if not settings.smtp_password or settings.smtp_password in ("your_zoho_app_password_here", "your_brevo_smtp_master_key"):
            return False, "SMTP credentials are not configured in .env. Please set your SMTP username and password/key."

        try:
            server = self.create_smtp_connection()
            server.quit()
            return True, f"Successfully authenticated with {settings.provider_name} ({settings.smtp_host}:{settings.smtp_port})."
        except smtplib.SMTPAuthenticationError as e:
            return False, f"SMTP Authentication Failed (Code {e.smtp_code}): Please verify your SMTP credentials in .env."
        except (socket.timeout, socket.gaierror) as e:
            return False, f"Network/DNS error connecting to {settings.smtp_host}: {str(e)}"
        except Exception as e:
            return False, f"SMTP Connection error: {str(e)}"

    def send_single_message(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        html_content: str,
        text_content: str,
        campaign_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        smtp_server: Optional[smtplib.SMTP] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches a single message and records the outcome in send_logs.
        Returns: (success, message_id, error_message)
        """
        clean_email = recipient_email.strip().lower()

        # Build MIME message with deliverability headers
        mime_msg, message_id = build_mime_message(
            recipient_email=clean_email,
            recipient_name=recipient_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            campaign_id=campaign_id,
        )

        # Handle Dry-Run simulation
        if settings.dry_run:
            SendLogRepository.record_send_attempt(
                campaign_id=campaign_id,
                contact_id=contact_id,
                recipient_email=clean_email,
                status="SUCCESS",
                message_id=f"[DRY_RUN]{message_id}",
                error_message=None,
            )
            return True, f"[DRY_RUN]{message_id}", None

        # Live SMTP delivery
        server_to_close = None
        try:
            server = smtp_server
            if server is None:
                server = self.create_smtp_connection()
                server_to_close = server

            server.send_message(
                msg=mime_msg,
                from_addr=settings.sender_email,
                to_addrs=[clean_email],
            )

            SendLogRepository.record_send_attempt(
                campaign_id=campaign_id,
                contact_id=contact_id,
                recipient_email=clean_email,
                status="SUCCESS",
                message_id=message_id,
                error_message=None,
            )
            return True, message_id, None

        except Exception as e:
            err_msg = str(e)
            SendLogRepository.record_send_attempt(
                campaign_id=campaign_id,
                contact_id=contact_id,
                recipient_email=clean_email,
                status="FAILED",
                message_id=message_id,
                error_message=err_msg,
            )
            return False, message_id, err_msg

        finally:
            if server_to_close:
                try:
                    server_to_close.quit()
                except Exception:
                    pass

    def run_queue_dispatch(
        self,
        campaign_id: int,
        template_name: str,
        custom_subject: Optional[str] = None,
        custom_message: Optional[str] = None,
        template_vars: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes sequential queue dispatch from first to last (FIFO).
        - Skips already-emailed contacts automatically.
        - Enforces daily 300 send cap.
        - Paces with jitter and pauses.
        """
        self.quota_limiter.reset_batch_counter()

        # Check today's dynamic quota (accounting for website OTPs & 10 buffer)
        can_send, sent_today, remaining_quota = self.quota_limiter.can_send_today()
        if not can_send:
            msg = f"Account daily quota of {settings.daily_send_limit} reached or reserved for website OTPs ({sent_today} used today, {settings.otp_reserve_buffer} strictly reserved for OTP). Halting bot dispatch."
            CampaignRepository.finish_campaign(campaign_id, status="PAUSED_DAILY_LIMIT")
            return {
                "success": False,
                "reason": "DAILY_LIMIT_REACHED",
                "message": msg,
                "sent_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }

        effective_limit = remaining_quota
        if limit and limit > 0:
            effective_limit = min(effective_limit, limit)

        # Retrieve unemailed contacts in strict FIFO order (contacts.id ASC)
        candidates = ContactRepository.get_unemailed_contacts(limit=effective_limit)

        if not candidates:
            CampaignRepository.finish_campaign(campaign_id, status="COMPLETED")
            return {
                "success": True,
                "reason": "NO_PENDING_CONTACTS",
                "message": "All uploaded contacts have already been emailed! No new recipients to dispatch.",
                "sent_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        # Reuse SMTP connection when not in dry-run
        smtp_session: Optional[smtplib.SMTP] = None
        if not settings.dry_run:
            try:
                smtp_session = self.create_smtp_connection()
            except Exception as e:
                return {
                    "success": False,
                    "reason": "SMTP_CONNECTION_ERROR",
                    "message": f"Failed to connect to Zoho SMTP: {str(e)}",
                    "sent_count": 0,
                    "failed_count": 0,
                    "skipped_count": 0,
                }

        try:
            for idx, contact in enumerate(candidates):
                # Double-check daily quota before each email
                can_send, current_sent, remaining = self.quota_limiter.can_send_today()
                if not can_send:
                    skipped_count += (len(candidates) - idx)
                    if progress_callback:
                        progress_callback({
                            "type": "QUOTA_REACHED",
                            "message": f"Daily limit of {settings.daily_send_limit} reached. Paused until tomorrow.",
                        })
                    break

                email = contact["email"]

                # Double check deduplication
                if ContactRepository.is_already_emailed(email):
                    skipped_count += 1
                    CampaignRepository.update_campaign_stats(campaign_id, skipped_inc=1)
                    continue

                # Prepare render context
                ctx = {
                    "name": contact["name"],
                    "first_name": contact["first_name"],
                    "email": email,
                    "custom_message": custom_message or "",
                    "extra_data": contact.get("extra_data") or {},
                }
                if template_vars:
                    ctx.update(template_vars)

                subj, html_body, text_body = template_engine.render(
                    template_name=template_name,
                    context=ctx,
                    custom_subject=custom_subject,
                )

                # Send
                success, msg_id, err = self.send_single_message(
                    recipient_email=email,
                    recipient_name=contact["name"],
                    subject=subj,
                    html_content=html_body,
                    text_content=text_body,
                    campaign_id=campaign_id,
                    contact_id=contact["id"],
                    smtp_server=smtp_session,
                )

                if success:
                    sent_count += 1
                    CampaignRepository.update_campaign_stats(campaign_id, sent_inc=1)
                else:
                    failed_count += 1
                    CampaignRepository.update_campaign_stats(campaign_id, failed_inc=1)

                if progress_callback:
                    progress_callback({
                        "type": "ITEM_PROCESSED",
                        "index": idx + 1,
                        "total": len(candidates),
                        "recipient": email,
                        "name": contact["name"],
                        "success": success,
                        "error": err,
                        "sent_count": sent_count,
                        "failed_count": failed_count,
                    })

                # Apply anti-burst jitter pacing
                if idx < len(candidates) - 1:
                    self.quota_limiter.wait_pace()

        finally:
            if smtp_session:
                try:
                    smtp_session.quit()
                except Exception:
                    pass

        status = "COMPLETED" if (sent_count + skipped_count + failed_count) >= len(candidates) else "PAUSED"
        CampaignRepository.finish_campaign(campaign_id, status=status)

        return {
            "success": True,
            "message": f"Dispatch finished. Successfully sent: {sent_count}, Failed: {failed_count}, Skipped: {skipped_count}",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "campaign_id": campaign_id,
        }


# Singleton dispatcher
dispatcher = MailDispatcher()

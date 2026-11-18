import uuid
from datetime import datetime, timezone
from email.utils import formatdate, make_msgid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, Tuple
from devengers_engine.config import settings


def build_mime_message(
    recipient_email: str,
    recipient_name: str,
    subject: str,
    html_content: str,
    text_content: str,
    campaign_id: Optional[int] = None,
) -> Tuple[MIMEMultipart, str]:
    """
    Builds a Gmail-friendly, high-deliverability MIME multipart/alternative message.
    Includes List-Unsubscribe, Reply-To, custom RFC Message-ID, and clean headers.
    Returns: (MIMEMultipart, generated_message_id)
    """
    msg = MIMEMultipart("alternative")

    # Domain-specific Message-ID (RFC 5322)
    # Using devengers.org as the domain for highest reputation
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    custom_msg_id = f"<{timestamp}.{unique_id}@devengers.org>"

    # RFC Required & Best Practice Deliverability Headers
    msg["Message-ID"] = custom_msg_id
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["From"] = f'"{settings.sender_name}" <{settings.sender_email}>'
    msg["To"] = f'"{recipient_name}" <{recipient_email}>' if recipient_name else recipient_email
    msg["Reply-To"] = settings.reply_to_email
    msg["Return-Path"] = settings.sender_email
    msg["Subject"] = subject

    if not settings.primary_inbox_mode:
        # Standard bulk marketing headers (Causes Gmail to categorize into Promotions tab)
        unsub_mail = f"mailto:{settings.reply_to_email}?subject=Unsubscribe%20{recipient_email}"
        msg["List-Unsubscribe"] = f"<{unsub_mail}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["Precedence"] = "bulk"
        msg["X-Mailer"] = "Devengers Engine 1.0"
        if campaign_id:
            msg["X-Campaign-ID"] = str(campaign_id)
    else:
        # Primary Inbox Mode: Send as direct 1-to-1 personal/community message
        msg["X-Priority"] = "3"
        msg["Importance"] = "normal"

    # Attach Plain-Text Part First (Required for RFC alternative hierarchy)
    part_text = MIMEText(text_content, "plain", "utf-8")
    msg.attach(part_text)

    # Attach HTML Part Second (Mail clients prefer the last attached alternative part)
    part_html = MIMEText(html_content, "html", "utf-8")
    msg.attach(part_html)

    return msg, custom_msg_id

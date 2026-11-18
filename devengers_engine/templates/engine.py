import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from devengers_engine.config import settings

TEMPLATES_DIR = Path(__file__).parent


class TemplateEngine:
    """Renders Gmail-optimized responsive HTML and plain-text email templates."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        custom_subject: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Renders template into (subject, html_body, text_body).
        Injects global defaults (sender, reply_to, current_year).
        """
        # Ensure standard variables are populated
        ctx = {
            "name": context.get("name", "Member"),
            "first_name": context.get("first_name") or context.get("name", "Member").split()[0],
            "email": context.get("email", ""),
            "event_name": context.get("event_name", "Devengers Community Event"),
            "event_date": context.get("event_date", "Upcoming"),
            "event_time": context.get("event_time", "6:00 PM IST"),
            "event_location": context.get("event_location", "Online / Discord & Google Meet"),
            "cta_url": context.get("cta_url") or "https://whatsapp.com/channel/0029VbCVGAd8KMql7Ie3ew43",
            "cta_text": context.get("cta_text") or "JOIN DEVENGERS NOW",
            "custom_message": context.get("custom_message", ""),
            "extra_data": context.get("extra_data", {}),
            "sender_email": settings.sender_email,
            "reply_to_email": settings.reply_to_email,
            "sender_name": settings.sender_name,
            "current_year": datetime.now(timezone.utc).year,
        }
        # Merge extra_data directly into top-level for convenience (e.g. {{college}} or {{role}})
        for k, v in ctx["extra_data"].items():
            if k not in ctx:
                ctx[k] = v

        # Resolve template files
        html_file = f"{template_name}.html"
        txt_file = f"{template_name}.txt"

        if not (TEMPLATES_DIR / html_file).exists():
            html_file = "event_invite.html"
        if not (TEMPLATES_DIR / txt_file).exists():
            txt_file = "event_invite.txt"

        html_template = self.env.get_template(html_file)
        html_rendered = html_template.render(ctx)

        txt_template = self.env.get_template(txt_file)
        text_rendered = txt_template.render(ctx)

        # Subject interpolation
        raw_subject = custom_subject or context.get("subject") or f"Congratulations {ctx['first_name']}! You're Invited to Join DEVENGERS"
        subject_template = self.env.from_string(raw_subject)
        subject_rendered = subject_template.render(ctx)

        return subject_rendered, html_rendered, text_rendered


# Global singleton engine
template_engine = TemplateEngine()

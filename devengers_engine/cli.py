import argparse
import sys
from pathlib import Path

from devengers_engine.config import settings
from devengers_engine.database.db import init_db
from devengers_engine.database.repository import (
    ContactRepository,
    SendLogRepository,
    CampaignRepository,
)
from devengers_engine.parsers.extractor import FileExtractor
from devengers_engine.templates.engine import template_engine
from devengers_engine.deliverability.dns_advisor import DNSAdvisor
from devengers_engine.deliverability.spam_checker import SpamChecker
from devengers_engine.dispatcher.sender import dispatcher


def main():
    parser = argparse.ArgumentParser(
        description="Devengers Mail Engine CLI - Quota-aware deduplicating email dispatcher for devengers.org"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: web
    web_parser = subparsers.add_parser("web", help="Launch the interactive web dashboard")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    web_parser.add_argument("--reload", action="store_true", help="Enable hot reload")

    # Command: import
    import_parser = subparsers.add_parser("import", help="Import contacts from Excel (.xlsx), CSV, or PDF")
    import_parser.add_argument("file", help="Path to Excel, CSV, or PDF file")

    # Command: status
    subparsers.add_parser("status", help="Display contacts ledger and today's Zoho 300 quota status")

    # Command: send
    send_parser = subparsers.add_parser("send", help="Dispatch emails to pending unemailed contacts in FIFO order")
    send_parser.add_argument("--template", default="event_invite", help="Template name (event_invite, community_update, certificate, custom_wrapper)")
    send_parser.add_argument("--subject", default=None, help="Custom subject line (supports {{first_name}}, {{event_name}})")
    send_parser.add_argument("--limit", type=int, default=300, help="Max emails to send (auto-capped at daily quota)")
    send_parser.add_argument("--event-name", default="Devengers Tech Event", help="Event Name")
    send_parser.add_argument("--event-date", default="Upcoming", help="Event Date")
    send_parser.add_argument("--event-time", default="6:00 PM IST", help="Event Time")
    send_parser.add_argument("--event-location", default="Online via Discord / Meet", help="Event Location")
    send_parser.add_argument("--cta-url", default="https://devengers.org", help="CTA Button URL")
    send_parser.add_argument("--cta-text", default="Confirm Attendance", help="CTA Button Text")
    send_parser.add_argument("--message", default="", help="Custom message body")

    # Command: test
    test_parser = subparsers.add_parser("test", help="Send single test email to verify inbox deliverability")
    test_parser.add_argument("--to", required=True, help="Recipient email address")
    test_parser.add_argument("--name", default="Test Member", help="Recipient Name")

    # Command: dns
    subparsers.add_parser("dns", help="Display Spaceship DNS records required for Zoho Mail deliverability")

    args = parser.parse_args()

    # Always ensure database exists
    init_db()

    if args.command == "web":
        import uvicorn
        print(f"\n🚀 Starting Devengers Mail Engine Dashboard at http://{args.host}:{args.port}")
        print(f"📧 Sender: {settings.sender_email} | Replies: {settings.reply_to_email}")
        print(f"🛡️ Mode: {'DRY RUN' if settings.dry_run else 'LIVE ZOHO SMTP'}\n")
        uvicorn.run("devengers_engine.web.app:app", host=args.host, port=args.port, reload=args.reload)

    elif args.command == "import":
        path = Path(args.file)
        if not path.exists():
            print(f"❌ Error: File not found: {path}")
            sys.exit(1)

        print(f"📥 Extracting contacts from {path.name}...")
        contacts, warnings = FileExtractor.extract_from_file(path)
        print(f"✓ Found {len(contacts)} valid contacts.")

        inserted, updated = ContactRepository.bulk_upsert(contacts, source_file=path.name)
        print(f"✓ Database updated: {inserted} newly inserted, {updated} updated with existing records.")
        if warnings:
            print(f"⚠️ Warnings ({len(warnings)}):")
            for w in warnings[:5]:
                print(f"  - {w}")

    elif args.command == "status":
        summary = ContactRepository.get_contacts_summary()
        sent_today = SendLogRepository.get_daily_sent_count()
        remaining = SendLogRepository.get_remaining_daily_quota()

        print("\n========================================================")
        print("          DEVENGERS MAIL ENGINE - STATUS REPORT         ")
        print("========================================================")
        print(f"Domain & From:        {settings.formatted_from}")
        print(f"Replies Routed To:    {settings.reply_to_email}")
        print(f"Operational Mode:     {'DRY RUN (Simulated)' if settings.dry_run else 'LIVE ZOHO SMTP'}")
        print("--------------------------------------------------------")
        print(f"Total Unique Contacts:   {summary['total_contacts']}")
        print(f"Already Emailed (Sent): {summary['already_emailed']}")
        print(f"Unsubscribed:           {summary['unsubscribed']}")
        print(f"Pending Unemailed:      {summary['pending_unemailed']}")
        print("--------------------------------------------------------")
        print(f"Today's Sent Count:     {sent_today} / {settings.daily_send_limit}")
        print(f"Today's Quota Left:     {remaining} emails")
        print("========================================================\n")

    elif args.command == "send":
        remaining = SendLogRepository.get_remaining_daily_quota()
        if remaining <= 0:
            print(f"❌ Daily limit of {settings.daily_send_limit} emails reached today. Aborting.")
            sys.exit(1)

        effective_limit = min(args.limit, remaining)
        candidates = ContactRepository.get_unemailed_contacts(limit=effective_limit)

        if not candidates:
            print("✓ All contacts in the ledger have already received an email! Nothing to send.")
            sys.exit(0)

        print(f"⚡ Starting dispatch for {len(candidates)} unemailed contacts (FIFO order)...")

        campaign_id = CampaignRepository.create_campaign(
            name=f"CLI {args.event_name}",
            subject=args.subject or f"Invitation | Devengers",
            template_name=args.template,
            custom_body=args.message,
            total_queued=len(candidates),
        )

        def progress_cb(evt):
            if evt.get("type") == "ITEM_PROCESSED":
                status = "✓" if evt["success"] else "✗"
                print(f"[{evt['index']}/{evt['total']}] {status} {evt['recipient']} ({evt['name']})")
            elif evt.get("type") == "QUOTA_REACHED":
                print(f"⚠️ {evt['message']}")

        result = dispatcher.run_queue_dispatch(
            campaign_id=campaign_id,
            template_name=args.template,
            custom_subject=args.subject,
            custom_message=args.message,
            template_vars={
                "event_name": args.event_name,
                "event_date": args.event_date,
                "event_time": args.event_time,
                "event_location": args.event_location,
                "cta_url": args.cta_url,
                "cta_text": args.cta_text,
            },
            limit=effective_limit,
            progress_callback=progress_cb,
        )
        print(f"\n{result['message']}\n")

    elif args.command == "test":
        print(f"🧪 Dispatching single test email to {args.to}...")
        subj, html, text = template_engine.render(
            template_name="event_invite",
            context={
                "name": args.name,
                "first_name": args.name.split()[0],
                "email": args.to,
            },
            custom_subject="[TEST] Devengers Delivery Verification",
        )
        success, msg_id, err = dispatcher.send_single_message(
            recipient_email=args.to,
            recipient_name=args.name,
            subject=subj,
            html_content=html,
            text_content=text,
        )
        if success:
            print(f"✓ Test email sent successfully! Message-ID: {msg_id}")
        else:
            print(f"❌ Test email failed: {err}")

    elif args.command == "dns":
        guide = DNSAdvisor.get_spaceship_records_guide()
        print("\n========================================================")
        print(f"  SPACESHIP & ZOHO DNS RECORDS FOR {guide['domain']}  ")
        print("========================================================")
        for r in guide["records"]:
            prio = f" (Priority: {r['priority']})" if "priority" in r else ""
            print(f"\nType:     {r['type']}{prio}")
            print(f"Host:     {r['host']}")
            print(f"Value:    {r['value']}")
            print(f"Purpose:  {r['purpose']}")
        print("\n========================================================\n")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

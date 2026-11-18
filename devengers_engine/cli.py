import argparse
import os
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
from devengers_engine.dispatcher.quota_sync import DynamicQuotaManager


def main():
    parser = argparse.ArgumentParser(
        description="Devengers Mail Engine CLI - Quota-aware deduplicating email dispatcher for devengers.org"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: web
    web_parser = subparsers.add_parser("web", help="Launch the interactive web dashboard")
    web_parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host interface (default: 0.0.0.0)")
    web_parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="Port to listen on (default: 8000 or $PORT)")
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

    # Command: daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run in continuous background daemon mode, firing daily at specified time (default 18:00 IST)")
    daemon_parser.add_argument("--time", default="18:00", help="Daily trigger time in HH:MM (default: 18:00)")
    daemon_parser.add_argument("--template", default="event_invite", help="Template name")
    daemon_parser.add_argument("--limit", type=int, default=300, help="Max emails per day (auto-capped at daily quota)")

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
        quota = DynamicQuotaManager.calculate_dynamic_quota()

        print("\n========================================================")
        print("          DEVENGERS MAIL ENGINE - STATUS REPORT         ")
        print("========================================================")
        print(f"Domain & From:        {settings.formatted_from}")
        print(f"Replies Routed To:    {settings.reply_to_email}")
        print(f"Relay Provider:       {settings.provider_name}")
        print(f"SMTP Host:            {settings.smtp_host}:{settings.smtp_port}")
        print(f"Operational Mode:     {'DRY RUN (Simulated)' if settings.dry_run else 'LIVE TRANSMISSION'}")
        print("--------------------------------------------------------")
        print(f"Total Unique Contacts:   {summary['total_contacts']}")
        print(f"Already Emailed (Sent): {summary['already_emailed']}")
        print(f"Unsubscribed:           {summary['unsubscribed']}")
        print(f"Pending Unemailed:      {summary['pending_unemailed']}")
        print("--------------------------------------------------------")
        print(f"Total Account Limit:    {quota['total_account_limit']} emails / day")
        print(f"Credits Used Today:     {quota['total_used_today']} (OTPs: {quota['used_by_otp_today']}, Bot: {quota['used_by_bot_today']})")
        print(f"OTP Safety Buffer:      {quota['otp_reserve_buffer']} strictly reserved for website OTPs")
        print(f"Safe For Bot Today:     {quota['safe_to_send_now']} emails (Auto-adjusted)")
        print(f"Data Source:            {quota['source']}")
        print("========================================================\n")

    elif args.command == "send":
        quota = DynamicQuotaManager.calculate_dynamic_quota()
        remaining = quota["safe_to_send_now"]
        if remaining <= 0:
            print(f"⚠️ No safe quota remaining today ({quota['total_used_today']} used, {quota['otp_reserve_buffer']} strictly reserved for website OTPs). Aborting.")
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

    elif args.command == "daemon":
        import time
        from datetime import datetime, timedelta

        try:
            target_hour, target_min = map(int, args.time.split(":"))
        except ValueError:
            print("❌ Invalid time format. Please use HH:MM (e.g. 18:00)")
            sys.exit(1)

        print(f"\n========================================================")
        print(f"        DEVENGERS MAIL ENGINE - DAILY DAEMON            ")
        print(f"========================================================")
        print(f"Target Schedule:      Every day at {args.time} IST")
        print(f"Batch Limit:          {args.limit} emails / day (Zoho Free Tier)")
        print(f"Sender:               {settings.formatted_from}")
        print(f"Template:             {args.template}")
        print(f"Operational Mode:     {'DRY RUN (Simulated)' if settings.dry_run else 'LIVE ZOHO SMTP'}")
        print(f"Press Ctrl+C to terminate daemon gracefully.")
        print(f"========================================================\n")

        while True:
            now = datetime.now()
            target_today = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if now >= target_today:
                next_run = target_today + timedelta(days=1)
            else:
                next_run = target_today

            wait_seconds = max(0.0, (next_run - now).total_seconds())
            hours_left = int(wait_seconds // 3600)
            mins_left = int((wait_seconds % 3600) // 60)
            secs_left = int(wait_seconds % 60)

            print(f"⏰ Next dispatch scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (in {hours_left}h {mins_left}m {secs_left}s)")
            
            try:
                time.sleep(wait_seconds)
            except KeyboardInterrupt:
                print("\n🛑 Daemon stopped by user.")
                break

            print(f"\n🚀 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Triggering daily batch...")
            quota = DynamicQuotaManager.calculate_dynamic_quota()
            remaining = quota["safe_to_send_now"]
            if remaining <= 0:
                print(f"⚠️ Account used {quota['total_used_today']} emails today ({quota['used_by_otp_today']} OTPs). Only {quota['otp_reserve_buffer']} remain, strictly reserved for OTPs. Sleeping until tomorrow.")
                time.sleep(60)
                continue

            effective_limit = min(args.limit, remaining)
            print(f"⚡ Dynamic Adjustment: Account used {quota['total_used_today']} today ({quota['used_by_otp_today']} OTPs). Dispatching {effective_limit} emails, leaving {quota['otp_reserve_buffer']} for OTPs.")
            candidates = ContactRepository.get_unemailed_contacts(limit=effective_limit)

            if not candidates:
                print("✓ All contacts in database have already been emailed! Sleeping until next schedule.")
                time.sleep(60)
                continue

            print(f"⚡ Dispatching to next {len(candidates)} members in FIFO sequence...")
            campaign_id = CampaignRepository.create_campaign(
                name=f"Daemon {datetime.now().strftime('%Y-%m-%d')} Batch",
                subject=f"Special Invitation | Devengers",
                template_name=args.template,
                total_queued=len(candidates),
            )

            result = dispatcher.run_queue_dispatch(
                campaign_id=campaign_id,
                template_name=args.template,
                limit=effective_limit,
            )
            print(f"✓ Daily run finished: {result['message']}\n")
            # Sleep 60s so it doesn't immediately re-trigger in the same minute
            time.sleep(60)

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

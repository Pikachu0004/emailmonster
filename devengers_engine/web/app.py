import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devengers_engine.config import settings
from devengers_engine.database.db import init_db
from devengers_engine.database.repository import (
    ContactRepository,
    SendLogRepository,
    CampaignRepository,
)
from contextlib import asynccontextmanager
from devengers_engine.parsers.extractor import FileExtractor
from devengers_engine.templates.engine import template_engine
from devengers_engine.deliverability.spam_checker import SpamChecker
from devengers_engine.deliverability.dns_advisor import DNSAdvisor
from devengers_engine.dispatcher.sender import dispatcher
from devengers_engine.dispatcher.quota_sync import DynamicQuotaManager
from devengers_engine.scheduler.service import scheduler_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB & Start 18:00 IST Background Dispatcher
    init_db()
    scheduler_service.start()
    yield
    scheduler_service.stop()


app = FastAPI(
    title="Devengers Mail Engine",
    description="High-deliverability, quota-aware, deduplicating email dispatcher for devengers.org",
    version="1.0.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared state for active dispatch progress
active_dispatch_state: Dict[str, Any] = {
    "is_running": False,
    "current_index": 0,
    "total": 0,
    "sent_count": 0,
    "failed_count": 0,
    "last_recipient": "",
    "status_message": "Idle",
}


class PreviewRequest(BaseModel):
    template_name: str = "event_invite"
    subject: Optional[str] = None
    custom_message: Optional[str] = None
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    event_location: Optional[str] = None
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None
    sample_name: Optional[str] = "Kishan Sharma"
    sample_email: Optional[str] = "kishan@example.com"


class TestSendRequest(BaseModel):
    recipient_email: str
    recipient_name: Optional[str] = "Test Recipient"
    template_name: str = "event_invite"
    subject: Optional[str] = None
    custom_message: Optional[str] = None
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    event_location: Optional[str] = None
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None


class DispatchRequest(BaseModel):
    template_name: str = "event_invite"
    campaign_name: str = "Devengers Dispatch"
    subject: Optional[str] = None
    custom_message: Optional[str] = None
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    event_location: Optional[str] = None
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None
    limit: Optional[int] = 300


@app.get("/health")
async def health_check():
    from zoneinfo import ZoneInfo
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
    return {
        "status": "online",
        "service": "Devengers Mail Engine",
        "time_ist": now_ist,
        "scheduler": "active",
    }


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Devengers Mail Engine</h1><p>Dashboard UI loading...</p>")


@app.get("/api/stats")
async def get_stats():
    summary = ContactRepository.get_contacts_summary()
    dynamic_quota = DynamicQuotaManager.calculate_dynamic_quota()
    smtp_ok, smtp_msg = dispatcher.verify_smtp_connection()

    return {
        "contacts": summary,
        "daily_quota": {
            "limit": dynamic_quota["total_account_limit"],
            "sent_today": dynamic_quota["total_used_today"],
            "used_by_otp": dynamic_quota["used_by_otp_today"],
            "used_by_bot": dynamic_quota["used_by_bot_today"],
            "otp_reserve_buffer": dynamic_quota["otp_reserve_buffer"],
            "remaining_today": dynamic_quota["safe_to_send_now"],
            "percentage_used": round((dynamic_quota["total_used_today"] / dynamic_quota["total_account_limit"]) * 100, 1),
            "source": dynamic_quota["source"],
        },
        "smtp": {
            "status": "connected" if smtp_ok else "warning",
            "message": smtp_msg,
            "provider": "Brevo API (300/day)" if settings.brevo_api_key else settings.provider_name,
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "user": settings.smtp_user,
            "sender": settings.sender_email,
            "reply_to": settings.reply_to_email,
            "dry_run": settings.dry_run,
        },
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Receives Excel, CSV, or PDF, extracts contacts, and automatically returns summary & preview."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv", ".pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported format '{ext}'. Upload .xlsx, .csv, or .pdf")

    # Save to uploads dir
    dest_path = settings.uploads_path / (file.filename or "uploaded_data.xlsx")
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    contacts, warnings = FileExtractor.extract_from_file(dest_path)

    # Ingest into database immediately for deduplication
    inserted, updated = ContactRepository.bulk_upsert(contacts, source_file=file.filename or "")

    return {
        "success": True,
        "filename": file.filename,
        "total_extracted": len(contacts),
        "newly_inserted": inserted,
        "existing_updated": updated,
        "warnings": warnings[:10],
        "preview_sample": contacts[:8],
    }


@app.get("/api/contacts/pending")
async def get_pending_contacts(limit: int = 50):
    candidates = ContactRepository.get_unemailed_contacts(limit=limit)
    return {
        "total_unemailed": len(candidates),
        "sample": candidates,
    }


@app.post("/api/preview")
async def preview_template(req: PreviewRequest):
    ctx = {
        "name": req.sample_name,
        "first_name": req.sample_name.split()[0] if req.sample_name else "Friend",
        "email": req.sample_email,
        "custom_message": req.custom_message or "",
        "event_name": req.event_name or "Devengers Tech Summit",
        "event_date": req.event_date or "Saturday, Dec 6",
        "event_time": req.event_time or "5:00 PM IST",
        "event_location": req.event_location or "Online via Google Meet & Discord",
        "cta_url": req.cta_url or "https://devengers.org",
        "cta_text": req.cta_text or "Confirm Your Seat",
    }
    subj, html_body, text_body = template_engine.render(
        template_name=req.template_name,
        context=ctx,
        custom_subject=req.subject,
    )
    return {
        "subject": subj,
        "html": html_body,
        "text": text_body,
    }


@app.post("/api/spam-check")
async def check_spam(req: PreviewRequest):
    ctx = {
        "name": req.sample_name,
        "first_name": req.sample_name.split()[0] if req.sample_name else "Friend",
        "email": req.sample_email,
        "custom_message": req.custom_message or "",
        "event_name": req.event_name or "Devengers Tech Summit",
        "event_date": req.event_date or "Saturday, Dec 6",
        "event_time": req.event_time or "5:00 PM IST",
        "event_location": req.event_location or "Online via Google Meet & Discord",
        "cta_url": req.cta_url or "https://devengers.org",
        "cta_text": req.cta_text or "Confirm Your Seat",
    }
    subj, html_body, text_body = template_engine.render(
        template_name=req.template_name,
        context=ctx,
        custom_subject=req.subject,
    )
    eval_result = SpamChecker.evaluate(subj, html_body, text_body)
    return eval_result


@app.post("/api/test-send")
async def send_test_email(req: TestSendRequest):
    """Sends a single test email to check live inbox formatting."""
    ctx = {
        "name": req.recipient_name,
        "first_name": req.recipient_name.split()[0] if req.recipient_name else "Friend",
        "email": req.recipient_email,
        "custom_message": req.custom_message or "",
        "event_name": req.event_name or "Devengers Test Dispatch",
        "event_date": req.event_date or "Upcoming",
        "event_time": req.event_time or "6:00 PM IST",
        "event_location": req.event_location or "Online / Discord",
        "cta_url": req.cta_url or "https://devengers.org",
        "cta_text": req.cta_text or "Check Details",
    }
    subj, html_body, text_body = template_engine.render(
        template_name=req.template_name,
        context=ctx,
        custom_subject=req.subject,
    )

    success, msg_id, err = dispatcher.send_single_message(
        recipient_email=req.recipient_email,
        recipient_name=req.recipient_name or "",
        subject=f"[TEST] {subj}",
        html_content=html_body,
        text_content=text_body,
        campaign_id=None,
        contact_id=None,
    )

    return {
        "success": success,
        "message_id": msg_id,
        "error": err,
        "recipient": req.recipient_email,
    }


def _run_background_dispatch(
    campaign_id: int,
    template_name: str,
    subject: Optional[str],
    custom_message: Optional[str],
    template_vars: Dict[str, Any],
    limit: int,
):
    global active_dispatch_state
    active_dispatch_state["is_running"] = True
    active_dispatch_state["status_message"] = "Dispatching queue..."

    def on_progress(event: Dict[str, Any]):
        global active_dispatch_state
        if event.get("type") == "ITEM_PROCESSED":
            active_dispatch_state["current_index"] = event.get("index", 0)
            active_dispatch_state["total"] = event.get("total", 0)
            active_dispatch_state["sent_count"] = event.get("sent_count", 0)
            active_dispatch_state["failed_count"] = event.get("failed_count", 0)
            active_dispatch_state["last_recipient"] = event.get("recipient", "")
        elif event.get("type") == "QUOTA_REACHED":
            active_dispatch_state["status_message"] = event.get("message", "Quota reached.")

    try:
        dispatcher.run_queue_dispatch(
            campaign_id=campaign_id,
            template_name=template_name,
            custom_subject=subject,
            custom_message=custom_message,
            template_vars=template_vars,
            limit=limit,
            progress_callback=on_progress,
        )
    finally:
        active_dispatch_state["is_running"] = False
        active_dispatch_state["status_message"] = "Batch finished."


@app.post("/api/dispatch")
async def start_dispatch(req: DispatchRequest, background_tasks: BackgroundTasks):
    global active_dispatch_state
    if active_dispatch_state["is_running"]:
        raise HTTPException(status_code=409, detail="A dispatch is currently running. Please wait for it to complete.")

    # Calculate remaining quota
    dynamic_quota = DynamicQuotaManager.calculate_dynamic_quota()
    remaining_quota = dynamic_quota["safe_to_send_now"]
    if remaining_quota <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"No safe quota remaining for bot today ({dynamic_quota['total_used_today']} used today, {dynamic_quota['otp_reserve_buffer']} strictly reserved for website OTPs).",
        )

    effective_limit = min(req.limit or 300, remaining_quota)

    # Get queued count
    unemailed = ContactRepository.get_unemailed_contacts(limit=effective_limit)
    if not unemailed:
        return {
            "success": False,
            "message": "All uploaded contacts have already been emailed! Upload a new file or check status.",
        }

    template_vars = {
        "event_name": req.event_name,
        "event_date": req.event_date,
        "event_time": req.event_time,
        "event_location": req.event_location,
        "cta_url": req.cta_url,
        "cta_text": req.cta_text,
    }

    campaign_id = CampaignRepository.create_campaign(
        name=req.campaign_name,
        subject=req.subject or f"Invitation | Devengers",
        template_name=req.template_name,
        custom_body=req.custom_message or "",
        template_vars=template_vars,
        total_queued=len(unemailed),
    )

    active_dispatch_state.update({
        "is_running": True,
        "current_index": 0,
        "total": len(unemailed),
        "sent_count": 0,
        "failed_count": 0,
        "last_recipient": "",
        "status_message": f"Starting batch for {len(unemailed)} recipients...",
    })

    background_tasks.add_task(
        _run_background_dispatch,
        campaign_id=campaign_id,
        template_name=req.template_name,
        subject=req.subject,
        custom_message=req.custom_message,
        template_vars=template_vars,
        limit=effective_limit,
    )

    return {
        "success": True,
        "campaign_id": campaign_id,
        "queued_recipients": len(unemailed),
        "daily_quota_remaining": remaining_quota,
        "message": f"Dispatch started for {len(unemailed)} members (Strict FIFO, zero-duplicate guarantee).",
    }


@app.get("/api/dispatch/status")
async def get_dispatch_status():
    global active_dispatch_state
    return active_dispatch_state


@app.get("/api/logs")
async def get_logs(limit: int = 50):
    logs = SendLogRepository.get_recent_logs(limit=limit)
    return {"logs": logs}


@app.get("/api/dns-guide")
async def get_dns_guide():
    guide = DNSAdvisor.get_spaceship_records_guide()
    connectivity = DNSAdvisor.test_domain_connectivity()
    return {"guide": guide, "connectivity": connectivity}

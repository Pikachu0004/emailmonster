import json
from typing import List, Dict, Any, Optional, Tuple
from devengers_engine.database.db import (
    get_db_connection,
    get_today_iso_date,
    get_current_timestamp,
)
from devengers_engine.config import settings


class ContactRepository:
    """Repository handling contact ingestion, deduplication, and FIFO queueing."""

    @staticmethod
    def upsert_contact(
        email: str,
        name: str,
        first_name: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        source_file: str = "",
    ) -> int:
        """Inserts or updates a contact by unique email. Returns contact ID."""
        clean_email = email.strip().lower()
        clean_name = name.strip()
        if not first_name:
            first_name = clean_name.split()[0] if clean_name else "Friend"

        extra_json = json.dumps(extra_data or {})
        now = get_current_timestamp()

        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO contacts (email, name, first_name, extra_data, source_file, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        name = excluded.name,
                        first_name = excluded.first_name,
                        extra_data = excluded.extra_data,
                        source_file = CASE WHEN excluded.source_file != '' THEN excluded.source_file ELSE contacts.source_file END
                    RETURNING id;
                """, (clean_email, clean_name, first_name, extra_json, source_file, now))
                row = cursor.fetchone()
                return row["id"]
        finally:
            conn.close()

    @staticmethod
    def bulk_upsert(contacts_list: List[Dict[str, Any]], source_file: str = "") -> Tuple[int, int]:
        """
        Bulk upserts contacts. Returns (new_inserted, updated).
        Ensures strict deduplication upon ingestion.
        """
        conn = get_db_connection()
        inserted_count = 0
        updated_count = 0
        now = get_current_timestamp()

        try:
            with conn:
                cursor = conn.cursor()
                for c in contacts_list:
                    clean_email = c["email"].strip().lower()
                    clean_name = c.get("name", "").strip() or clean_email.split("@")[0]
                    first_name = c.get("first_name") or (clean_name.split()[0] if clean_name else "Friend")
                    extra_json = json.dumps(c.get("extra_data") or {})

                    # Check if exists
                    cursor.execute("SELECT id FROM contacts WHERE email = ?", (clean_email,))
                    exists = cursor.fetchone()

                    if exists:
                        cursor.execute("""
                            UPDATE contacts
                            SET name = ?, first_name = ?, extra_data = ?, source_file = ?
                            WHERE email = ?;
                        """, (clean_name, first_name, extra_json, source_file, clean_email))
                        updated_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO contacts (email, name, first_name, extra_data, source_file, created_at)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (clean_email, clean_name, first_name, extra_json, source_file, now))
                        inserted_count += 1
        finally:
            conn.close()

        return inserted_count, updated_count

    @staticmethod
    def get_unemailed_contacts(limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all contacts that have NOT yet received an email successfully.
        Strict FIFO ordering (ordered by contacts.id ASC: from first uploaded to last).
        Filters out any suppressed/unsubscribed addresses.
        """
        conn = get_db_connection()
        try:
            query = """
                SELECT c.id, c.email, c.name, c.first_name, c.extra_data, c.source_file, c.created_at
                FROM contacts c
                WHERE c.status = 'ACTIVE'
                  AND c.email NOT IN (
                      SELECT DISTINCT recipient_email FROM send_logs WHERE status = 'SUCCESS'
                  )
                  AND c.email NOT IN (
                      SELECT DISTINCT email FROM unsubscribes
                  )
                ORDER BY c.id ASC
            """
            if limit and limit > 0:
                query += f" LIMIT {int(limit)}"

            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["extra_data"] = json.loads(item.get("extra_data") or "{}")
                results.append(item)
            return results
        finally:
            conn.close()

    @staticmethod
    def is_already_emailed(email: str) -> bool:
        """Checks if this specific email was ever successfully sent to."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM send_logs 
                WHERE recipient_email = ? AND status = 'SUCCESS' 
                LIMIT 1;
            """, (email.strip().lower(),))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def get_contacts_summary() -> Dict[str, Any]:
        """Returns overview statistics of the contacts ledger."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM contacts;")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(DISTINCT recipient_email) AS sent FROM send_logs WHERE status = 'SUCCESS';")
            sent = cursor.fetchone()["sent"]

            cursor.execute("SELECT COUNT(*) AS unsubscribed FROM unsubscribes;")
            unsub = cursor.fetchone()["unsubscribed"]

            pending = max(0, total - sent - unsub)
            return {
                "total_contacts": total,
                "already_emailed": sent,
                "unsubscribed": unsub,
                "pending_unemailed": pending,
            }
        finally:
            conn.close()


class SendLogRepository:
    """Repository handling send logs, daily quota enforcement, and audit history."""

    @staticmethod
    def record_send_attempt(
        campaign_id: Optional[int],
        contact_id: Optional[int],
        recipient_email: str,
        status: str,
        message_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> int:
        """Records a dispatch attempt (SUCCESS, FAILED, SKIPPED)."""
        clean_email = recipient_email.strip().lower()
        now = get_current_timestamp()
        today = get_today_iso_date()

        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO send_logs (campaign_id, contact_id, recipient_email, status, message_id, error_message, sent_at, date_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id;
                """, (campaign_id, contact_id, clean_email, status, message_id, error_message, now, today))
                row = cursor.fetchone()
                return row["id"]
        finally:
            conn.close()

    @staticmethod
    def get_daily_sent_count(date_str: Optional[str] = None) -> int:
        """Calculates how many successful emails have been dispatched for the given date (UTC)."""
        target_date = date_str or get_today_iso_date()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) AS sent_today
                FROM send_logs
                WHERE date_sent = ? AND status = 'SUCCESS';
            """, (target_date,))
            row = cursor.fetchone()
            return row["sent_today"] if row else 0
        finally:
            conn.close()

    @staticmethod
    def get_remaining_daily_quota(date_str: Optional[str] = None) -> int:
        """Calculates remaining emails allowed today based on the 300 daily limit."""
        sent = SendLogRepository.get_daily_sent_count(date_str)
        return max(0, settings.daily_send_limit - sent)

    @staticmethod
    def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent dispatch records for audit and dashboard inspection."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.id, l.campaign_id, l.recipient_email, l.status, l.message_id, l.error_message, l.sent_at,
                       c.name AS contact_name
                FROM send_logs l
                LEFT JOIN contacts c ON l.contact_id = c.id
                ORDER BY l.id DESC
                LIMIT ?;
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()


class CampaignRepository:
    """Repository handling campaign creation and live progress state."""

    @staticmethod
    def create_campaign(
        name: str,
        subject: str,
        template_name: str,
        custom_body: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
        total_queued: int = 0,
    ) -> int:
        now = get_current_timestamp()
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO campaigns (name, subject, template_name, custom_body, template_vars, status, total_queued, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'IN_PROGRESS', ?, ?, ?)
                    RETURNING id;
                """, (name, subject, template_name, custom_body, json.dumps(template_vars or {}), total_queued, now, now))
                return cursor.fetchone()["id"]
        finally:
            conn.close()

    @staticmethod
    def update_campaign_stats(campaign_id: int, sent_inc: int = 0, failed_inc: int = 0, skipped_inc: int = 0) -> None:
        now = get_current_timestamp()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    UPDATE campaigns
                    SET sent_count = sent_count + ?,
                        failed_count = failed_count + ?,
                        skipped_count = skipped_count + ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (sent_inc, failed_inc, skipped_inc, now, campaign_id))
        finally:
            conn.close()

    @staticmethod
    def finish_campaign(campaign_id: int, status: str = "COMPLETED") -> None:
        now = get_current_timestamp()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    UPDATE campaigns
                    SET status = ?, updated_at = ?
                    WHERE id = ?;
                """, (status, now, campaign_id))
        finally:
            conn.close()

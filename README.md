# ⚡ Devengers Mail Engine

A production-grade, quota-aware, deduplicating email automation engine engineered for **devengers.org**. Built specifically for Zoho Mail's free tier with domain routing configured via Spaceship, strict 300/day sending protection, FIFO contact queueing, and enterprise deliverability standards to guarantee inbox landing in Gmail and Outlook.

---

## 🌟 Key Features

1. **Strict 300/Day Quota Enforcement**:
   - Accurately tracks daily email volume against Zoho Mail's free tier limit (300/day).
   - Automatically pauses when the daily threshold is met and seamlessly resumes the following day.
2. **Zero-Duplicate Guarantee & Strict FIFO Ordering**:
   - Ingests contacts from Excel (`.xlsx`, `.xls`), CSV, and PDF documents.
   - Enforces persistent database deduplication.
   - Dispatches in strict first-to-last (FIFO) sequence: if you send to 300 members today, tomorrow's run automatically skips those 300 and starts at member 301.
3. **Gmail & Outlook Spam Prevention**:
   - **MIME Multipart/Alternative**: Full responsive HTML + clean RFC 2822 plain-text alternative.
   - **Compliant Headers**: `List-Unsubscribe` (one-click header required by Gmail 2024+ guidelines), `Reply-To: support@devengers.org`, `From: "Devengers Events" <event@devengers.org>`, and custom RFC `Message-ID`.
   - **Real-Time Spam Radar**: Heuristic scanner checking subject length, all-caps ratio, exclamation marks, and promotional trigger keywords.
4. **Interactive Web Dashboard + Full CLI**:
   - Modern glassmorphic Web UI with live queue progress bar, file upload preview, desktop/mobile previewer, and single-click test sending.
   - Comprehensive command-line interface for terminal users and cron automations.

---

## 🌐 Spaceship DNS Configuration for `devengers.org`

To guarantee that your emails from `event@devengers.org` go directly to the inbox and never to the spam folder, enter these records into your **Spaceship Advanced DNS** panel:

| Record Type | Host | Value / Target | Priority | Purpose |
|:---|:---|:---|:---:|:---|
| **MX** | `@` | `mx.zoho.com` *(or `mx.zoho.in` for India)* | 10 | Primary Mail Exchange route to Zoho |
| **MX** | `@` | `mx2.zoho.com` *(or `mx2.zoho.in`)* | 20 | Secondary Mail Exchange backup |
| **MX** | `@` | `mx3.zoho.com` *(or `mx3.zoho.in`)* | 50 | Tertiary Mail Exchange backup |
| **TXT (SPF)** | `@` | `v=spf1 include:zoho.com ~all` | — | **Crucial:** Authorizes Zoho servers to send from `@devengers.org` |
| **TXT (DKIM)**| `zoho._domainkey` | *(Copy public key from Zoho Mail Admin &rarr; DKIM)* | — | **Crucial:** Cryptographically signs outgoing emails |
| **TXT (DMARC)**| `_dmarc` | `v=DMARC1; p=none; rua=mailto:support@devengers.org; sp=none; adkim=r; aspf=r` | — | Enforces Gmail & Yahoo 2024 bulk sender rules |

---

## 🚀 Quick Start

### 1. Configure Credentials (`.env`)

Copy `.env.example` to `.env` (already created for you):
```bash
# Generate an App-Specific Password in Zoho:
# Zoho Account -> Security -> App Passwords -> Generate
SMTP_HOST=smtppro.zoho.in        # Use smtp.zoho.com if registered outside India
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USER=event@devengers.org
SMTP_PASSWORD=your_zoho_app_password

SENDER_NAME="Devengers Events"
SENDER_EMAIL=event@devengers.org
REPLY_TO_EMAIL=support@devengers.org

# Set DRY_RUN=false to enable real email transmission
DRY_RUN=false
```

### 2. Launch the Web Dashboard

```bash
./venv/bin/python3 run.py web
```
Open your browser at **`http://localhost:8000`**:
- **Overview Tab**: Live quota meter showing `X / 300 Sent Today`, total ledger count, and SMTP health.
- **Upload Tab**: Drag and drop your `.xlsx`, `.csv`, or `.pdf` file.
- **Studio Tab**: Edit event details, choose templates, test spam score, and preview in desktop/mobile view.
- **Dispatch Tab**: Run a single test email or trigger the automated batch dispatch with live progress bars.

---

## 💻 CLI Commands

The engine includes a complete command-line interface:

```bash
# 1. Check ledger counts and today's remaining Zoho quota
./venv/bin/python3 run.py status

# 2. Import contacts from an Excel, CSV, or PDF file
./venv/bin/python3 run.py import sample_members.xlsx

# 3. Send a single verification test email
./venv/bin/python3 run.py test --to your_email@gmail.com

# 4. Dispatch today's batch to unemailed members in FIFO order
./venv/bin/python3 run.py send --template event_invite --limit 300

# 5. Display Spaceship DNS records guide
./venv/bin/python3 run.py dns
```

---

## 🧪 Testing & Verification

Run the automated test suite verifying parsers, validators, templates, deliverability score, and the 300/day zero-duplicate logic:

```bash
./venv/bin/pytest tests/
```

All 15 automated test cases verify:
- RFC 5322 email regex and sanitization.
- Multi-format ingestion (`.xlsx`, `.csv`, `.pdf`).
- Dynamic template rendering with plain-text alternative.
- Anti-spam scoring and trigger keyword filtering.
- Sequential FIFO queueing and zero-duplicate continuation across multiple days.

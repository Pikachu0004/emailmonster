# ⚡ Devengers Mail Engine

A production-grade, quota-aware, deduplicating email automation engine engineered for **devengers.org**. Built specifically to combine **Zoho Mail** (for incoming inboxes and reading replies) with **Brevo's Free SMTP Relay** (for guaranteed 300 free outgoing emails every day), strict FIFO contact queueing, and enterprise deliverability standards to guarantee inbox landing in Gmail and Outlook.

---

## 🏗️ Architecture & How It Works

* **Incoming Mailbox Hosting:** Hosted on **Zoho Mail (Free Tier)**. Any replies sent to `support@devengers.org` or `event@devengers.org` land directly in your Zoho Webmail / mobile app inbox.
* **Outgoing 300/Day Automation:** Routed via **Brevo SMTP Relay** (`smtp-relay.brevo.com:587`), giving you a permanent allowance of **300 emails/day completely free** (no credit card required).
* **Automated Schedule:** Runs automatically every single day at **6:00 PM IST (18:00)**.
* **Strict FIFO Ordering & Deduplication:** Processes contacts in order from first to last (FIFO). If you upload 1,000 members and send 300 today, tomorrow's run automatically skips those 300 and starts at member 301.

---

## 🌐 Spaceship DNS Configuration for `devengers.org`

Add these exact records into your **Spaceship Advanced DNS** panel:

| Record Type | Host | Value / Target | Priority | Purpose |
|:---|:---|:---|:---:|:---|
| **MX** | `@` | `mx.zoho.com` *(or `mx.zoho.in` if India)* | 10 | Routes incoming replies into Zoho Webmail |
| **MX** | `@` | `mx2.zoho.com` *(or `mx2.zoho.in`)* | 20 | Secondary Zoho MX backup |
| **MX** | `@` | `mx3.zoho.com` *(or `mx3.zoho.in`)* | 50 | Tertiary Zoho MX backup |
| **TXT (SPF)** | `@` | `v=spf1 include:spf.brevo.com include:zoho.com ~all` | — | **Crucial:** Authorizes both Brevo (300/day outgoing) & Zoho without SPF errors |
| **TXT (DKIM)**| `mail._domainkey` | *(Copy DKIM value from Brevo Dashboard &rarr; Senders & Domains)* | — | **Crucial:** Cryptographically signs outgoing emails |
| **TXT (DMARC)**| `_dmarc` | `v=DMARC1; p=none; rua=mailto:support@devengers.org; sp=none; adkim=r; aspf=r` | — | Enforces Gmail & Yahoo 2024 bulk authentication |

---

## 🚀 Quick Setup (2 Minutes)

### 1. Get Free Brevo SMTP Credentials
1. Sign up for a free account at **[brevo.com](https://www.brevo.com/)** (no credit card needed).
2. Go to **Senders & IP** &rarr; **Senders** &rarr; Add `event@devengers.org` (Name: "Devengers Events").
3. Go to **SMTP & API** &rarr; **SMTP** &rarr; Generate an **SMTP Key**.

### 2. Configure Your `.env`
Edit your `.env` file with your Brevo login and generated key:
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USE_SSL=false
SMTP_USE_TLS=true
SMTP_USER=your_brevo_login_email
SMTP_PASSWORD=your_brevo_smtp_master_key

SENDER_NAME="Devengers Events"
SENDER_EMAIL=event@devengers.org
REPLY_TO_EMAIL=support@devengers.org

DAILY_SEND_LIMIT=300
DRY_RUN=false
```

### 3. Activate the Daily 6:00 PM IST Automation
To automatically dispatch the daily 300 emails at 6:00 PM IST without opening terminal every day:
```bash
./scripts/setup_schedule.sh mac
```
*(On Linux/servers, use `./scripts/setup_schedule.sh cron`)*.

---

## 💻 Manual Commands & Web Dashboard

```bash
# 1. Launch the Web Dashboard
./venv/bin/python3 run.py web
# (Open http://localhost:8000 to upload Excel/PDF files & view live progress)

# 2. Check quota & unemailed contacts status
./venv/bin/python3 run.py status

# 3. Import contacts from an Excel or PDF file
./venv/bin/python3 run.py import sample_members.xlsx

# 4. Send a single test email to your Gmail
./venv/bin/python3 run.py test --to your_email@gmail.com

# 5. Dispatch today's batch to the next 300 members in FIFO order
./venv/bin/python3 run.py send --limit 300
```

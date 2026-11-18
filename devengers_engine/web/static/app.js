// Devengers Mail Engine - Client Controller

let debounceTimer = null;
let dispatchPollingInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  fetchStats();
  refreshPreview();
  fetchLogs();
  fetchDnsGuide();
  setupDragAndDrop();
});

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));

  const targetPanel = document.getElementById(`tab-${tabId}`);
  if (targetPanel) {
    targetPanel.classList.add("active");
  }

  // Set active tab button
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach(btn => {
    if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(tabId)) {
      btn.classList.add("active");
    }
  });

  if (tabId === "overview") fetchStats();
  if (tabId === "dispatch") fetchLogs();
}

async function fetchStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();

    // Daily Quota
    const sentToday = data.daily_quota.sent_today;
    const limit = data.daily_quota.limit;
    const remaining = data.daily_quota.remaining_today;
    const otpUsed = data.daily_quota.used_by_otp || 0;
    const buffer = data.daily_quota.otp_reserve_buffer || 10;
    const pct = data.daily_quota.percentage_used;

    document.getElementById("stat-sent-today").innerText = `${sentToday} / ${limit}`;
    document.getElementById("stat-remaining-quota").innerText = `${remaining} safe for bot (OTPs: ${otpUsed}, Reserved: ${buffer})`;
    document.getElementById("quota-progress-fill").style.width = `${pct}%`;
    document.getElementById("quota-header-badge").innerText = `Bot Allowance: ${remaining} (Reserve: ${buffer})`;

    // Contacts
    document.getElementById("stat-total-contacts").innerText = data.contacts.total_contacts;
    document.getElementById("stat-already-emailed").innerText = data.contacts.already_emailed;
    document.getElementById("stat-pending-contacts").innerText = data.contacts.pending_unemailed;

    // SMTP Status
    const smtpBadge = document.getElementById("smtp-badge");
    if (data.smtp.dry_run) {
      smtpBadge.className = "badge badge-dryrun";
      smtpBadge.innerText = "🛡️ Dry-Run Mode Active";
    } else if (data.smtp.status === "connected") {
      smtpBadge.className = "badge badge-connected";
      smtpBadge.innerText = `⚡ ${data.smtp.provider || "SMTP"} Connected`;
    } else {
      smtpBadge.className = "badge badge-warning";
      smtpBadge.innerText = "⚠️ SMTP Key Needed";
    }

    if (document.getElementById("cfg-smtp-host")) {
      document.getElementById("cfg-smtp-host").innerText = `${data.smtp.provider || data.smtp.host}`;
    }
  } catch (err) {
    console.error("Failed to fetch stats:", err);
  }
}

function setupDragAndDrop() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) {
      uploadFileObj(files[0]);
    }
  });
}

function handleFileUpload(e) {
  if (e.target.files.length) {
    uploadFileObj(e.target.files[0]);
  }
}

async function uploadFileObj(file) {
  const statusEl = document.getElementById("upload-status");
  statusEl.style.display = "block";
  statusEl.innerHTML = `<span style="color: #60a5fa;">Uploading and parsing ${file.name}...</span>`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    statusEl.innerHTML = `
      <div style="padding: 12px; background-color: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; color: #10b981;">
        <strong>Success:</strong> Extracted <strong>${data.total_extracted}</strong> valid contacts! 
        (New: ${data.newly_inserted}, Updated: ${data.existing_updated})
      </div>
    `;

    // Render Preview Table
    if (data.preview_sample && data.preview_sample.length) {
      const card = document.getElementById("upload-preview-card");
      const tbody = document.getElementById("upload-preview-body");
      tbody.innerHTML = "";
      data.preview_sample.forEach(c => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><strong>${c.name}</strong></td>
          <td>${c.first_name}</td>
          <td><code style="color: #38bdf8;">${c.email}</code></td>
          <td><span style="font-size: 11px; color: #94a3b8;">${JSON.stringify(c.extra_data)}</span></td>
        `;
        tbody.appendChild(row);
      });
      card.style.display = "block";
    }

    fetchStats();
  } catch (err) {
    statusEl.innerHTML = `
      <div style="padding: 12px; background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; color: #ef4444;">
        <strong>Upload Error:</strong> ${err.message}
      </div>
    `;
  }
}

function debouncePreview() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    refreshPreview();
  }, 350);
}

function getComposerValues() {
  return {
    template_name: document.getElementById("tpl-select").value,
    subject: document.getElementById("tpl-subject").value,
    event_name: document.getElementById("tpl-event-name").value,
    event_date: document.getElementById("tpl-event-date").value,
    event_time: document.getElementById("tpl-event-time").value,
    event_location: document.getElementById("tpl-event-location").value,
    cta_url: document.getElementById("tpl-cta-url").value,
    cta_text: document.getElementById("tpl-cta-text").value,
    custom_message: document.getElementById("tpl-custom-message").value,
    sample_name: "Kishan Sharma",
    sample_email: "kishan@devengers.org",
  };
}

async function refreshPreview() {
  const payload = getComposerValues();

  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    const iframe = document.getElementById("preview-iframe");
    if (iframe) {
      iframe.srcdoc = data.html;
    }

    // Also run spam check
    checkSpamScore(payload);
  } catch (err) {
    console.error("Preview render failed:", err);
  }
}

async function checkSpamScore(payload) {
  try {
    const res = await fetch("/api/spam-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    const scoreBadge = document.getElementById("spam-score-badge");
    const ratingEl = document.getElementById("spam-rating");
    const issuesEl = document.getElementById("spam-issues");

    scoreBadge.innerText = data.score;
    ratingEl.innerText = `${data.rating} Deliverability`;

    if (data.score >= 85) {
      scoreBadge.style.backgroundColor = "#10b981";
      ratingEl.style.color = "#10b981";
    } else if (data.score >= 70) {
      scoreBadge.style.backgroundColor = "#f59e0b";
      ratingEl.style.color = "#f59e0b";
    } else {
      scoreBadge.style.backgroundColor = "#ef4444";
      ratingEl.style.color = "#ef4444";
    }

    if (data.issues && data.issues.length) {
      issuesEl.innerHTML = `<strong>Deliverability Notes:</strong> ` + data.issues.join(" | ");
    } else {
      issuesEl.innerHTML = `<span style="color: #10b981;">✓ Optimal Gmail deliverability. No trigger words or formatting flags found.</span>`;
    }
  } catch (err) {
    console.error("Spam check failed:", err);
  }
}

function setPreviewWidth(width) {
  const iframe = document.getElementById("preview-iframe");
  iframe.style.maxWidth = width;
  iframe.style.margin = "0 auto";
}

function insertTag(tag) {
  const input = document.getElementById("tpl-subject");
  input.value += ` ${tag}`;
  refreshPreview();
}

async function sendTestEmail() {
  const recipient = document.getElementById("test-recipient").value.trim();
  const resEl = document.getElementById("test-result");
  if (!recipient) {
    resEl.innerHTML = `<span style="color: #ef4444;">Please enter an email address for testing.</span>`;
    return;
  }

  resEl.innerHTML = `<span style="color: #60a5fa;">Dispatching test email to ${recipient}...</span>`;
  const composer = getComposerValues();
  const payload = {
    ...composer,
    recipient_email: recipient,
    recipient_name: "Test Recipient",
  };

  try {
    const res = await fetch("/api/test-send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
      resEl.innerHTML = `<span style="color: #10b981;">✓ Test sent successfully! Message-ID: ${data.message_id}</span>`;
      fetchLogs();
      fetchStats();
    } else {
      resEl.innerHTML = `<span style="color: #ef4444;">✗ Send Failed: ${data.error}</span>`;
    }
  } catch (err) {
    resEl.innerHTML = `<span style="color: #ef4444;">✗ Network Error: ${err.message}</span>`;
  }
}

async function startBatchDispatch() {
  const btn = document.getElementById("btn-start-dispatch");
  const limit = parseInt(document.getElementById("dispatch-limit").value) || 300;
  const composer = getComposerValues();

  btn.disabled = true;
  btn.innerText = "Dispatching...";

  const card = document.getElementById("dispatch-progress-card");
  card.style.display = "block";

  try {
    const res = await fetch("/api/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...composer,
        campaign_name: `${composer.event_name} Dispatch`,
        limit: limit,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Dispatch failed");
    }

    pollDispatchProgress();
  } catch (err) {
    alert("Could not start dispatch: " + err.message);
    btn.disabled = false;
    btn.innerText = "Start Automated Dispatch →";
  }
}

function pollDispatchProgress() {
  if (dispatchPollingInterval) clearInterval(dispatchPollingInterval);

  dispatchPollingInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/dispatch/status");
      const state = await res.json();

      const counter = document.getElementById("dispatch-counter");
      const bar = document.getElementById("dispatch-progress-bar");
      const msg = document.getElementById("dispatch-status-msg");

      counter.innerText = `${state.current_index} / ${state.total}`;
      const pct = state.total > 0 ? (state.current_index / state.total) * 100 : 0;
      bar.style.width = `${pct}%`;

      if (state.last_recipient) {
        msg.innerText = `Sent to ${state.last_recipient} (${state.sent_count} successful, ${state.failed_count} failed)`;
      } else {
        msg.innerText = state.status_message;
      }

      if (!state.is_running) {
        clearInterval(dispatchPollingInterval);
        document.getElementById("btn-start-dispatch").disabled = false;
        document.getElementById("btn-start-dispatch").innerText = "Start Automated Dispatch →";
        fetchStats();
        fetchLogs();
      }
    } catch (err) {
      console.error("Progress polling error:", err);
    }
  }, 1000);
}

async function fetchLogs() {
  try {
    const res = await fetch("/api/logs?limit=30");
    const data = await res.json();

    const tbody = document.getElementById("logs-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!data.logs.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #64748b;">No emails dispatched yet.</td></tr>`;
      return;
    }

    data.logs.forEach(l => {
      const row = document.createElement("tr");
      const statusClass = l.status === "SUCCESS" ? "color: #10b981;" : "color: #ef4444;";
      row.innerHTML = `
        <td><strong style="color: #fff;">${l.recipient_email}</strong></td>
        <td>${l.contact_name || '-'}</td>
        <td><span style="${statusClass} font-weight: 700;">${l.status}</span></td>
        <td><code style="font-size: 11px; color: #94a3b8;">${l.message_id || '-'}</code></td>
        <td style="font-size: 12px; color: #94a3b8;">${new Date(l.sent_at).toLocaleTimeString()}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error("Failed to fetch logs:", err);
  }
}

async function fetchDnsGuide() {
  try {
    const res = await fetch("/api/dns-guide");
    const data = await res.json();

    const tbody = document.getElementById("dns-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    data.guide.records.forEach(r => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><span class="tag-pill" style="color: #60a5fa;">${r.type}</span></td>
        <td><code>${r.host}</code></td>
        <td><code style="color: #cbd5e1; word-break: break-all;">${r.value}</code></td>
        <td>${r.priority || '-'}</td>
        <td style="font-size: 12px; color: #94a3b8;">${r.purpose}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error("Failed to fetch DNS guide:", err);
  }
}

"""
Email Notifier
Sends job review emails to Melanie for 60-79% match jobs.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger("email_notifier")


def send_review_email(jobs: List[Dict], email_config: dict) -> bool:
    """
    Send a digest email with jobs that need manual review (60-79% match).

    Each job dict:
      {"title", "company", "url", "platform", "score",
       "matched_skills", "missing_skills", "summary", "salary"}
    """
    if not jobs:
        return True
    if not email_config.get("from_password"):
        logger.warning("Email password not set — skipping notification")
        return False

    subject = (
        f"{email_config['subject_prefix']} {len(jobs)} Job(s) Need Your Review "
        f"— {datetime.now().strftime('%b %d, %I:%M %p')}"
    )

    html_rows = ""
    for j in jobs:
        matched = ", ".join(j.get("matched_skills", [])[:8]) or "—"
        missing = ", ".join(j.get("missing_skills", [])[:6]) or "—"
        score_color = "#e67e22" if j["score"] < 75 else "#27ae60"
        html_rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #eee;">
            <div style="font-size:16px;font-weight:700;color:#1a1a2e;">
              {j['title']}
            </div>
            <div style="font-size:13px;color:#666;margin-top:3px;">
              {j['company']} &nbsp;·&nbsp; {j['platform']}
            </div>
            <div style="margin-top:8px;font-size:13px;color:#444;">
              {j.get('summary','No summary available.')}
            </div>
            <div style="margin-top:8px;">
              <span style="background:#eafaf1;color:#27ae60;padding:3px 10px;
                border-radius:12px;font-size:12px;">✓ {matched}</span>
            </div>
            <div style="margin-top:6px;">
              <span style="background:#fef9e7;color:#e67e22;padding:3px 10px;
                border-radius:12px;font-size:12px;">⚠ Missing: {missing}</span>
            </div>
          </td>
          <td style="padding:16px;border-bottom:1px solid #eee;
              text-align:center;vertical-align:top;white-space:nowrap;">
            <div style="font-size:28px;font-weight:800;color:{score_color};">
              {j['score']}%
            </div>
            <div style="font-size:11px;color:#999;margin-bottom:12px;">match</div>
            <a href="{j['url']}" style="display:inline-block;
              background:#1a1a2e;color:white;padding:8px 18px;
              border-radius:8px;text-decoration:none;font-size:12px;
              font-weight:600;">View Job →</a>
            <br><br>
            <a href="{j['url']}" style="display:inline-block;
              background:#00c896;color:white;padding:8px 18px;
              border-radius:8px;text-decoration:none;font-size:12px;
              font-weight:600;">Apply Now ✓</a>
          </td>
        </tr>"""

    html_body = f"""
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;
      background:#f5f5f5;margin:0;padding:0;">
    <div style="max-width:680px;margin:30px auto;background:white;
      border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

      <!-- Header -->
      <div style="background:#1a1a2e;padding:28px 32px;">
        <div style="font-size:22px;font-weight:800;color:white;">
          🤖 AutoApply Bot
        </div>
        <div style="color:#00c896;font-size:14px;margin-top:4px;">
          {len(jobs)} job{'s' if len(jobs)>1 else ''} matched 60–79% — needs your decision
        </div>
        <div style="color:#8888aa;font-size:12px;margin-top:4px;">
          {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}
        </div>
      </div>

      <!-- Jobs Table -->
      <table style="width:100%;border-collapse:collapse;">
        {html_rows}
      </table>

      <!-- Footer -->
      <div style="background:#f9f9f9;padding:20px 32px;
        border-top:1px solid #eee;text-align:center;">
        <p style="color:#999;font-size:12px;margin:0;">
          Your bot is scanning 20 platforms every 15 minutes, 24/7.<br>
          Jobs ≥80% are being applied to automatically.
        </p>
      </div>
    </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_config["from_email"]
    msg["To"]      = email_config["to_email"]
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as s:
            s.starttls()
            s.login(email_config["from_email"], email_config["from_password"])
            s.send_message(msg)
        logger.info(f"Review email sent: {len(jobs)} jobs")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_applied_confirmation(job: Dict, email_config: dict) -> bool:
    """Quick confirmation email after auto-applying."""
    if not email_config.get("from_password"):
        return False

    subject = (
        f"{email_config['subject_prefix']} ✅ Applied: "
        f"{job['title']} @ {job['company']} ({job['score']}% match)"
    )

    html = f"""
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;">
    <div style="max-width:500px;margin:20px auto;padding:24px;
      background:#f0fdf4;border-radius:12px;border:1px solid #bbf7d0;">
      <div style="font-size:18px;font-weight:700;color:#15803d;">
        ✅ Auto-Applied Successfully
      </div>
      <div style="margin-top:12px;color:#333;">
        <strong>{job['title']}</strong> at <strong>{job['company']}</strong>
      </div>
      <div style="color:#666;margin-top:4px;font-size:13px;">
        Platform: {job['platform']} &nbsp;·&nbsp;
        Match: <strong style="color:#15803d;">{job['score']}%</strong>
      </div>
      <a href="{job['url']}" style="display:inline-block;margin-top:14px;
        background:#15803d;color:white;padding:8px 18px;
        border-radius:8px;text-decoration:none;font-size:13px;">
        View Application →
      </a>
    </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_config["from_email"]
    msg["To"]      = email_config["to_email"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as s:
            s.starttls()
            s.login(email_config["from_email"], email_config["from_password"])
            s.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Confirmation email failed: {e}")
        return False

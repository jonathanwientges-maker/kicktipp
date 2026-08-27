"""
Email delivery (D3): SMTP via Gmail, HTML report as both body and
attachment.

Credentials from env vars GMAIL_ADDRESS, GMAIL_APP_PASSWORD, recipient
list MAIL_TO (comma-separated). On SMTP failure: retry twice (3 attempts
total), then still let the caller commit the report to the repo so
nothing is lost, and exit non-zero so the workflow shows red.
"""
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 5


class EmailSendError(Exception):
    pass


def build_message(subject, html_body, attachment_filename, attachment_html,
                   sender, recipients):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(
        "This email contains an HTML report. Please view it in an HTML-"
        "capable mail client, or open the attached file.", "plain"
    ))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    # text/html (not application/html, which isn't a registered MIME
    # type) is the correct content-type for an .html attachment; the
    # explicit Content-Disposition: attachment header still makes mail
    # clients offer it as a downloadable file rather than only inlining
    # it, alongside the body copy above.
    attachment = MIMEText(attachment_html, "html", _charset="utf-8")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=attachment_filename
    )
    msg.attach(attachment)
    return msg


def send_report_email(matchday_number, n_tips, html_report, dry_run=False):
    """
    Send the weekly report email. Reads credentials from env vars.
    Raises EmailSendError after MAX_ATTEMPTS failed attempts.

    If dry_run=True, does not attempt to send -- just validates
    credentials/recipients are configured and returns without side
    effects (used by predict.py --no-email).
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    mail_to_raw = os.environ.get("MAIL_TO", "")
    recipients = [r.strip() for r in mail_to_raw.split(",") if r.strip()]

    if dry_run:
        print("[notify] --no-email dry run: skipping actual send. "
              "Configured recipients: {0}".format(recipients or "(none)"))
        return

    if not gmail_address or not gmail_password:
        raise EmailSendError(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in environment."
        )
    if not recipients:
        raise EmailSendError("MAIL_TO is empty -- no recipients configured.")

    subject = "⚽ Kicktipp MD{0}: {1} tips ready".format(matchday_number, n_tips)
    attachment_filename = "matchday_{0:02d}_report.html".format(matchday_number)
    msg = build_message(subject, html_report, attachment_filename, html_report,
                         gmail_address, recipients)

    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(gmail_address, gmail_password)
                server.sendmail(gmail_address, recipients, msg.as_string())
            print("[notify] Email sent successfully to {0} (attempt {1}/{2}).".format(
                recipients, attempt, MAX_ATTEMPTS
            ))
            return
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
            print("[notify] SMTP send attempt {0}/{1} failed: {2}".format(
                attempt, MAX_ATTEMPTS, exc
            ))
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)

    raise EmailSendError(
        "Failed to send report email after {0} attempts: {1}".format(
            MAX_ATTEMPTS, last_err
        )
    )

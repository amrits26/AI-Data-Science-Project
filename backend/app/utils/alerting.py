"""Email alerting utility for Imperial Cars AI observability."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

def send_alert_email(subject: str, body: str, to: str = None):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_addr = os.getenv("ALERT_FROM", smtp_user)
    to_addr = to or os.getenv("ALERT_TO")
    if not (smtp_host and smtp_user and smtp_pass and to_addr):
        raise RuntimeError("Missing SMTP or alerting environment variables.")

    msg = MIMEMultipart()
    msg["From"] = formataddr(("Imperial AI Alert", from_addr))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, [to_addr], msg.as_string())

import os
import smtplib
from email.message import EmailMessage

EMAIL_OUTBOX: list[tuple[str, str, str]] = []
SMS_OUTBOX: list[tuple[str, str]] = []


def send_email(to_email: str, subject: str, message: str):
    if os.getenv("TESTING") == "1":
        EMAIL_OUTBOX.append((to_email, subject, message))
        return
    server = os.getenv("SMTP_SERVER")
    if not server:
        return
    from_addr = os.getenv("EMAIL_FROM", "noreply@example.com")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(message)
    with smtplib.SMTP(server) as s:
        s.send_message(msg)


def send_sms(to_number: str, message: str):
    if os.getenv("TESTING") == "1":
        SMS_OUTBOX.append((to_number, message))
        return
    provider = os.getenv("SMS_PROVIDER")
    if provider:
        pass


def send_daily_digest(db):
    from datetime import datetime, timezone
    from . import models

    now = datetime.now(timezone.utc)
    users = db.query(models.User).all()
    for user in users:
        if not user.email:
            continue

        if user.digest_frequency and user.digest_frequency != "daily":
            continue
        since = user.last_digest
        notifs = (
            db.query(models.Notification)
            .filter(models.Notification.user_id == user.id)
            .filter(models.Notification.created_at > since)
            .all()
        )
        if notifs:
            if (
                user.quiet_hours_enabled
                and user.quiet_hours_start
                and user.quiet_hours_end
            ):
                current_time = now.time()
                start = user.quiet_hours_start
                end = user.quiet_hours_end
                in_quiet_window = False
                if start <= end:
                    in_quiet_window = start <= current_time < end
                else:
                    in_quiet_window = current_time >= start or current_time < end
                if in_quiet_window:
                    continue
            content = "\n".join(n.message for n in notifs)
            send_email(user.email, "Daily Notification Digest", content)
            user.last_digest = now
    db.commit()

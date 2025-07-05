import os
import datetime
from datetime import timezone
from celery import Celery
from celery.schedules import crontab
from .database import SessionLocal
from uuid import UUID
from .sequence import process_sequence_file
from . import models

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
celery_app = Celery("tasks", broker=CELERY_BROKER_URL)
celery_app.conf.task_always_eager = (
    CELERY_BROKER_URL == "memory://" or os.getenv("TESTING") == "1"
)

@celery_app.task
def analyze_sequence_job(job_id: str, data: bytes, fmt: str):
    db = SessionLocal()
    job = db.get(models.SequenceAnalysisJob, UUID(job_id))
    if not job:
        db.close()
        return
    try:
        result = process_sequence_file(data, fmt)
        job.result = result
        job.status = "completed"
    except Exception:
        job.status = "failed"
        job.result = []
    db.commit()
    db.close()


def enqueue_analyze_sequence_job(job_id: str, data: bytes, fmt: str):
    if celery_app.conf.task_always_eager:
        analyze_sequence_job(job_id, data, fmt)
    else:
        analyze_sequence_job.delay(job_id, data, fmt)


celery_app.conf.beat_schedule = {
    "daily-backup": {
        "task": "app.tasks.backup_database",
        "schedule": crontab(hour=0, minute=0),
    },
    "inventory-warning": {
        "task": "app.tasks.check_inventory_levels",
        "schedule": crontab(hour=7, minute=0),
    },
}


@celery_app.task
def backup_database():
    dest = os.getenv("BACKUP_DIR", "/tmp/backups")
    os.makedirs(dest, exist_ok=True)
    fname = os.path.join(
        dest,
        f"backup_{datetime.datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}" + ".txt",
    )
    with open(fname, "w") as f:
        f.write("backup")
    return fname


@celery_app.task
def check_inventory_levels():
    from .assistant import inventory_forecast
    from . import notify

    db = SessionLocal()
    threshold = int(os.getenv("INVENTORY_WARNING_DAYS", "7"))
    since = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)
    users = db.query(models.User).all()
    for user in users:
        forecasts = inventory_forecast(user, db)
        for f in forecasts:
            days = f.get("projected_days")
            if days is None or days > threshold:
                continue
            msg = f"{f['name']} may run out in {int(days)} days"
            exists = (
                db.query(models.Notification)
                .filter(
                    models.Notification.user_id == user.id,
                    models.Notification.message == msg,
                    models.Notification.created_at > since,
                )
                .first()
            )
            if exists:
                continue
            pref = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=user.id,
                    pref_type="inventory_alert",
                    channel="in_app",
                )
                .first()
            )
            if not pref or pref.enabled:
                db.add(models.Notification(user_id=user.id, message=msg))
            pref_email = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=user.id,
                    pref_type="inventory_alert",
                    channel="email",
                )
                .first()
            )
            if (not pref_email or pref_email.enabled) and user.email:
                notify.send_email(user.email, "Inventory Alert", msg)
    db.commit()
    db.close()

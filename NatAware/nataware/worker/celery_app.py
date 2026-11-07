"""Celery application.

DEMO_MODE=true (default): tasks run eagerly, in-process, so no Redis or worker is needed.
DEMO_MODE=false: tasks go through Redis; run a worker and beat:

    celery -A nataware.worker.celery_app worker --loglevel=info --pool=solo
    celery -A nataware.worker.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from nataware.config import settings

celery_app = Celery(
    "nataware",
    broker="memory://" if settings.demo_mode else settings.redis_url,
    backend="cache+memory://" if settings.demo_mode else settings.redis_url,
    include=["nataware.worker.tasks"],
)

celery_app.conf.update(
    task_always_eager=settings.demo_mode,
    task_eager_propagates=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/London",
    beat_schedule={
        # Phase 3: daily exogenous data aggregation + threat matrix.
        "refresh-threats-daily": {
            "task": "threats.refresh",
            "schedule": crontab(hour=7, minute=0),
        },
        # Phase 4 temporal trigger: Friday 16:00 weekend preparation.
        "weekend-prep-friday": {
            "task": "coaching.weekend_prep",
            "schedule": crontab(day_of_week="fri", hour=16, minute=0),
        },
        # Phase 2: sweep for any untagged transactions.
        "tag-untagged-hourly": {
            "task": "tagging.tag_untagged",
            "schedule": crontab(minute=15),
        },
    },
)

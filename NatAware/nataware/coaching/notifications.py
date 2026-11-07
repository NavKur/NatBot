"""Notification delivery.

Production: push (FCM/APNs), email, or a queued ElevenLabs audio message.
DEMO: every channel just records the nudge in the store (the API exposes it at
`GET /nudges`) and logs it, so a front end can pick it up.
"""

from __future__ import annotations

import logging
from typing import Any

from nataware.data.store import get_store

log = logging.getLogger("nataware.notifications")

CHANNELS = ("push", "email", "audio")


def deliver(nudge: dict[str, Any]) -> dict[str, Any]:
    channel = nudge.get("channel", "push")
    if channel not in CHANNELS:
        raise ValueError(f"Unknown channel {channel!r}")
    nudge = {**nudge, "delivered": True, "delivery": f"demo-{channel}"}
    get_store().append("nudges", nudge)
    log.info("[%s] %s - %s", channel.upper(), nudge["title"], nudge["message"])
    return nudge

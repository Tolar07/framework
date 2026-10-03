"""
WhatsApp delivery — the daily push's copy channel (official Meta Cloud API).

Telegram stays the phone-critical channel; WhatsApp mirrors the same stamped
text so the user's two phones say the same thing. Delivery is best-effort: a
failure here is logged loudly but never fails the run (see run_daily wiring).

One rule is enforced by WhatsApp itself, so it is enforced here: a
BUSINESS-INITIATED message (the 7am push is business-initiated) must go out as
an approved TEMPLATE message — free-form text is only allowed inside the
24-hour customer-service window after the user messages the number. The
template used has a single {{1}} body placeholder, so one template carries any
content. If the (stamped) text outgrows the template parameter cap, it is split
into a few messages, mirroring how Telegram splits a long board.

Same discipline as output/notify.py: never raises, returns (ok, notes), retries
transient faults, and refuses to send if credentials are missing.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from output import notify

WHATSAPP_API = "https://graph.facebook.com/v23.0/{phone_number_id}/messages"

# A template text parameter is capped (on the order of ~1 KB). Today's compact
# push is well under this; the cap only matters if the board ever grows.
WHATSAPP_PARAM_MAX = 1000

# Credentials read from env. Unset/empty ⇒ WhatsApp silently off, exactly like
# the Telegram token guard in notify.py — the framework behaves as today.
_ENV_KEYS = ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO")


def send_whatsapp(body: str, token: Optional[str] = None,
                  phone_number_id: Optional[str] = None,
                  to: Optional[str] = None,
                  template_name: Optional[str] = None,
                  language: Optional[str] = None) -> tuple[bool, list[str]]:
    """Send `body` as a template message. Returns (ok, notes). Never raises.

    Uses the same phase stamp + chunking as Telegram so both channels are
    byte-identical (notify.deliver stamps; this mirrors that)."""
    notes: list[str] = []
    token = token or os.environ.get("WHATSAPP_TOKEN")
    phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    to = to or os.environ.get("WHATSAPP_TO")
    template_name = (template_name or os.environ.get("WHATSAPP_TEMPLATE_NAME")
                     or "olp_daily_pick")
    language = (language or os.environ.get("WHATSAPP_LANGUAGE") or "en")

    if requests is None:
        return False, ["requests not installed — cannot send WhatsApp"]
    missing = [k for k, v in zip(_ENV_KEYS,
                                 (token, phone_number_id, to)) if not v]
    if missing:
        return False, [f"{', '.join(missing)} not set — WhatsApp delivery skipped"]

    parts = notify._chunk(notify._stamp(body), limit=WHATSAPP_PARAM_MAX)
    ok = True
    for i, part in enumerate(parts, 1):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": [{"type": "body",
                                "parameters": [{"type": "text", "text": part}]}],
            },
        }
        last_err = None
        for attempt in range(3):
            try:
                r = requests.post(
                    WHATSAPP_API.format(phone_number_id=phone_number_id),
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30)
                data = r.json()
                if r.status_code == 200 and data.get("messages"):
                    last_err = None
                    break
                last_err = (data.get("error", {}).get("message")
                            or f"HTTP {r.status_code}")
            except Exception as e:
                last_err = str(e)[:120]
            time.sleep(2 * (attempt + 1))
        if last_err:
            ok = False
            notes.append(f"WhatsApp part {i} of {len(parts)} FAILED after 3 "
                         f"attempts: {last_err}")
    notes.append(f"delivered {len(parts)} part(s) to WhatsApp" if ok
                 else "WhatsApp DELIVERY FAILED — see note above")
    return ok, notes


def deliver(body: str) -> tuple[bool, list[str]]:
    """Best-effort WhatsApp copy of the push. No disk save — Telegram already
    wrote the board; WhatsApp is a mirror. Returns (ok, notes)."""
    return send_whatsapp(body)

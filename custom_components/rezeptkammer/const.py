"""Konstanten der RezeptKammer-Integration."""
from __future__ import annotations

DOMAIN = "rezeptkammer"
DEFAULT_URL = "https://rezeptkammer.de"
CONF_URL = "url"
CONF_TOKEN = "token"

# Ereignis auf dem Home-Assistant-Bus fuer eigene Automationen:
# trigger: event / event_type: rezeptkammer_event / event_data: {type: timer_finished}
BUS_EVENT = "rezeptkammer_event"
EVENT_TYPES = [
    "timer_started",
    "timer_finished",
    "timer_cancelled",
    "oven_preheat",
    "cooking_started",
    "cooking_step",
    "cooking_finished",
]

# Kochmodus gilt als beendet, wenn so lange nichts mehr kam (wie auf dem Server)
COOKING_IDLE_MINUTES = 90
# Ab weniger Prisen meldet der Binaersensor "Prisen knapp"
LOW_CREDITS = 5

FULL_REFRESH_MINUTES = 10
EVENT_WAIT_SECONDS = 20

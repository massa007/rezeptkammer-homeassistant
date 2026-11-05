"""Sensoren: Ende des laufenden Kochmodus-Timers und Rezeptvorschlag des Tages."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .coordinator import parse_utc
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([TimerEndSensor(coordinator, "timer_end"), SuggestionSensor(coordinator, "suggestion")])


class TimerEndSensor(RezeptKammerEntity, SensorEntity):
    """Zeitpunkt, an dem der Timer im Kochmodus ablaeuft (leer = kein Timer)."""

    _attr_translation_key = "timer_end"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        return parse_utc((self.coordinator.data.active_timer or {}).get("ends_at"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        timer = self.coordinator.data.active_timer or {}
        return {k: timer.get(k) for k in ("label", "duration", "recipe", "recipe_url")}


class SuggestionSensor(RezeptKammerEntity, SensorEntity):
    """Rezeptvorschlag des Tages aus den eigenen Rezepten."""

    _attr_translation_key = "suggestion"

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data.suggestion or {}).get("title")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.data.suggestion or {}
        return {"url": s.get("url"), "image_url": s.get("image_url"),
                "total_time_min": s.get("total_time_min"), "servings": s.get("servings")}

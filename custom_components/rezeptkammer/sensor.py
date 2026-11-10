"""Sensoren: laufender Kochmodus-Timer (Ende, Dauer, Rezept, Schritt), Kochmodus (Rezept, Schritt, Fortschritt),
Rezeptvorschlag des Tages, Prisen."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .coordinator import RezeptKammerCoordinator, parse_utc
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        TimerEndSensor(coordinator, "timer_end"), TimerDurationSensor(coordinator, "timer_duration"),
        TimerRecipeSensor(coordinator, "timer_recipe"), TimerStepSensor(coordinator, "timer_step"),
        SuggestionSensor(coordinator, "suggestion"),
        CookingRecipeSensor(coordinator, "cooking_recipe"), CookingStepSensor(coordinator, "cooking_step"),
        CookingProgressSensor(coordinator, "cooking_progress"),
    ])
    if coordinator.data.credits is not None:  # unbegrenztes Guthaben: kein Prisen-Sensor
        async_add_entities([CreditsSensor(coordinator, "credits")])


def _step_text(step: int | None, text: str | None) -> str | None:
    """"3: Nudeln 10 Minuten kochen" - Zustand hoechstens 255 Zeichen."""
    if not step:
        return None
    value = f"{step}: {text or ''}".strip()
    return value if len(value) <= 255 else value[:254] + "…"


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
        return {k: timer.get(k) for k in ("label", "duration", "recipe", "recipe_url", "step", "step_text")}


class TimerDurationSensor(RezeptKammerEntity, SensorEntity):
    """Gesamtdauer des laufenden Timers (inkl. +1/-1 im Kochmodus)."""

    _attr_translation_key = "timer_duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data.active_timer or {}).get("duration")


class TimerRecipeSensor(RezeptKammerEntity, SensorEntity):
    """Rezept, in dessen Kochmodus der laufende Timer gestartet wurde."""

    _attr_translation_key = "timer_recipe"

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data.active_timer or {}).get("recipe")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"url": (self.coordinator.data.active_timer or {}).get("recipe_url")}


class TimerStepSensor(RezeptKammerEntity, SensorEntity):
    """Kochschritt des laufenden Timers als "3: Nudeln 10 Minuten kochen" (Zustand max. 255 Zeichen)."""

    _attr_translation_key = "timer_step"

    @property
    def native_value(self) -> str | None:
        timer = self.coordinator.data.active_timer or {}
        return _step_text(timer.get("step"), timer.get("step_text"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        timer = self.coordinator.data.active_timer or {}
        return {"step": timer.get("step"), "text": timer.get("step_text")}


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
                "total_time_min": s.get("total_time_min"), "servings": s.get("servings"), "kcal": s.get("kcal")}


class CookingRecipeSensor(RezeptKammerEntity, SensorEntity):
    """Rezept, das gerade im Kochmodus offen ist."""

    _attr_translation_key = "cooking_recipe"

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data.cooking or {}).get("recipe")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator.data.cooking or {}
        return {"url": c.get("recipe_url"), "started_at": c.get("started_at")}


class CookingStepSensor(RezeptKammerEntity, SensorEntity):
    """Aktueller Schritt im Kochmodus als "3: Teig 10 Minuten ruhen lassen"."""

    _attr_translation_key = "cooking_step"

    @property
    def native_value(self) -> str | None:
        c = self.coordinator.data.cooking or {}
        return _step_text(c.get("step"), c.get("step_text"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator.data.cooking or {}
        return {"step": c.get("step"), "total": c.get("total"), "text": c.get("step_text")}


class CookingProgressSensor(RezeptKammerEntity, SensorEntity):
    """Fortschritt im Kochmodus: Schritt 3 von 8 = 38 %."""

    _attr_translation_key = "cooking_progress"
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> int | None:
        c = self.coordinator.data.cooking or {}
        if not c.get("step") or not c.get("total"):
            return None
        return round(min(c["step"], c["total"]) / c["total"] * 100)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator.data.cooking or {}
        return {"step": c.get("step"), "total": c.get("total")}


class CreditsSensor(RezeptKammerEntity, SensorEntity):
    """Verfuegbare Prisen. Einheit nach der Sprache von Home Assistant - uebersetzte Einheiten nimmt
    Home Assistant immer auf Englisch (stabile Statistik), dann stuende auch bei Deutsch "pinches" da."""

    _attr_translation_key = "credits"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RezeptKammerCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        language = coordinator.hass.config.language or ""
        self._attr_native_unit_of_measurement = "Prisen" if language.startswith("de") else "pinches"

    @property
    def native_value(self) -> float | int | None:
        credits = self.coordinator.data.credits
        return int(credits) if credits is not None and credits == int(credits) else credits  # 12 statt 12.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"url": f"{self.coordinator.api.base_url}/guthaben"}


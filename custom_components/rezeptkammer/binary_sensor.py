"""Binaersensoren: Kochmodus laeuft, Prisen werden knapp."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .const import LOW_CREDITS
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [CookingSensor(coordinator, "cooking_active")]
    if coordinator.data.credits is not None:  # unbegrenztes Guthaben: keine Prisen-Entitaeten
        entities.append(LowCreditsSensor(coordinator, "credits_low"))
    async_add_entities(entities)


class CookingSensor(RezeptKammerEntity, BinarySensorEntity):
    """An, solange ein Rezept im Kochmodus offen ist (aus beim Verlassen oder nach 90 Min. ohne Aktivitaet)."""

    _attr_translation_key = "cooking_active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.cooking is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator.data.cooking or {}
        return {k: c.get(k) for k in ("recipe", "recipe_url", "started_at", "step", "total")}


class LowCreditsSensor(RezeptKammerEntity, BinarySensorEntity):
    """An, wenn weniger als LOW_CREDITS Prisen uebrig sind."""

    _attr_translation_key = "credits_low"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        credits = self.coordinator.data.credits
        return None if credits is None else credits < LOW_CREDITS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"threshold": LOW_CREDITS}

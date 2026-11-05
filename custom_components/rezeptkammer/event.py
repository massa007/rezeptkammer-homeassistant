"""Ereignis-Entitaet 'Kochen': Timer, Ofen vorheizen, Kochschritte."""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .const import EVENT_TYPES
from .coordinator import signal_event
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CookingEvent(entry.runtime_data, "cooking")])


class CookingEvent(RezeptKammerEntity, EventEntity):
    _attr_translation_key = "cooking"
    _attr_event_types = EVENT_TYPES

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, signal_event(self.coordinator.config_entry.entry_id), self._handle))

    @callback
    def _handle(self, event_type: str, data: dict[str, Any]) -> None:
        if event_type in EVENT_TYPES:
            self._trigger_event(event_type, data)
            self.async_write_ha_state()

"""Bild des Rezeptvorschlags fuers Dashboard."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RezeptKammerConfigEntry
from .coordinator import RezeptKammerCoordinator
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SuggestionImage(hass, entry.runtime_data)])


class SuggestionImage(RezeptKammerEntity, ImageEntity):
    _attr_translation_key = "suggestion_image"

    def __init__(self, hass: HomeAssistant, coordinator: RezeptKammerCoordinator) -> None:
        RezeptKammerEntity.__init__(self, coordinator, "suggestion_image")
        ImageEntity.__init__(self, hass)
        self._sync()

    @callback
    def _sync(self) -> None:
        url = (self.coordinator.data.suggestion or {}).get("image_url")
        if url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._sync()
        super()._handle_coordinator_update()

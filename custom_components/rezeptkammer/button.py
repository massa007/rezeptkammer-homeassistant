"""Knopf: Zutaten des Rezeptvorschlags auf die Einkaufsliste."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .api import RezeptKammerError
from .const import DOMAIN
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SuggestionToListButton(entry.runtime_data, "suggestion_to_list")])


class SuggestionToListButton(RezeptKammerEntity, ButtonEntity):
    """Legt die Zutaten auf die Liste, zu der das Rezept gehoert (eigenes Rezept: private Liste,
    Kammer-Rezept: Liste der Kammer). Mehrfaches Tippen kurz hintereinander verdoppelt nichts."""

    _attr_translation_key = "suggestion_to_list"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.suggestion is not None

    async def async_press(self) -> None:
        try:
            result = await self.coordinator.api.suggestion_to_list()
        except RezeptKammerError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="suggestion_to_list_failed") from err
        await self.coordinator.async_refresh_list((result or {}).get("list_id", "private"))

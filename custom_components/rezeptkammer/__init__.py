"""RezeptKammer fuer Home Assistant: Einkaufslisten, Kochmodus, Rezeptvorschlag, Prisen."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RezeptKammerApi, RezeptKammerError
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import RezeptKammerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.EVENT, Platform.IMAGE, Platform.SENSOR, Platform.TODO]

type RezeptKammerConfigEntry = ConfigEntry[RezeptKammerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RezeptKammerConfigEntry) -> bool:
    api = RezeptKammerApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = RezeptKammerCoordinator(hass, entry, api)
    coordinator.instance_id = await instance_id.async_get(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, coordinator.async_listen(), f"{DOMAIN}_events")
    entry.async_on_unload(coordinator.async_shutdown_timer)
    entry.async_on_unload(coordinator.async_shutdown_cooking)
    _remove_stale_devices(hass, entry)
    return True


def _remove_stale_devices(hass: HomeAssistant, entry: RezeptKammerConfigEntry) -> None:
    """Zu einem Eintrag gehoert nur noch das Konto-Geraet - aeltere Geraete samt ihrer Entitaeten aufraeumen."""
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) not in device.identifiers:
            registry.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, device: dr.DeviceEntry,
) -> bool:
    """Von Hand loeschen laesst sich jedes Geraet ausser dem Konto-Geraet."""
    return (DOMAIN, entry.entry_id) not in device.identifiers


async def async_unload_entry(hass: HomeAssistant, entry: RezeptKammerConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RezeptKammerConfigEntry) -> None:
    """Integration entfernt: Zugangsschluessel bei der RezeptKammer widerrufen."""
    api = RezeptKammerApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    try:
        await api.revoke()
    except RezeptKammerError:
        pass

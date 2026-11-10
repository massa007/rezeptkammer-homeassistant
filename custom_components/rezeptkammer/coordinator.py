"""Datenhaltung + Ereignis-Empfang der RezeptKammer-Integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import RezeptKammerApi, RezeptKammerAuthError, RezeptKammerConnectionError, RezeptKammerError
from .const import BUS_EVENT, COOKING_IDLE_MINUTES, DOMAIN, EVENT_WAIT_SECONDS, FULL_REFRESH_MINUTES

_LOGGER = logging.getLogger(__name__)


@dataclass
class RezeptKammerData:
    """Stand aller Listen und des Kochmodus."""

    lists: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> {name, items}
    active_timer: dict[str, Any] | None = None
    suggestion: dict[str, Any] | None = None
    account: str | None = None
    # laufender Kochmodus: recipe, recipe_url, started_at, step, total, step_text, expires_at
    cooking: dict[str, Any] | None = None
    credits: float | None = None  # None = unbegrenztes Guthaben (dann keine Prisen-Entitaeten)
    # Kammer-Listen, die in diesem Home Assistant schon ein anderes Konto zeigt (Haushalt mit mehreren Konten)
    lists_elsewhere: set[str] = field(default_factory=set)


def signal_event(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}_event"


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


class RezeptKammerCoordinator(DataUpdateCoordinator[RezeptKammerData]):
    """Holt den Gesamtstand alle FULL_REFRESH_MINUTES und reagiert sofort auf Ereignisse."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: RezeptKammerApi) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN,
            update_interval=timedelta(minutes=FULL_REFRESH_MINUTES),
        )
        self.api = api
        self.instance_id: str | None = None
        self._timer_unsub: CALLBACK_TYPE | None = None
        self._cooking_unsub: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> RezeptKammerData:
        try:
            state = await self.api.state(self.instance_id)
            lists: dict[str, dict[str, Any]] = {}
            elsewhere: set[str] = set()
            for lst in state.get("lists", []):
                if lst.get("elsewhere"):
                    elsewhere.add(lst["id"])
                    continue
                lists[lst["id"]] = {"name": lst["name"], "items": await self.api.list_items(lst["id"])}
        except RezeptKammerAuthError as err:
            raise ConfigEntryAuthFailed("Zugangsschluessel ungueltig") from err
        except RezeptKammerError as err:
            raise UpdateFailed(str(err)) from err
        data = RezeptKammerData(lists=lists, active_timer=state.get("active_timer"),
                                suggestion=state.get("suggestion"), account=state.get("user"),
                                lists_elsewhere=elsewhere, cooking=state.get("cooking"),
                                credits=state.get("credits"))
        self._schedule_timer(data.active_timer)
        self._schedule_cooking_end(data.cooking)
        return data

    async def async_refresh_list(self, list_id: str) -> None:
        if self.data and list_id in self.data.lists_elsewhere:
            return  # zeigt ein anderes Konto in diesem Home Assistant
        if not self.data or list_id not in self.data.lists:
            await self.async_request_refresh()  # neue Kammer -> alles neu holen
            return
        try:
            items = await self.api.list_items(list_id)
        except RezeptKammerAuthError:
            self.config_entry.async_start_reauth(self.hass)
            return
        except RezeptKammerError as err:
            _LOGGER.debug("Liste %s nicht aktualisiert: %s", list_id, err)
            return
        self.data.lists[list_id]["items"] = items
        self.async_set_updated_data(self.data)

    # --- Timer: Ende wird LOKAL in Home Assistant ausgeloest (zuverlaessig, auch
    # wenn die Verbindung zur RezeptKammer kurz weg ist) ----------------------------

    @callback
    def _schedule_timer(self, timer: dict[str, Any] | None) -> None:
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        ends = parse_utc((timer or {}).get("ends_at"))
        if not timer or not ends or ends <= dt_util.utcnow():
            return
        finished = dict(timer)

        @callback
        def _finish(_now: datetime) -> None:
            self._timer_unsub = None
            if self.data:
                self.data.active_timer = None
                self.async_set_updated_data(self.data)
            self._fire("timer_finished", finished)

        self._timer_unsub = async_track_point_in_utc_time(self.hass, _finish, ends)

    # --- Kochmodus: "Kocht gerade" endet mit cooking_finished oder nach COOKING_IDLE_MINUTES ohne
    # neues Ereignis (Tab einfach geschlossen) - ebenfalls lokal ausgeloest --------------------------

    @callback
    def _schedule_cooking_end(self, cooking: dict[str, Any] | None) -> None:
        if self._cooking_unsub:
            self._cooking_unsub()
            self._cooking_unsub = None
        ends = parse_utc((cooking or {}).get("expires_at"))
        if not cooking or not ends:
            return

        @callback
        def _end(_now: datetime) -> None:
            self._cooking_unsub = None
            if self.data and self.data.cooking:
                self.data.cooking = None
                self.async_set_updated_data(self.data)

        self._cooking_unsub = async_track_point_in_utc_time(self.hass, _end, ends)

    @callback
    def _cooking_activity(self, etype: str, data: dict[str, Any]) -> None:
        if not self.data:
            return
        if etype == "cooking_finished":
            self.data.cooking = None
            self._schedule_cooking_end(None)
            return
        cooking = self.data.cooking
        if etype == "cooking_started" or (etype == "cooking_step" and not cooking):
            cooking = {"recipe": data.get("recipe"), "recipe_url": data.get("recipe_url"),
                       "started_at": dt_util.utcnow().isoformat(), "total": data.get("total"),
                       "step": None, "step_text": None}
        if not cooking:
            return  # Timer/Ofen ohne Kochmodus
        if etype == "cooking_step":
            cooking.update(step=data.get("step"), total=data.get("total") or cooking.get("total"),
                           step_text=data.get("text"))
        ends = dt_util.utcnow()
        timer_end = parse_utc((self.data.active_timer or {}).get("ends_at"))
        if timer_end and timer_end > ends:
            ends = timer_end
        cooking["expires_at"] = (ends + timedelta(minutes=COOKING_IDLE_MINUTES)).isoformat()
        self.data.cooking = cooking
        self._schedule_cooking_end(cooking)

    @callback
    def _fire(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {k: v for k, v in data.items() if k != "type"}
        if self.data and self.data.account:
            payload["account"] = self.data.account  # wessen Kochmodus (mehrere Konten in einem Haushalt)
        self.hass.bus.async_fire(BUS_EVENT, {"type": event_type, **payload,
                                             "config_entry_id": self.config_entry.entry_id})
        async_dispatcher_send(self.hass, signal_event(self.config_entry.entry_id), event_type, payload)

    async def _async_handle(self, event: dict[str, Any]) -> None:
        etype, data = event.get("type"), event.get("data") or {}
        if etype == "shopping_list_changed":
            await self.async_refresh_list(data.get("list_id", "private"))
            return
        if etype == "timer_started":
            if self.data:
                self.data.active_timer = data
            self._schedule_timer(data)
        elif etype == "timer_cancelled":
            self._schedule_timer(None)
            if self.data:
                self.data.active_timer = None
        elif etype == "credits_changed":
            if self.data and self.data.credits is not None and isinstance(data.get("credits"), (int, float)):
                self.data.credits = data["credits"]
        self._cooking_activity(etype, data)
        if self.data:
            self.async_set_updated_data(self.data)
        self._fire(etype, data)

    async def async_listen(self) -> None:
        """Endlosschleife: Long-Polling auf /events, mit Wiederverbindung."""
        since: int | None = None
        backoff = 5
        while True:
            try:
                if since is None:
                    since = (await self.api.events(None))["last_event_id"]
                result = await self.api.events(since, wait=EVENT_WAIT_SECONDS)
                for event in result.get("events", []):
                    await self._async_handle(event)
                since = result.get("last_event_id", since)
                backoff = 5
            except RezeptKammerAuthError:
                self.config_entry.async_start_reauth(self.hass)
                return
            except RezeptKammerError as err:
                if not isinstance(err, RezeptKammerConnectionError):
                    _LOGGER.warning("RezeptKammer-Ereignisse: %s", err)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
                if since is not None:
                    # nach einer Pause verpasste Aenderungen nachholen
                    await self.async_request_refresh()

    @callback
    def async_shutdown_timer(self) -> None:
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None

    @callback
    def async_shutdown_cooking(self) -> None:
        self._schedule_cooking_end(None)

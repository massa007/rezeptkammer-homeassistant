"""Einrichtung: Konto per Code bestaetigen (ohne Abtippen eines Schluessels) oder
alternativ einen unter rezeptkammer.de/account erzeugten Zugangsschluessel eingeben."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RezeptKammerApi, RezeptKammerAuthError, RezeptKammerConnectionError, RezeptKammerError
from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RezeptKammerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url = DEFAULT_URL
        self._pairing: dict[str, Any] | None = None
        self._pair_task: asyncio.Task | None = None
        self._token: str | None = None

    def _api(self, token: str | None = None) -> RezeptKammerApi:
        return RezeptKammerApi(async_get_clientsession(self.hass), self._url, token)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Einstieg mit kurzer Erklaerung; eigene Server-Adresse (Test-Instanzen)
        # eingeklappt unter "Erweitert"
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({
                vol.Required("advanced"): section(
                    vol.Schema({vol.Required(CONF_URL, default=DEFAULT_URL): str}), {"collapsed": True}),
            }))
        url = (user_input.get("advanced") or {}).get(CONF_URL) or DEFAULT_URL
        self._url = url.strip().rstrip("/")
        return self.async_show_menu(step_id="method", menu_options=["pair", "token"])

    async def async_step_method(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="method", menu_options=["pair", "token"])

    # --- Kopplung per Code --------------------------------------------------------

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._pairing is None:
            try:
                self._pairing = await self._api().pair_start(self.hass.config.location_name or "Home Assistant")
            except RezeptKammerError:
                return self.async_abort(reason="cannot_connect")
        if self._pair_task is None:
            self._pair_task = self.hass.async_create_task(self._async_wait_for_approval())
        if not self._pair_task.done():
            return self.async_show_progress(
                step_id="pair", progress_action="wait_for_approval", progress_task=self._pair_task,
                description_placeholders={
                    "url": self._pairing["verification_url"], "code": self._pairing["user_code"],
                    "base_url": self._pairing["verification_url_base"],
                },
            )
        if self._token:
            return self.async_show_progress_done(next_step_id="finish")
        return self.async_show_progress_done(next_step_id="pair_failed")

    async def _async_wait_for_approval(self) -> None:
        assert self._pairing
        api = self._api()
        interval = max(2, int(self._pairing.get("interval", 3)))
        deadline = asyncio.get_running_loop().time() + int(self._pairing.get("expires_in", 900))
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(interval)
            try:
                status, data = await api.pair_poll(self._pairing["device_secret"])
            except RezeptKammerConnectionError:
                continue
            if status == "ok":
                self._token = data["token"]
                return
            if status == "expired":
                return

    async def async_step_pair_failed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_abort(reason="pairing_expired")

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_create(self._token or "")

    # --- Zugangsschluessel manuell ------------------------------------------------------

    async def async_step_token(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            try:
                await self._api(token).me()
            except RezeptKammerAuthError:
                errors["base"] = "invalid_auth"
            except RezeptKammerError:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_create(token)
        return self.async_show_form(step_id="token", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                                    errors=errors)

    async def _async_create(self, token: str) -> ConfigFlowResult:
        try:
            me = await self._api(token).me()
        except RezeptKammerAuthError:
            return self.async_abort(reason="invalid_auth")
        except RezeptKammerError:
            return self.async_abort(reason="cannot_connect")
        data = {CONF_URL: self._url, CONF_TOKEN: token}
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        await self.async_set_unique_id(f"{self._url}::{me['user_id']}")
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(title=f"RezeptKammer ({me['user']})", data=data)

    # --- Erneut verbinden (Schluessel widerrufen) -------------------------------------

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._url = entry_data.get(CONF_URL, DEFAULT_URL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return self.async_show_menu(step_id="method", menu_options=["pair", "token"])

"""Kleiner Client fuer die RezeptKammer-API (https://rezeptkammer.de/api/ha/v1).

Alle Verbindungen gehen von Home Assistant aus - funktioniert daher auch ohne
Cloud-Zugang, Portfreigabe oder VPN-Konfiguration auf Seiten der RezeptKammer.
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class RezeptKammerError(Exception):
    """Allgemeiner Fehler."""


class RezeptKammerAuthError(RezeptKammerError):
    """Zugangsschluessel ungueltig oder widerrufen."""


class RezeptKammerConnectionError(RezeptKammerError):
    """Server nicht erreichbar."""


class RezeptKammerApi:
    """Zugriff auf eine RezeptKammer-Instanz."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str | None = None) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._token = token

    async def _request(
        self, method: str, path: str, *, json: Any = None, params: dict | None = None,
        timeout: float = 20, auth: bool = True,
    ) -> tuple[int, Any]:
        headers = {"Accept": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method, f"{self.base_url}/api/ha/v1{path}", json=json, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 401:
                    raise RezeptKammerAuthError
                if resp.status >= 500 or resp.status == 429:
                    raise RezeptKammerConnectionError(f"HTTP {resp.status}")
                try:
                    data = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    data = None
                if resp.status >= 400 and resp.status not in (410,):
                    raise RezeptKammerError(f"HTTP {resp.status}: {data}")
                return resp.status, data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RezeptKammerConnectionError(str(err)) from err

    # Kopplung
    async def pair_start(self, name: str) -> dict:
        _, data = await self._request("POST", "/pair/start", json={"name": name}, auth=False)
        return data

    async def pair_poll(self, device_secret: str) -> tuple[str, dict]:
        """('pending'|'ok'|'expired', daten)."""
        status, data = await self._request("POST", "/pair/poll", json={"device_secret": device_secret}, auth=False)
        if status == 200:
            return "ok", data
        if status == 202:
            return "pending", data or {}
        return "expired", data or {}

    # Konto / Zustand
    async def me(self) -> dict:
        return (await self._request("GET", "/me"))[1]

    async def state(self) -> dict:
        return (await self._request("GET", "/state"))[1]

    async def revoke(self) -> None:
        await self._request("DELETE", "/token")

    # Einkaufslisten
    async def list_items(self, list_id: str) -> list[dict]:
        return (await self._request("GET", f"/lists/{list_id}/items"))[1]["items"]

    async def add_item(self, list_id: str, summary: str, note: str | None = None) -> None:
        await self._request("POST", f"/lists/{list_id}/items", json={"summary": summary, "note": note or ""})

    async def update_item(self, list_id: str, item_id: str, **fields: Any) -> None:
        await self._request("PATCH", f"/lists/{list_id}/items/{item_id}", json=fields)

    async def delete_item(self, list_id: str, item_id: str) -> None:
        await self._request("DELETE", f"/lists/{list_id}/items/{item_id}")

    # Ereignisse (Long-Polling)
    async def events(self, since: int | None, wait: int = 20) -> dict:
        params = {} if since is None else {"since": since, "wait": wait}
        return (await self._request("GET", "/events", params=params, timeout=wait + 20))[1]

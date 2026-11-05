"""Einkaufslisten (privat + jede gemeinsame Kammer) als To-do-Listen - per Assist
auch per Sprache befuellbar ("Fuege Milch zur Einkaufsliste hinzu")."""
from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RezeptKammerConfigEntry
from .api import RezeptKammerError
from .coordinator import RezeptKammerCoordinator
from .entity import RezeptKammerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RezeptKammerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_lists() -> None:
        new = [lid for lid in coordinator.data.lists if lid not in known]
        known.update(new)
        if new:
            async_add_entities(RezeptKammerTodoList(coordinator, lid) for lid in new)

    _add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_lists))


class RezeptKammerTodoList(RezeptKammerEntity, TodoListEntity):
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: RezeptKammerCoordinator, list_id: str) -> None:
        super().__init__(coordinator, f"list_{list_id}")
        self._list_id = list_id
        self._attr_name = coordinator.data.lists[list_id]["name"]

    @property
    def available(self) -> bool:
        return super().available and self._list_id in self.coordinator.data.lists

    @property
    def todo_items(self) -> list[TodoItem] | None:
        lst = self.coordinator.data.lists.get(self._list_id)
        if lst is None:
            return None
        return [
            TodoItem(
                uid=item["id"],
                summary=item["summary"] or item["name"],
                status=TodoItemStatus.COMPLETED if item["checked"] else TodoItemStatus.NEEDS_ACTION,
                description=item.get("note") or None,
            )
            for item in lst["items"]
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self._call(self.coordinator.api.add_item(self._list_id, item.summary or "", item.description))

    async def async_update_todo_item(self, item: TodoItem) -> None:
        fields = {"checked": item.status == TodoItemStatus.COMPLETED, "note": item.description or ""}
        current = next((i for i in self.coordinator.data.lists[self._list_id]["items"] if i["id"] == item.uid), None)
        if item.summary and (current is None or item.summary != current["summary"]):
            fields["summary"] = item.summary
        await self._call(self.coordinator.api.update_item(self._list_id, item.uid, **fields))

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self._call(self.coordinator.api.delete_item(self._list_id, uid), refresh=False)
        await self.coordinator.async_refresh_list(self._list_id)

    async def _call(self, coro, refresh: bool = True) -> None:
        try:
            await coro
        except RezeptKammerError as err:
            raise HomeAssistantError(f"RezeptKammer: {err}") from err
        if refresh:
            await self.coordinator.async_refresh_list(self._list_id)

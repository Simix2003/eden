from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WorldEvent:
    tick: int
    category: str
    severity: str
    title: str
    description: str
    entity_ids: list[int]
    lineage_ids: list[int]
    data: dict[str, float | int | str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "entity_ids": self.entity_ids,
            "lineage_ids": self.lineage_ids,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldEvent":
        return cls(
            tick=int(data["tick"]),
            category=str(data["category"]),
            severity=str(data["severity"]),
            title=str(data["title"]),
            description=str(data["description"]),
            entity_ids=[int(value) for value in data.get("entity_ids", [])],
            lineage_ids=[int(value) for value in data.get("lineage_ids", [])],
            data=dict(data.get("data", {})),
        )


class EventLog:
    def __init__(self, limit: int = 300) -> None:
        self.limit = limit
        self.events: list[WorldEvent] = []
        self._last_tick_by_key: dict[str, int] = {}

    def add(
        self,
        tick: int,
        category: str,
        severity: str,
        title: str,
        description: str,
        *,
        key: str | None = None,
        cooldown: int = 0,
        entity_ids: list[int] | None = None,
        lineage_ids: list[int] | None = None,
        data: dict[str, float | int | str] | None = None,
    ) -> bool:
        event_key = key or f"{category}:{title}"
        previous = self._last_tick_by_key.get(event_key)
        if previous is not None and tick - previous < cooldown:
            return False
        self._last_tick_by_key[event_key] = tick
        self.events.append(
            WorldEvent(
                tick=tick,
                category=category,
                severity=severity,
                title=title,
                description=description,
                entity_ids=entity_ids or [],
                lineage_ids=lineage_ids or [],
                data=data or {},
            )
        )
        if len(self.events) > self.limit:
            del self.events[: len(self.events) - self.limit]
        if len(self._last_tick_by_key) > self.limit * 3:
            cutoff = tick - 100_000
            self._last_tick_by_key = {key: value for key, value in self._last_tick_by_key.items() if value >= cutoff}
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "last_tick_by_key": self._last_tick_by_key,
            "limit": self.limit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventLog":
        result = cls(int(data.get("limit", 300)))
        result.events = [WorldEvent.from_dict(item) for item in data.get("events", [])][-result.limit :]
        result._last_tick_by_key = {str(key): int(value) for key, value in data.get("last_tick_by_key", {}).items()}
        return result


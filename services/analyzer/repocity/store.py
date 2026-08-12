"""In-process project store.

A single local user analyzing a checkout on their own disk does not need a database or a
task queue; when Phase 3 adds long-running agent work this grows an async job registry.
"""

from __future__ import annotations

from .schema import CityMap


class UnknownProject(KeyError):
    pass


class ProjectStore:
    def __init__(self) -> None:
        self._cities: dict[str, CityMap] = {}

    def put(self, city: CityMap) -> None:
        self._cities[city.project_id] = city

    def get(self, project_id: str) -> CityMap:
        try:
            return self._cities[project_id]
        except KeyError:
            raise UnknownProject(project_id) from None

    def ids(self) -> list[str]:
        return sorted(self._cities)

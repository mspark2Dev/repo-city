"""REST surface. Phase 1 covers analysis and retrieval; agent routes land in Phase 3."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..build import build_city
from ..schema import CityMap
from ..store import ProjectStore, UnknownProject

router = APIRouter(prefix="/api/v1")
store = ProjectStore()


class Wire(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AnalyzeRequest(Wire):
    path: str
    exclude: list[str] = Field(default_factory=list)


class AnalyzeResponse(Wire):
    project_id: str
    stats: dict


class FileDetail(Wire):
    id: str
    path: str
    lang: str
    metrics: dict
    source: str
    imports: list[str]
    imported_by: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    root = Path(request.path).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {request.path}")

    city = build_city(root, tuple(request.exclude))
    store.put(city)
    return AnalyzeResponse(project_id=city.project_id, stats=city.stats.model_dump(by_alias=True))


@router.get("/projects/{project_id}/citymap", response_model=CityMap)
def citymap(project_id: str) -> CityMap:
    try:
        return store.get(project_id)
    except UnknownProject:
        raise HTTPException(status_code=404, detail="unknown project") from None


@router.get("/projects/{project_id}/metrics/{node_id:path}", response_model=FileDetail)
def metrics(project_id: str, node_id: str) -> FileDetail:
    """node_id is `f:<repo-relative-path>`; the `:path` converter keeps its slashes."""
    try:
        city = store.get(project_id)
    except UnknownProject:
        raise HTTPException(status_code=404, detail="unknown project") from None

    building = next((b for b in city.buildings if b.id == node_id), None)
    if building is None:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")

    source_path = Path(city.root) / building.path
    try:
        source = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=410, detail=f"source unreadable: {exc}") from None

    return FileDetail(
        id=building.id,
        path=building.path,
        lang=building.lang,
        metrics=building.metrics.model_dump(by_alias=True),
        source=source,
        imports=sorted(link.target for link in city.links if link.source == building.id),
        imported_by=sorted(link.source for link in city.links if link.target == building.id),
    )


def project_id_for(root: Path) -> str:
    return hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]

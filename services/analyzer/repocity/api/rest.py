"""REST surface. Phase 1 covers analysis and retrieval; agent routes land in Phase 3."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..agent import LLMAdapter, TaskRegistry, run_refactor
from ..agent.context import build_context
from ..agent.patch import apply_change, revert
from ..build import build_city
from ..delta import diff_cities
from ..jobs import JobRegistry
from ..schema import CityMap
from ..store import ProjectStore, UnknownProject
from .ws import hub

router = APIRouter(prefix="/api/v1")
store = ProjectStore()
tasks = TaskRegistry()
jobs = JobRegistry()
adapter = LLMAdapter()


class Wire(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AnalyzeRequest(Wire):
    path: str
    exclude: list[str] = Field(default_factory=list)


class AnalyzeResponse(Wire):
    job_id: str
    project_id: str


class FileDetail(Wire):
    id: str
    path: str
    lang: str
    metrics: dict
    source: str
    imports: list[str]
    imported_by: list[str]


@router.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Start an analysis and return immediately.

    The client subscribes to the project channel with the id returned here, so it sees
    progress rather than a frozen window while a large repository is parsed.
    """
    root = Path(request.path).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {request.path}")

    project_id = project_id_for(root)
    job = jobs.create(project_id, str(root))
    asyncio.create_task(_run_analysis(job, root, tuple(request.exclude)))
    return AnalyzeResponse(job_id=job.id, project_id=project_id)


async def _run_analysis(job, root: Path, excludes: tuple[str, ...]) -> None:
    loop = asyncio.get_running_loop()

    def on_progress(done: int, total: int) -> None:
        job.done, job.total = done, total
        # The parse runs in a worker thread; hop back to the loop to reach the socket.
        asyncio.run_coroutine_threadsafe(
            hub.broadcast(
                job.project_id,
                {"type": "analysis.progress", "jobId": job.id, "done": done, "total": total},
            ),
            loop,
        )

    try:
        city = await asyncio.to_thread(build_city, root, excludes, on_progress=on_progress)
    except OSError as exc:
        job.status, job.error = "error", str(exc)
        await hub.broadcast(
            job.project_id, {"type": "analysis.error", "jobId": job.id, "message": str(exc)}
        )
        return

    previous = store.peek(city.project_id)
    store.put(city)
    job.status = "done"
    await hub.broadcast(
        job.project_id,
        {"type": "analysis.done", "jobId": job.id, "projectId": city.project_id},
    )
    if previous is not None:
        await hub.broadcast(
            job.project_id, {"type": "citymap.delta", **diff_cities(previous, city)}
        )


@router.get("/analyze/{job_id}")
def analysis_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.as_dict()


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


class RefactorRequest(Wire):
    project_id: str
    node_id: str
    instruction: str


class PrewarmRequest(Wire):
    project_id: str
    node_id: str


class ApplyRequest(Wire):
    task_id: str


class RevertRequest(Wire):
    snapshot_id: str


def _city_and_building(project_id: str, node_id: str):
    try:
        city = store.get(project_id)
    except UnknownProject:
        raise HTTPException(status_code=404, detail="unknown project") from None
    building = next((b for b in city.buildings if b.id == node_id), None)
    if building is None:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    return city, building


@router.get("/agent/health")
async def agent_health() -> dict:
    health = await adapter.health()
    return {"ok": health.ok, "model": health.model, "detail": health.detail}


@router.post("/agent/prewarm", status_code=202)
async def prewarm(request: PrewarmRequest, background: BackgroundTasks) -> dict:
    """Warm the cacheable prefix while the user is still typing their command.

    The prefix is the file and its dependencies, which is the expensive part of the
    prefill; sending it early turns the first command from a cold request into a warm one.
    """
    city, building = _city_and_building(request.project_id, request.node_id)
    try:
        context = build_context(city, building, "")
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="source file is gone") from None
    background.add_task(adapter.prewarm, context.prefix)
    return {"warming": True}


@router.post("/agent/refactor", status_code=202)
async def refactor(request: RefactorRequest) -> dict:
    city, building = _city_and_building(request.project_id, request.node_id)
    if not request.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is empty")

    task = tasks.create(request.project_id, request.node_id, request.instruction)
    emit = hub.emitter(request.project_id)
    tasks.spawn(task, run_refactor(task, city, building, adapter, emit))
    return {"taskId": task.id}


@router.get("/agent/tasks/{task_id}")
def task_status(task_id: str) -> dict:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return task.as_dict()


@router.post("/agent/apply")
async def apply(request: ApplyRequest) -> dict:
    task = tasks.get(request.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="unknown task")
    if task.status != "ready" or task.proposal is None:
        raise HTTPException(status_code=409, detail=f"task is {task.status}, not ready")

    city, building = _city_and_building(task.project_id, task.node_id)
    applied = apply_change(task.project_id, task.id, Path(city.root), building.path, task.proposal)

    refreshed = await asyncio.to_thread(build_city, Path(city.root))
    store.put(refreshed)
    delta = diff_cities(city, refreshed)
    await hub.broadcast(
        task.project_id,
        {"type": "citymap.delta", "taskId": task.id, "reason": "applied", **delta},
    )
    return {
        "applied": applied.paths,
        "snapshotId": applied.snapshot_id,
        "stats": refreshed.stats.model_dump(by_alias=True),
        "delta": delta,
    }


@router.post("/agent/revert")
async def revert_snapshot(request: RevertRequest) -> dict:
    try:
        restored = revert(request.snapshot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="unknown snapshot") from None

    project_id = request.snapshot_id.split("/")[0]
    try:
        city = store.get(project_id)
    except UnknownProject:
        return {"reverted": restored}

    refreshed = await asyncio.to_thread(build_city, Path(city.root))
    store.put(refreshed)
    delta = diff_cities(city, refreshed)
    await hub.broadcast(project_id, {"type": "citymap.delta", "reason": "reverted", **delta})
    return {
        "reverted": restored,
        "stats": refreshed.stats.model_dump(by_alias=True),
        "delta": delta,
    }


def project_id_for(root: Path) -> str:
    return hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]

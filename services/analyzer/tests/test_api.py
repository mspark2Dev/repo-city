"""API surface, including the async analysis flow the canvas depends on."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repocity.app import app

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "sample-project"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path / "state"))
    with TestClient(app) as test_client:
        yield test_client


def _analyze(client: TestClient) -> str:
    response = client.post("/api/v1/analyze", json={"path": str(FIXTURE)})
    assert response.status_code == 202
    job_id = response.json()["jobId"]

    for _ in range(200):
        status = client.get(f"/api/v1/analyze/{job_id}").json()
        if status["status"] != "running":
            break
        time.sleep(0.05)
    assert status["status"] == "done", status
    return response.json()["projectId"]


def test_analysis_reports_a_job_then_completes(client):
    project_id = _analyze(client)
    city = client.get(f"/api/v1/projects/{project_id}/citymap").json()
    assert city["stats"]["files"] == len(city["buildings"]) == 29


def test_analyzing_a_missing_path_is_rejected(client):
    assert client.post("/api/v1/analyze", json={"path": "/no/such/dir"}).status_code == 400


def test_unknown_job_and_project_are_404(client):
    assert client.get("/api/v1/analyze/nope").status_code == 404
    assert client.get("/api/v1/projects/deadbeef/citymap").status_code == 404


def test_metrics_include_source_and_both_link_directions(client):
    project_id = _analyze(client)
    detail = client.get(
        f"/api/v1/projects/{project_id}/metrics/f:orderbook/core/settlement.py"
    ).json()
    assert detail["metrics"]["maxCC"] == 29
    assert "def settle" in detail["source"]
    assert "f:orderbook/core/models.py" in detail["imports"]
    assert "f:orderbook/service.py" in detail["importedBy"]


def test_unknown_node_is_404(client):
    project_id = _analyze(client)
    assert client.get(f"/api/v1/projects/{project_id}/metrics/f:nope.py").status_code == 404


def test_applying_an_unfinished_task_is_refused(client):
    _analyze(client)
    assert client.post("/api/v1/agent/apply", json={"taskId": "nope"}).status_code == 404


def test_refactoring_with_an_empty_instruction_is_refused(client):
    project_id = _analyze(client)
    response = client.post(
        "/api/v1/agent/refactor",
        json={
            "projectId": project_id,
            "nodeId": "f:orderbook/core/settlement.py",
            "instruction": "   ",
        },
    )
    assert response.status_code == 400

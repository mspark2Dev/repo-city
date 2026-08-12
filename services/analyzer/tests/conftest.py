from pathlib import Path

import pytest

from repocity.build import build_city
from repocity.schema import CityMap

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "sample-project"


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    assert FIXTURE.is_dir(), f"fixture project missing at {FIXTURE}"
    return FIXTURE


@pytest.fixture(scope="session")
def city(fixture_root: Path) -> CityMap:
    return build_city(fixture_root)

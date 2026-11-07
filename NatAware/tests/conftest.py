import pytest

from nataware.config import settings
from nataware.data.store import Store, set_store


@pytest.fixture(autouse=True)
def store(tmp_path):
    """Every test gets a fresh store seeded from data/seed, persisted to a temp file."""
    from nataware.worker.tasks import bootstrap

    s = Store(settings.seed_dir, tmp_path / "state.json")
    set_store(s)
    bootstrap()
    yield s
    set_store(None)

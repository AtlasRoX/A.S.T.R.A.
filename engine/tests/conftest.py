import os
import tempfile
from pathlib import Path

import pytest

# Keep the module-level app away from the real demo database.
os.environ.setdefault("ASTRA_DB", str(Path(tempfile.mkdtemp()) / "import.db"))
# No background telemetry in tests: readings must only come from the tests themselves.
os.environ.setdefault("ASTRA_LIVE_SIM", "off")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(str(tmp_path / "astra.db")))

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# DB URL configured before importing the application modules.
_tempdir=tempfile.TemporaryDirectory()
os.environ['MODELAUDIT_DATABASE_URL'] = 'sqlite:///' + str(Path(_tempdir.name)/'tests.sqlite3')
from app.main import app  # noqa: E402
from app.db import Base, engine  # noqa: E402

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c

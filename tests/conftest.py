import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

TEST_URL = os.environ["TEST_DATABASE_URL"]
# Safety net: refuse to run if this doesn't look like a test database
assert TEST_URL.rsplit("/", 1)[-1].endswith("_test"), "TEST_DATABASE_URL must end in _test"

# Must happen BEFORE importing the app, because database.py reads this on import
os.environ["DATABASE_URL"] = TEST_URL

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

SCHEMA_FILE = Path(__file__).parent.parent / "sql" / "schema.sql"


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Once per test run: rebuild all tables from schema.sql."""
    with engine.begin() as conn:
        conn.execute(
            text("DROP TABLE IF EXISTS resource_dependencies, resources, scans CASCADE")
        )
        conn.execute(text(SCHEMA_FILE.read_text()))


@pytest.fixture(autouse=True)
def clean_tables():
    """Before every test: empty the tables so tests don't affect each other."""
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE resource_dependencies, resources, scans RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def client():
    return TestClient(app)
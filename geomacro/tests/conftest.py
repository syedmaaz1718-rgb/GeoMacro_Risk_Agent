import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["GEOMACRO_NO_SCHEDULER"] = "1"
os.environ["LLM_PROVIDER"] = "none"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
import pytest
from app.db import Base, engine, init_db


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

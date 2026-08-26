import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_zalo_app.db"

from app.database.db import Base, engine
from app.database.init_db import init_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)

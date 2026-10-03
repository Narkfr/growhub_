import sys
import types
from unittest.mock import MagicMock

import pytest

# --- Fake third-party modules ------------------------------------------------
_psycopg2 = types.ModuleType("psycopg2")
_psycopg2.connect = MagicMock()
_psycopg2.DatabaseError = type("DatabaseError", (Exception,), {})
sys.modules["psycopg2"] = _psycopg2

_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _dotenv

from gateway import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_conn():
    _psycopg2.connect.reset_mock(return_value=True, side_effect=True)
    yield


def test_init_database_executes_schema():
    conn = MagicMock()
    cur = conn.cursor.return_value
    _psycopg2.connect.return_value = conn

    init_db.init_database()

    _psycopg2.connect.assert_called_once()
    assert cur.execute.call_count == 3
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_init_database_connect_error_does_not_raise():
    _psycopg2.connect.side_effect = Exception("boom")
    init_db.init_database()
    _psycopg2.connect.assert_called_once()

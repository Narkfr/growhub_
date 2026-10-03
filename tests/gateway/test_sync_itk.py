import json
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

from gateway import sync_itk  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_conn():
    _psycopg2.connect.reset_mock(return_value=True)
    yield


def test_sync_itks_missing_dir_returns_early(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no itk/ directory here
    sync_itk.sync_itks()
    _psycopg2.connect.assert_not_called()


def test_sync_itks_upserts_itk_and_phases(tmp_path, monkeypatch):
    itk_dir = tmp_path / "itk"
    itk_dir.mkdir()
    (itk_dir / "example.json").write_text(
        json.dumps(
            {
                "name": "Example",
                "phases": [
                    {
                        "name": "Germination",
                        "order": 0,
                        "duration": 3,
                        "settings": {"moisture_target": 60},
                    },
                    {
                        "name": "Croissance",
                        "order": 1,
                        "duration": 7,
                        "settings": {"moisture_target": 50},
                    },
                ],
            }
        )
    )
    monkeypatch.chdir(tmp_path)

    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchone.return_value = [1]
    _psycopg2.connect.return_value = conn

    sync_itk.sync_itks()

    _psycopg2.connect.assert_called_once()
    conn.commit.assert_called_once()
    conn.close.assert_called_once()
    # 1 ITK upsert + 2 phase upserts
    assert cur.execute.call_count == 3


def test_sync_itks_rolls_back_on_error(tmp_path, monkeypatch):
    itk_dir = tmp_path / "itk"
    itk_dir.mkdir()
    (itk_dir / "example.json").write_text(json.dumps({"name": "Example", "phases": []}))
    monkeypatch.chdir(tmp_path)

    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.execute.side_effect = Exception("boom")
    _psycopg2.connect.return_value = conn

    sync_itk.sync_itks()  # must not raise

    conn.rollback.assert_called_once()
    conn.close.assert_called_once()

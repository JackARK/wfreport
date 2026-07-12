from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core import history

client = TestClient(app)


def test_upload_and_preview(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("WFREPORT_DB_PATH", db_path)
    history.init_db(db_path)

    with open("resource/本周.xlsx", "rb") as f:
        r = client.post(
            "/api/upload",
            files={"file": ("本周.xlsx", f,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200
    wid = r.json()["week_id"]
    assert wid.startswith("2026-W")

    rp = client.post(f"/api/preview/{wid}")
    assert rp.status_code == 200
    data = rp.json()
    assert "overview" in data and "figures" in data

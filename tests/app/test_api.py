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


def test_download_rejects_traversal(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("WFREPORT_DB_PATH", db_path)
    history.init_db(db_path)

    # week_id traversal via encoded ".." -> must not escape output root
    r = client.get("/api/download/%2E%2E/README.md")
    assert r.status_code == 404

    # name being literal ".." -> reject
    r = client.get("/api/download/2026-W01/%2E%2E")
    assert r.status_code == 404

    # encoded slashes in name attempting to climb out -> reject
    r = client.get("/api/download/2026-W01/%2E%2E%2F%2E%2E%2FREADME.md")
    assert r.status_code == 404

    # a valid-shaped path whose file does not exist -> 404
    r = client.get("/api/download/2026-W99/missing.xlsx")
    assert r.status_code == 404

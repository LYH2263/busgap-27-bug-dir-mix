import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Line, Trip
from app.services.seed import seed_if_empty

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    seed_if_empty(db)
    db.close()
    return TestClient(app)


def _trip_dirs(client):
    return {t["trip_no"]: t["direction"] for t in client.get("/api/trips").json()}


def test_seed_b12_has_both_directions(client):
    dirs = _trip_dirs(client)
    assert set(dirs.values()) == {"up", "down"}


def test_run_excludes_cross_direction_pairs(client):
    events = client.post("/api/reports/run?line_id=1").json()["events"]
    dirs = _trip_dirs(client)
    assert events, "种子数据应产生同方向间隔事件"
    for e in events:
        assert dirs[e["earlier_trip"]] == dirs[e["later_trip"]] == e["direction"]
    # 同向相邻仍按现网阈值判定：串车与大间隔都应出现
    statuses = {e["status"] for e in events}
    assert "bunching" in statuses
    assert "large_gap" in statuses
    # 异向相邻（市民中心 T01→T02 仅 1 分钟等）不再出现在报告事件里
    pairs = {(e["earlier_trip"], e["later_trip"]) for e in events}
    for cross in [("T01", "T02"), ("T02", "T03"), ("T03", "T04"), ("T04", "T05"), ("T05", "T06")]:
        assert cross not in pairs
    assert ("T01", "T03") in pairs
    assert ("T02", "T04") in pairs


def test_timeline_direction_filter(client):
    all_marks = client.get("/api/reports/timeline?line_id=1").json()["marks"]
    assert len(all_marks) == 6
    up = client.get("/api/reports/timeline?line_id=1&direction=up").json()["marks"]
    down = client.get("/api/reports/timeline?line_id=1&direction=down").json()["marks"]
    assert {m["trip_no"] for m in up} == {"T01", "T03", "T05"}
    assert all(m["direction"] == "up" for m in up)
    assert {m["trip_no"] for m in down} == {"T02", "T04", "T06"}
    assert all(m["direction"] == "down" for m in down)
    assert client.get("/api/reports/timeline?line_id=1&direction=sideways").status_code == 422


def test_patch_trip_direction_persists(client):
    trips = client.get("/api/trips").json()
    t01 = next(t for t in trips if t["trip_no"] == "T01")
    assert t01["direction"] == "up"
    r = client.patch(f"/api/trips/{t01['id']}", json={"direction": "down"})
    assert r.status_code == 200
    assert r.json()["direction"] == "down"
    # 离开再进来仍在：重新 GET 仍为 down
    trips2 = client.get("/api/trips").json()
    assert next(t for t in trips2 if t["trip_no"] == "T01")["direction"] == "down"
    # 清除班次方向后回到跟随线路（上行）
    r = client.patch(f"/api/trips/{t01['id']}", json={"direction": None})
    assert r.json()["direction"] == "up"
    assert client.patch(f"/api/trips/{t01['id']}", json={"direction": "x"}).status_code == 422
    assert client.patch("/api/trips/9999", json={"direction": "up"}).status_code == 404


def test_patch_line_direction_persists(client):
    lines = client.get("/api/lines").json()
    line_id = lines[0]["id"]
    assert lines[0]["direction"] == "up"
    r = client.patch(f"/api/lines/{line_id}", json={"direction": "down"})
    assert r.status_code == 200 and r.json()["direction"] == "down"
    assert client.get("/api/lines").json()[0]["direction"] == "down"
    assert client.patch(f"/api/lines/{line_id}", json={"direction": "left"}).status_code == 422
    assert client.patch("/api/lines/9999", json={"direction": "up"}).status_code == 404


def test_trip_inherits_line_direction(client):
    trips = client.get("/api/trips").json()
    t01 = next(t for t in trips if t["trip_no"] == "T01")
    client.patch(f"/api/trips/{t01['id']}", json={"direction": None})
    client.patch("/api/lines/1", json={"direction": "down"})
    t01_after = next(t for t in client.get("/api/trips").json() if t["trip_no"] == "T01")
    assert t01_after["own_direction"] is None
    assert t01_after["direction"] == "down"


def test_unmarked_trip_and_line_default_up(client):
    # 历史数据：班次与线路均未标方向 → 一律按上行
    db = TestSession()
    line = db.query(Line).one()
    line.direction = None
    for t in db.query(Trip).all():
        t.direction = None
    db.commit()
    db.close()
    trips = client.get("/api/trips").json()
    assert all(t["direction"] == "up" for t in trips)
    events = client.post("/api/reports/run?line_id=1").json()["events"]
    assert events
    assert all(e["direction"] == "up" for e in events)


def test_direction_change_affects_detection(client):
    trips = client.get("/api/trips").json()
    t03 = next(t for t in trips if t["trip_no"] == "T03")
    client.patch(f"/api/trips/{t03['id']}", json={"direction": "down"})
    events = client.post("/api/reports/run?line_id=1").json()["events"]
    pairs = {(e["earlier_trip"], e["later_trip"]) for e in events}
    assert ("T01", "T03") not in pairs  # 改向后不再与上行相邻判定
    assert ("T02", "T03") in pairs      # 改与下行同向相邻

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Arrival, BunchReport, Line, Trip
from app.services.bunch_engine import detect_bunching, events_to_dicts, normalize_direction
from app.services.scope_helpers import flatten_marks, stamp_status

router = APIRouter(prefix="/reports", tags=["reports"])


def _trip_maps(trips: list[Trip], line_direction: str | None) -> tuple[dict[int, str], dict[int, str]]:
    trip_no_map = {t.id: t.trip_no for t in trips}
    # 班次自身方向优先，未标才跟随线路，再未标按上行兼容
    trip_dir_map = {t.id: normalize_direction(t.direction or line_direction) for t in trips}
    return trip_no_map, trip_dir_map


def _participating_arrivals(db: Session, line: Line, stop_name: str | None = None,
                            direction: str | None = None) -> list[dict]:
    """报告检测与时间轴共用同一套参与班次：同一处解析方向、同一处筛选。"""
    trips = db.scalars(select(Trip).where(Trip.line_id == line.id)).all()
    trip_no_map, trip_dir_map = _trip_maps(trips, line.direction)
    arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(list(trip_no_map.keys())))).all()
    payload = []
    for a in arrivals:
        if stop_name is not None and a.stop_name != stop_name:
            continue
        trip_direction = trip_dir_map[a.trip_id]
        if direction is not None and trip_direction != direction:
            continue
        payload.append({"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id],
                        "direction": trip_direction, "actual_arrive": a.actual_arrive})
    return payload


@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]


@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "线路不存在")
    payload = _participating_arrivals(db, line, stop_name=stop_name)
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    data = events_to_dicts(events)
    data = [{**e, 'status': stamp_status(e.get('status', 'normal'))} for e in data]
    report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                         summary_json=json.dumps(data, ensure_ascii=False))
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "events": data}


@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    result = run_detection(line_id=line_id, stop_name=None, db=db)
    return {"line_id": line_id, "suggestions": [e for e in result["events"] if e["status"] != "normal"]}


@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", direction: Literal["up", "down"] | None = None,
             db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "线路不存在")
    # 与报告检测同源：方向过滤在参与集解析阶段完成，轴上只留该方向真正参与的班次
    payload = _participating_arrivals(db, line, stop_name=stop_name, direction=direction)
    arrivals = sorted(payload, key=lambda a: a["actual_arrive"])
    if not arrivals:
        return {"stop_name": stop_name, "direction": direction, "marks": []}
    t0 = arrivals[0]["actual_arrive"]
    span = max((arrivals[-1]["actual_arrive"] - t0).total_seconds(), 1)
    marks = [{"trip_no": a["trip_no"], "direction": a["direction"],
              "actual_arrive": a["actual_arrive"].isoformat(),
              "pct": round((a["actual_arrive"] - t0).total_seconds() / span * 100, 2)} for a in arrivals]
    return {"stop_name": stop_name, "direction": direction, "marks": flatten_marks(marks)}

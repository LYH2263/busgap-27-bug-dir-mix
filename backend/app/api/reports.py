import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Arrival, BunchReport, Line, Trip
from app.services.bunch_engine import detect_bunching, events_to_dicts, normalize_direction
from app.services.scope_helpers import prefer_raw_arrivals, flatten_marks, stamp_status

router = APIRouter(prefix="/reports", tags=["reports"])


def _trip_maps(trips: list[Trip], line_direction: str | None) -> tuple[dict[int, str], dict[int, str]]:
    trip_no_map = {t.id: t.trip_no for t in trips}
    # 班次自身方向优先；未标才跟随线路，再缺省按上行兼容
    trip_dir_map = {t.id: normalize_direction(t.direction or line_direction) for t in trips}
    return trip_no_map, trip_dir_map


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
    trips = db.scalars(select(Trip).where(Trip.line_id == line_id)).all()
    trip_ids = [t.id for t in trips]
    trip_no_map, trip_dir_map = _trip_maps(trips, line.direction)
    arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(trip_ids))).all()
    payload = [{"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id],
                "direction": trip_dir_map[a.trip_id], "actual_arrive": a.actual_arrive}
               for a in arrivals if stop_name is None or a.stop_name == stop_name]
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
    line_direction = line.direction if line else None
    trips = db.scalars(select(Trip).where(Trip.line_id == line_id)).all()
    trip_ids = [t.id for t in trips]
    trip_no_map, trip_dir_map = _trip_maps(trips, line_direction)
    arrivals = sorted(db.scalars(select(Arrival).where(Arrival.trip_id.in_(trip_ids),
                                                       Arrival.stop_name == stop_name)).all(),
                      key=lambda a: a.actual_arrive)
    if not arrivals:
        return {"stop_name": stop_name, "direction": direction, "marks": []}
    # 位置锚点取该站全部到站，切换方向时点的相对位置不漂移
    t0 = arrivals[0].actual_arrive
    span = max((arrivals[-1].actual_arrive - t0).total_seconds(), 1)
    # 与检测同一套参与班次：按方向过滤时只保留该方向班次的到站
    if direction is not None:
        arrivals = [a for a in arrivals if trip_dir_map[a.trip_id] == direction]
    marks = [{"trip_no": trip_no_map[a.trip_id], "direction": trip_dir_map[a.trip_id],
              "actual_arrive": a.actual_arrive.isoformat(),
              "pct": round((a.actual_arrive - t0).total_seconds() / span * 100, 2)} for a in arrivals]
    return {"stop_name": stop_name, "direction": direction, "marks": flatten_marks(marks)}

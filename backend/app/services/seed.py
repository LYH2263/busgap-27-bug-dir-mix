from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Arrival, Line, Trip

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Line)) or 0) > 0:
        return
    base = datetime(2026, 9, 17, 7, 0, 0)
    line = Line(code="B12", name="城东环线", planned_headway_min=8.0, bunch_threshold=3.0,
                large_threshold=15.0, direction="up")
    db.add(line); db.flush()
    # 双向班次：上行 T01/T03/T05，下行 T02/T04/T06。
    # 同一站两方向到站交错（异向相邻仅 1 分钟），同方向相邻 2 分钟（串车）与 18 分钟（大间隔）。
    specs = [
        # trip_no, vehicle, direction, planned_offset, actual_offset
        ("T01", "粤A1001", "up",   0,  0),
        ("T02", "粤A1002", "down", 0,  1),
        ("T03", "粤A1003", "up",   8,  2),
        ("T04", "粤A1004", "down", 8,  3),
        ("T05", "粤A1005", "up",  24, 20),
        ("T06", "粤A1006", "down",24, 21),
    ]
    stops = ["起点站", "市民中心", "火车站", "终点站"]
    for trip_no, vehicle, direction, planned_offset, actual_offset in specs:
        trip = Trip(line_id=line.id, trip_no=trip_no, planned_depart=base + timedelta(minutes=planned_offset),
                    vehicle_no=vehicle, direction=direction)
        db.add(trip); db.flush()
        for seq, stop in enumerate(stops):
            arrive = base + timedelta(minutes=actual_offset + seq * 6)
            db.add(Arrival(trip_id=trip.id, stop_name=stop, stop_seq=seq, actual_arrive=arrive))
    db.commit()

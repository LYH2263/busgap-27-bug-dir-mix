from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import Trip
from app.services.bunch_engine import normalize_direction

router = APIRouter(prefix="/trips", tags=["trips"])


class TripDirectionUpdate(BaseModel):
    # None 表示清除班次方向，回到跟随线路（未标按上行兼容）
    direction: Literal["up", "down"] | None


def effective_direction(trip: Trip) -> str:
    # 班次自身方向优先；未标才跟随线路；都未标按上行兼容
    line_dir = trip.line.direction if trip.line else None
    return normalize_direction(trip.direction or line_dir)


def trip_to_dict(r: Trip) -> dict:
    return {"id": r.id, "line_id": r.line_id, "trip_no": r.trip_no,
            "planned_depart": r.planned_depart.isoformat(), "vehicle_no": r.vehicle_no,
            "direction": effective_direction(r), "own_direction": r.direction}


@router.get("")
def list_trips(line_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Trip).options(joinedload(Trip.line)).order_by(Trip.planned_depart, Trip.id)
    if line_id is not None:
        q = q.where(Trip.line_id == line_id)
    return [trip_to_dict(r) for r in db.scalars(q).all()]


@router.patch("/{trip_id}")
def update_trip_direction(trip_id: int, body: TripDirectionUpdate, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(404, "班次不存在")
    trip.direction = body.direction
    db.commit()
    db.refresh(trip)
    return trip_to_dict(trip)

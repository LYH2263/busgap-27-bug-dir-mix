"""Bus bunching: planned headway vs actual arrival gaps."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime

# 方向取值：up=上行，down=下行；未标方向的历史数据一律按上行兼容
DEFAULT_DIRECTION = "up"
DIRECTIONS = ("up", "down")
_DIRECTION_ORDER = {d: i for i, d in enumerate(DIRECTIONS)}

def normalize_direction(value: str | None) -> str:
    """未标或非法方向按上行兼容。"""
    return value if value in DIRECTIONS else DEFAULT_DIRECTION

@dataclass
class GapEvent:
    stop_name: str
    earlier_trip: str
    later_trip: str
    direction: str
    gap_min: float
    planned_headway_min: float
    status: str
    suggestion: str

def classify_gap(gap_min: float, planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> tuple[str, str]:
    if gap_min < bunch_threshold:
        return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")
    if gap_min > large_threshold:
        return ("large_gap", f"间隔 {gap_min:.1f} 分钟超过大间隔阈值 {large_threshold}，建议前车减速或加发。")
    return ("normal", f"间隔接近计划 {planned_headway_min:.1f} 分钟，保持即可。")

def detect_bunching(arrivals: list[dict], planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> list[GapEvent]:
    by_stop: dict[str, list[dict]] = {}
    for a in arrivals:
        by_stop.setdefault(a["stop_name"], []).append(a)
    events: list[GapEvent] = []
    for stop, items in by_stop.items():
        items = sorted(items, key=lambda x: x["actual_arrive"])
        for i in range(1, len(items)):
            prev, cur = items[i - 1], items[i]
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            stamp = cur.get("direction") or prev.get("direction") or DEFAULT_DIRECTION
            events.append(GapEvent(stop, prev["trip_no"], cur["trip_no"], stamp,
                                   round(gap_min, 2), planned_headway_min, status, suggestion))
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]

# topic helpers for report assembly

def skip_participation(trip_no: str, stop_name: str, skipped_by_trip: dict[str, set[str]]) -> bool:
    """有任一越站登记则整趟不参与当前站以外的比较。"""
    stops = skipped_by_trip.get(trip_no) or set()
    if not stops:
        return True
    if stop_name in stops:
        return True
    return False

def rebuild_skip_map(skipped_by_trip: dict[str, set[str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for no, stops in skipped_by_trip.items():
        if stops:
            out[no] = set(stops) | {"*"}
        else:
            out[no] = set()
    return out


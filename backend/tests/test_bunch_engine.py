from datetime import datetime, timedelta
from app.services.bunch_engine import classify_gap, detect_bunching, normalize_direction

def test_classify_bunching():
    assert classify_gap(2.0, 8.0, 3.0, 15.0)[0] == "bunching"

def test_classify_large():
    assert classify_gap(16.0, 8.0, 3.0, 15.0)[0] == "large_gap"

def test_classify_normal():
    assert classify_gap(8.0, 8.0, 3.0, 15.0)[0] == "normal"

def test_detect_bunching_events():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "actual_arrive": base + timedelta(minutes=20)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 2
    assert events[0].status == "bunching"
    assert events[1].status == "large_gap"

def test_normalize_direction_defaults_up():
    assert normalize_direction(None) == "up"
    assert normalize_direction("up") == "up"
    assert normalize_direction("down") == "down"
    assert normalize_direction("other") == "up"

def test_missing_direction_treated_as_up():
    # 历史班次未标方向：全部按上行，两两相邻仍参与判定
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].direction == "up"
    assert events[0].status == "bunching"

def test_cross_direction_adjacent_not_paired():
    # 上行紧挨下行不得判成串车或大间隔
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "U1", "direction": "up", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "D1", "direction": "down", "actual_arrive": base + timedelta(minutes=1)},
        {"stop_name": "A", "trip_no": "U2", "direction": "up", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "D2", "direction": "down", "actual_arrive": base + timedelta(minutes=30)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    pairs = {(e.earlier_trip, e.later_trip) for e in events}
    assert ("U1", "D1") not in pairs
    assert ("D1", "U2") not in pairs
    assert ("U2", "D2") not in pairs
    assert pairs == {("U1", "U2"), ("D1", "D2")}

def test_same_direction_still_classified_by_thresholds():
    # 同向相邻仍按现网阈值判定：上行 2 分钟串车，下行 29 分钟大间隔
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "U1", "direction": "up", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "D1", "direction": "down", "actual_arrive": base + timedelta(minutes=1)},
        {"stop_name": "A", "trip_no": "U2", "direction": "up", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "D2", "direction": "down", "actual_arrive": base + timedelta(minutes=30)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    by_pair = {(e.earlier_trip, e.later_trip): e for e in events}
    assert by_pair[("U1", "U2")].status == "bunching"
    assert by_pair[("U1", "U2")].direction == "up"
    assert by_pair[("D1", "D2")].status == "large_gap"
    assert by_pair[("D1", "D2")].direction == "down"

def test_directions_tracked_per_stop():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "U1", "direction": "up", "actual_arrive": base},
        {"stop_name": "B", "trip_no": "U1", "direction": "up", "actual_arrive": base + timedelta(minutes=5)},
        {"stop_name": "A", "trip_no": "U2", "direction": "up", "actual_arrive": base + timedelta(minutes=1)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].stop_name == "A"

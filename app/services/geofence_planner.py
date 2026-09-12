import math
from typing import List, Dict, Any, Tuple, Optional

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_point_in_polygon(lat: float, lon: float, polygon: List[List[float]]) -> bool:
    """
    Ray casting algorithm to determine if a point (lat, lon) is inside a polygon.
    polygon is expected as [[lat, lon], ...]
    """
    if not polygon or len(polygon) < 3:
        return False

    inside = False
    n = len(polygon)
    p1x, p1y = polygon[0][1], polygon[0][0]  # lon, lat

    for i in range(n + 1):
        p2x, p2y = polygon[i % n][1], polygon[i % n][0]
        if min(p1y, p2y) < lat <= max(p1y, p2y):
            if lon <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or lon <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y

    return inside

def calculate_polygon_area_sqm(polygon: List[List[float]]) -> float:
    """
    Calculates approximate surface area in square meters for a geographic polygon.
    """
    if len(polygon) < 3:
        return 0.0

    ref_lat = sum(p[0] for p in polygon) / len(polygon)
    ref_lon = sum(p[1] for p in polygon) / len(polygon)
    
    m_per_lat = 111139.0
    m_per_lon = 111139.0 * math.cos(math.radians(ref_lat))

    pts_xy = [
        ((p[1] - ref_lon) * m_per_lon, (p[0] - ref_lat) * m_per_lat)
        for p in polygon
    ]

    area = 0.0
    n = len(pts_xy)
    for i in range(n):
        j = (i + 1) % n
        area += pts_xy[i][0] * pts_xy[j][1]
        area -= pts_xy[j][0] * pts_xy[i][1]

    return abs(area) / 2.0

def line_segment_intersection(
    p1: Tuple[float, float], p2: Tuple[float, float],
    p3: Tuple[float, float], p4: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """Calculates intersection between 2D segments (x1, y1)-(x2, y2) and (x3, y3)-(x4, y4)."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if abs(denom) < 1e-9:
        return None  # Parallel

    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    if 0.0 <= ua <= 1.0 and 0.0 <= ub <= 1.0:
        ix = x1 + ua * (x2 - x1)
        iy = y1 + ua * (y2 - y1)
        return (ix, iy)

    return None

def closest_point_on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> Tuple[float, float]:
    """Finds the closest point on line segment AB to point P."""
    abx = bx - ax
    aby = by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq < 1e-9:
        return ax, ay
    
    t = ((px - ax) * abx + (py - ay) * aby) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return ax + t * abx, ay + t * aby

def plan_uav_mission(
    polygon: List[List[float]],
    uav_start: Optional[Tuple[float, float]] = None,
    lane_spacing_meters: float = 25.0,
    altitude_meters: float = 65.0,
    cruise_speed_mps: float = 12.0
) -> Tuple[List[Dict[str, Any]], float, float, Dict[str, Any]]:
    """
    Plans optimal UAV deployment and boustrophedon sweep mission from the UAV's last known position
    to and through the newly plotted geofence.
    """
    if len(polygon) < 3:
        return [], 0.0, 0.0, {}

    ref_lat = sum(p[0] for p in polygon) / len(polygon)
    ref_lon = sum(p[1] for p in polygon) / len(polygon)
    m_per_lat = 111139.0
    m_per_lon = 111139.0 * math.cos(math.radians(ref_lat))

    # Convert polygon to Cartesian meters
    poly_xy = [
        ((p[1] - ref_lon) * m_per_lon, (p[0] - ref_lat) * m_per_lat)
        for p in polygon
    ]

    min_x = min(pt[0] for pt in poly_xy)
    max_x = max(pt[0] for pt in poly_xy)
    min_y = min(pt[1] for pt in poly_xy)
    max_y = max(pt[1] for pt in poly_xy)

    y_step = max(lane_spacing_meters, 10.0)
    current_y = min_y + (y_step / 2.0)

    lines_intersections = []
    poly_edges = [
        (poly_xy[i], poly_xy[(i + 1) % len(poly_xy)])
        for i in range(len(poly_xy))
    ]

    while current_y <= max_y:
        sweep_p1 = (min_x - 50.0, current_y)
        sweep_p2 = (max_x + 50.0, current_y)

        intersections = []
        for edge_p1, edge_p2 in poly_edges:
            inter = line_segment_intersection(sweep_p1, sweep_p2, edge_p1, edge_p2)
            if inter:
                intersections.append(inter[0])

        intersections = sorted(list(set(round(x, 2) for x in intersections)))
        if len(intersections) >= 2:
            lines_intersections.append((intersections[0], intersections[-1], current_y))

        current_y += y_step

    if not lines_intersections:
        lines_intersections = [(poly_xy[0][0], poly_xy[1][0], poly_xy[0][1])]

    # Convert UAV start position to Cartesian meters if provided
    uav_x, uav_y = 0.0, 0.0
    if uav_start:
        uav_x = (uav_start[1] - ref_lon) * m_per_lon
        uav_y = (uav_start[0] - ref_lat) * m_per_lat

    # 4 potential entry candidates for the boustrophedon sweep:
    # 1: Start at bottom row, start on left
    # 2: Start at bottom row, start on right
    # 3: Start at top row, start on left
    # 4: Start at top row, start on right
    first_row = lines_intersections[0]
    last_row = lines_intersections[-1]

    candidates = [
        {"from_bottom": True,  "start_left": True,  "pos": (first_row[0], first_row[2])},
        {"from_bottom": True,  "start_left": False, "pos": (first_row[1], first_row[2])},
        {"from_bottom": False, "start_left": True,  "pos": (last_row[0],  last_row[2])},
        {"from_bottom": False, "start_left": False, "pos": (last_row[1],  last_row[2])}
    ]

    # Pick candidate that minimizes transit distance from UAV's current position
    best_candidate = min(
        candidates,
        key=lambda c: math.hypot(c["pos"][0] - uav_x, c["pos"][1] - uav_y)
    )

    # Order rows based on selected optimal entry
    ordered_rows = lines_intersections if best_candidate["from_bottom"] else list(reversed(lines_intersections))
    reverse_sweep = not best_candidate["start_left"]

    raw_cartesian_wps = []
    for x_start, x_end, y in ordered_rows:
        if reverse_sweep:
            raw_cartesian_wps.append((x_end, y))
            raw_cartesian_wps.append((x_start, y))
        else:
            raw_cartesian_wps.append((x_start, y))
            raw_cartesian_wps.append((x_end, y))
        reverse_sweep = not reverse_sweep

    # Build Waypoint Sequence
    waypoints = []
    wp_id = 1
    total_dist = 0.0
    prev_pos = uav_start if uav_start else (ref_lat, ref_lon)

    # Convert entry point to lat/lon
    entry_pt_xy = raw_cartesian_wps[0]
    entry_lat = ref_lat + (entry_pt_xy[1] / m_per_lat)
    entry_lon = ref_lon + (entry_pt_xy[0] / m_per_lon)

    # Leg 1: Transit Waypoint from last known UAV location to geofence entry
    transit_dist = haversine_distance_meters(prev_pos[0], prev_pos[1], entry_lat, entry_lon)
    total_dist += transit_dist

    waypoints.append({
        "id": wp_id,
        "lat": round(entry_lat, 7),
        "lng": round(entry_lon, 7),
        "alt": float(altitude_meters),
        "action": "TRANSIT",
        "drone_type": "UAV",
        "description": "Transit to Geofence Entry"
    })
    wp_id += 1
    prev_pos = (entry_lat, entry_lon)

    # Leg 2: Interior boustrophedon sweep survey waypoints
    for idx, (x, y) in enumerate(raw_cartesian_wps):
        lat = ref_lat + (y / m_per_lat)
        lon = ref_lon + (x / m_per_lon)
        
        dist_step = haversine_distance_meters(prev_pos[0], prev_pos[1], lat, lon)
        total_dist += dist_step
        prev_pos = (lat, lon)

        waypoints.append({
            "id": wp_id,
            "lat": round(lat, 7),
            "lng": round(lon, 7),
            "alt": float(altitude_meters),
            "action": "SURVEY",
            "drone_type": "UAV",
            "description": f"Survey Grid Waypoint #{idx + 1}"
        })
        wp_id += 1

    est_duration_sec = total_dist / max(cruise_speed_mps, 1.0)
    meta = {
        "transit_distance_m": round(transit_dist, 1),
        "survey_distance_m": round(total_dist - transit_dist, 1),
        "entry_point": [round(entry_lat, 7), round(entry_lon, 7)]
    }

    return waypoints, total_dist, est_duration_sec, meta

def plan_ugv_mission(
    polygon: List[List[float]],
    ugv_start: Optional[Tuple[float, float]] = None,
    patrol_speed_mps: float = 3.5
) -> Tuple[List[Dict[str, Any]], float, float, Dict[str, Any]]:
    """
    Plans UGV deployment and perimeter containment patrol from the UGV's last known location
    to the newly plotted geofence boundary.
    """
    if len(polygon) < 3:
        return [], 0.0, 0.0, {}

    ref_lat = sum(p[0] for p in polygon) / len(polygon)
    ref_lon = sum(p[1] for p in polygon) / len(polygon)
    m_per_lat = 111139.0
    m_per_lon = 111139.0 * math.cos(math.radians(ref_lat))

    ugv_x, ugv_y = 0.0, 0.0
    if ugv_start:
        ugv_x = (ugv_start[1] - ref_lon) * m_per_lon
        ugv_y = (ugv_start[0] - ref_lat) * m_per_lat

    poly_xy = [
        ((p[1] - ref_lon) * m_per_lon, (p[0] - ref_lat) * m_per_lat)
        for p in polygon
    ]

    # Find closest entry point on polygon perimeter to UGV's current position
    best_entry_xy = poly_xy[0]
    best_entry_idx = 0
    min_entry_dist = float("inf")

    n = len(poly_xy)
    for i in range(n):
        p_a = poly_xy[i]
        p_b = poly_xy[(i + 1) % n]
        closest_xy = closest_point_on_segment(ugv_x, ugv_y, p_a[0], p_a[1], p_b[0], p_b[1])
        d = math.hypot(closest_xy[0] - ugv_x, closest_xy[1] - ugv_y)
        if d < min_entry_dist:
            min_entry_dist = d
            best_entry_xy = closest_xy
            best_entry_idx = (i + 1) % n

    # Build perimeter patrol order starting from entry point
    ordered_perimeter_xy = [best_entry_xy]
    for i in range(n):
        idx = (best_entry_idx + i) % n
        ordered_perimeter_xy.append(poly_xy[idx])
    ordered_perimeter_xy.append(best_entry_xy)  # Close loop

    # Convert to waypoints
    waypoints = []
    wp_id = 1
    total_dist = 0.0
    prev_pos = ugv_start if ugv_start else (ref_lat, ref_lon)

    # Leg 1: Transit to perimeter entry
    entry_lat = ref_lat + (best_entry_xy[1] / m_per_lat)
    entry_lon = ref_lon + (best_entry_xy[0] / m_per_lon)
    transit_dist = haversine_distance_meters(prev_pos[0], prev_pos[1], entry_lat, entry_lon)
    total_dist += transit_dist

    waypoints.append({
        "id": wp_id,
        "lat": round(entry_lat, 7),
        "lng": round(entry_lon, 7),
        "alt": 0.0,
        "action": "TRANSIT",
        "drone_type": "UGV",
        "description": "UGV Transit to Geofence Perimeter"
    })
    wp_id += 1
    prev_pos = (entry_lat, entry_lon)

    # Leg 2: Perimeter Patrol loop
    for idx, (x, y) in enumerate(ordered_perimeter_xy):
        lat = ref_lat + (y / m_per_lat)
        lon = ref_lon + (x / m_per_lon)
        dist_step = haversine_distance_meters(prev_pos[0], prev_pos[1], lat, lon)
        total_dist += dist_step
        prev_pos = (lat, lon)

        waypoints.append({
            "id": wp_id,
            "lat": round(lat, 7),
            "lng": round(lon, 7),
            "alt": 0.0,
            "action": "PATROL",
            "drone_type": "UGV",
            "description": f"Perimeter Patrol Waypoint #{idx + 1}"
        })
        wp_id += 1

    est_duration_sec = total_dist / max(patrol_speed_mps, 1.0)
    meta = {
        "transit_distance_m": round(transit_dist, 1),
        "patrol_distance_m": round(total_dist - transit_dist, 1),
        "entry_point": [round(entry_lat, 7), round(entry_lon, 7)]
    }

    return waypoints, total_dist, est_duration_sec, meta

# Backwards compatible alias for existing callers
def generate_lawnmower_path(
    polygon: List[List[float]],
    lane_spacing_meters: float = 30.0,
    altitude_meters: float = 65.0,
    cruise_speed_mps: float = 12.0
) -> Tuple[List[Dict[str, Any]], float, float]:
    wps, dist, dur, _ = plan_uav_mission(polygon, None, lane_spacing_meters, altitude_meters, cruise_speed_mps)
    return wps, dist, dur

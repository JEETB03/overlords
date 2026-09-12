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

    # Local flat-earth projection relative to polygon centroid
    ref_lat = sum(p[0] for p in polygon) / len(polygon)
    ref_lon = sum(p[1] for p in polygon) / len(polygon)
    
    # 1 deg lat ~ 111139 m
    # 1 deg lon ~ 111139 * cos(ref_lat) m
    m_per_lat = 111139.0
    m_per_lon = 111139.0 * math.cos(math.radians(ref_lat))

    pts_xy = [
        ((p[1] - ref_lon) * m_per_lon, (p[0] - ref_lat) * m_per_lat)
        for p in polygon
    ]

    # Shoelace formula in meters
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

def generate_lawnmower_path(
    polygon: List[List[float]],
    lane_spacing_meters: float = 30.0,
    altitude_meters: float = 65.0,
    cruise_speed_mps: float = 12.0
) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    Generates a boustrophedon (lawnmower) survey grid traversal path inside the given polygon.
    Returns: (waypoints_list, total_distance_meters, estimated_duration_sec)
    """
    if len(polygon) < 3:
        return [], 0.0, 0.0

    ref_lat = sum(p[0] for p in polygon) / len(polygon)
    ref_lon = sum(p[1] for p in polygon) / len(polygon)
    m_per_lat = 111139.0
    m_per_lon = 111139.0 * math.cos(math.radians(ref_lat))

    # Convert polygon to local Cartesian coordinates (meters)
    poly_xy = [
        ((p[1] - ref_lon) * m_per_lon, (p[0] - ref_lat) * m_per_lat)
        for p in polygon
    ]

    min_x = min(pt[0] for pt in poly_xy)
    max_x = max(pt[0] for pt in poly_xy)
    min_y = min(pt[1] for pt in poly_xy)
    max_y = max(pt[1] for pt in poly_xy)

    # Sweep horizontal scan lines from min_y to max_y
    y_step = max(lane_spacing_meters, 10.0)
    current_y = min_y + (y_step / 2.0)

    lines_intersections = []

    poly_edges = [
        (poly_xy[i], poly_xy[(i + 1) % len(poly_xy)])
        for i in range(len(poly_xy))
    ]

    margin_x = (max_x - min_x) + 50.0

    while current_y <= max_y:
        sweep_p1 = (min_x - 50.0, current_y)
        sweep_p2 = (max_x + 50.0, current_y)

        intersections = []
        for edge_p1, edge_p2 in poly_edges:
            inter = line_segment_intersection(sweep_p1, sweep_p2, edge_p1, edge_p2)
            if inter:
                intersections.append(inter[0])

        intersections = sorted(list(set(round(x, 2) for x in intersections)))
        
        # If we have pairs of intersections (entering and exiting polygon)
        if len(intersections) >= 2:
            lines_intersections.append((intersections[0], intersections[-1], current_y))

        current_y += y_step

    # Build alternating boustrophedon track
    cartesian_waypoints = []
    reverse = False
    for x_start, x_end, y in lines_intersections:
        if reverse:
            cartesian_waypoints.append((x_end, y))
            cartesian_waypoints.append((x_start, y))
        else:
            cartesian_waypoints.append((x_start, y))
            cartesian_waypoints.append((x_end, y))
        reverse = not reverse

    # If polygon is small or no grid lines found, fall back to perimeter waypoints
    if not cartesian_waypoints:
        cartesian_waypoints = poly_xy

    # Convert back to lat/lon coordinates
    waypoints = []
    total_dist = 0.0
    prev_coord = None

    for idx, (x, y) in enumerate(cartesian_waypoints):
        lat = ref_lat + (y / m_per_lat)
        lon = ref_lon + (x / m_per_lon)
        action = "TAKEOFF" if idx == 0 else "WAYPOINT"
        
        if prev_coord:
            total_dist += haversine_distance_meters(prev_coord[0], prev_coord[1], lat, lon)
        prev_coord = (lat, lon)

        waypoints.append({
            "id": idx + 1,
            "lat": round(lat, 7),
            "lng": round(lon, 7),
            "alt": float(altitude_meters),
            "action": action
        })

    est_duration_sec = total_dist / max(cruise_speed_mps, 1.0)
    return waypoints, total_dist, est_duration_sec

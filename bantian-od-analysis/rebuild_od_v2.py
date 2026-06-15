#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_od_v2.py
================
Comprehensive OD matrix rebuild using real Gaode API data.

Loads POI data from Gaode nearby/keyword searches, snaps them to the road
network, computes shortest-path OD matrices via Dijkstra, and exports
results to a new SQLite database and CSV files.
"""

import json
import math
import os
import sqlite3
import sys
import time
from collections import defaultdict
from statistics import median

import networkx as nx

# ── paths ────────────────────────────────────────────────────────────────────
BASE = r"C:\Users\Administrator\.qoderwork\workspace\mq86irc1jqgzw5w6"
GAODE_DIR = os.path.join(BASE, "gaode_comprehensive")
DB_DIR = os.path.join(BASE, "outputs", "coursework", "database")
OLD_DB = os.path.join(DB_DIR, "bantian_transport_network.db")
NEW_DB = os.path.join(DB_DIR, "bantian_od_v2.db")

# ── projection ───────────────────────────────────────────────────────────────
def wgs84_to_cgcs2000(lon, lat):
    """Convert WGS-84 (lon, lat) to CGCS2000 / Gauss-Kruger (easting, northing)."""
    a = 6378137.0
    f = 1 / 298.257222101
    b = a * (1 - f)
    e2 = (a**2 - b**2) / a**2
    e_prime2 = (a**2 - b**2) / b**2
    lon0 = math.radians(114.0)
    lat_r = math.radians(lat)
    dlon = math.radians(lon) - lon0
    N = a / math.sqrt(1 - e2 * math.sin(lat_r)**2)
    T = math.tan(lat_r)**2
    Cp = e_prime2 * math.cos(lat_r)**2
    A = math.cos(lat_r) * dlon
    M = a * (
        (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_r
        - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_r)
        + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_r)
        - (35*e2**3/3072) * math.sin(6*lat_r)
    )
    x = N * (
        A
        + (1 - T + Cp) * A**3 / 6
        + (5 - 18*T + T**2 + 72*Cp) * A**5 / 120
    )
    y = M + N * math.tan(lat_r) * (
        A**2 / 2
        + (5 - T + 9*Cp + 4*Cp**2) * A**4 / 24
        + (61 - 58*T + T**2 + 600*Cp - 330*e_prime2) * A**6 / 720
    )
    return 38500000.0 + x, y


# ── helpers ──────────────────────────────────────────────────────────────────
def load_json(filename):
    path = os.path.join(GAODE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def snap_to_network(lon, lat, node_coords, node_ids):
    """Find the nearest network node to a (lon, lat) point.
    Returns (node_id, snap_dist_m)."""
    easting, northing = wgs84_to_cgcs2000(lon, lat)
    best_id = None
    best_dist = float("inf")
    for nid, (ne, nn) in zip(node_ids, node_coords):
        d = math.sqrt((easting - ne)**2 + (northing - nn)**2)
        if d < best_dist:
            best_dist = d
            best_id = nid
    return best_id, best_dist, easting, northing


def snap_to_network_fast(easting, northing, kd_tree, node_ids):
    """Fast snapping using scipy KDTree (fallback to brute force)."""
    dist, idx = kd_tree.query([easting, northing])
    return node_ids[idx], float(dist)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("=" * 70)
    print("  Bantian OD Matrix v2 — Rebuild with Gaode API Data")
    print("=" * 70)

    # ── 1. Load Gaode data ───────────────────────────────────────────────────
    print("\n[1/7] Loading Gaode API data ...")
    nearby = load_json("nearby_pois.json")
    keyword = load_json("keyword_pois.json")
    walking_routes = load_json("walking_routes.json")
    transit_routes = load_json("transit_routes.json")
    driving_routes = load_json("driving_routes.json")
    bus_stations = load_json("bus_stations.json")

    print(f"  nearby_pois:     {sum(len(v) for v in nearby.values())} POIs across {len(nearby)} categories")
    print(f"  keyword_pois:    {sum(len(v) for v in keyword.values())} POIs across {len(keyword)} categories")
    print(f"  walking_routes:  {len(walking_routes)} routes")
    print(f"  transit_routes:  {len(transit_routes)} routes")
    print(f"  driving_routes:  {len(driving_routes)} routes")
    print(f"  bus_stations:    {len(bus_stations)} stations")

    for cat, pois in nearby.items():
        if pois:
            print(f"    nearby[{cat}]: {len(pois)} POIs")

    # ── 2. Build category POI pools ──────────────────────────────────────────
    print("\n[2/7] Building category POI pools ...")

    # Define the mapping from analysis category to source Gaode categories
    # We merge nearby + keyword sources, de-duplicating by name+lon+lat.
    category_sources = {
        "地铁站":     {"nearby": ["地铁站"], "keyword": ["地铁站"]},
        "公交站":     {"nearby": ["公交站"], "keyword": ["公交站"]},
        "教育设施":   {"nearby": ["小学", "中学", "幼儿园", "大学"], "keyword": ["教育设施", "幼儿园"]},
        "医疗设施":   {"nearby": ["综合医院", "社区医院", "诊所"], "keyword": ["医疗设施"]},
        "商业服务":   {"nearby": ["餐饮", "超市", "便利店", "商场", "菜市场"], "keyword": ["商场", "菜市场"]},
        "公园绿地":   {"nearby": ["公园", "广场"], "keyword": ["公园绿地"]},
    }

    def dedup_key(poi):
        return (poi.get("name", ""), round(float(poi.get("lon", 0)), 5), round(float(poi.get("lat", 0)), 5))

    category_pois = {}  # { category: [ {name, lon, lat, source_cat}, ... ] }
    for cat, sources in category_sources.items():
        seen = set()
        pool = []
        for src_type in ("nearby", "keyword"):
            for src_cat in sources.get(src_type, []):
                src_data = nearby if src_type == "nearby" else keyword
                if src_cat in src_data:
                    for poi in src_data[src_cat]:
                        key = dedup_key(poi)
                        if key not in seen and poi.get("lon") and poi.get("lat"):
                            seen.add(key)
                            pool.append({
                                "name": poi.get("name", ""),
                                "lon": float(poi["lon"]),
                                "lat": float(poi["lat"]),
                                "source_cat": src_cat,
                            })
        category_pois[cat] = pool
        print(f"  {cat}: {len(pool)} unique POIs")

    # ── 3. Load existing database ────────────────────────────────────────────
    print("\n[3/7] Loading existing road network database ...")
    conn_old = sqlite3.connect(OLD_DB)
    cur_old = conn_old.cursor()

    # Communities
    cur_old.execute("SELECT community_id, name, address, lon_wgs84, lat_wgs84, easting, northing, network_node, snap_dist_m FROM communities")
    communities = cur_old.fetchall()
    print(f"  Communities: {len(communities)}")

    # Network nodes
    cur_old.execute("SELECT node_id, easting, northing FROM network_nodes")
    nodes_raw = cur_old.fetchall()
    node_ids = [r[0] for r in nodes_raw]
    node_coords = [(r[1], r[2]) for r in nodes_raw]
    node_map = {r[0]: (r[1], r[2]) for r in nodes_raw}
    print(f"  Network nodes: {len(nodes_raw)}")

    # Roads / edges
    cur_old.execute("SELECT edge_id, from_node, to_node, road_name, road_type, speed_kmh, length_m, travel_time_min FROM roads")
    roads_raw = cur_old.fetchall()
    print(f"  Road edges: {len(roads_raw)}")

    # Load old OD statistics for comparison later
    conn_multi = sqlite3.connect(os.path.join(DB_DIR, "bantian_multi_service_od.db"))
    cur_multi = conn_multi.cursor()
    try:
        cur_multi.execute("SELECT category, facility_count, avg_min_dist_m, median_min_dist_m, max_min_dist_m, within_1km_pct, within_2km_pct FROM od_statistics")
        old_stats = {row[0]: row for row in cur_multi.fetchall()}
        print(f"  Old OD statistics loaded: {len(old_stats)} categories")
    except Exception:
        old_stats = {}
        print("  Old OD statistics: not available")
    conn_multi.close()

    conn_old.close()

    # ── 4. Build NetworkX graph ──────────────────────────────────────────────
    print("\n[4/7] Building NetworkX graph from roads ...")
    G = nx.Graph()
    for nid, (e, n) in zip(node_ids, node_coords):
        G.add_node(nid, easting=e, northing=n)

    edge_count = 0
    for row in roads_raw:
        eid, fn, tn, rname, rtype, speed, length_m, ttime = row
        if fn in node_map and tn in node_map and length_m and length_m > 0:
            G.add_edge(fn, tn, weight=length_m, edge_id=eid, road_name=rname or "", road_type=rtype or "")
            edge_count += 1
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Build a simple spatial index for fast snapping (brute force with numpy-like approach)
    # Use scipy KDTree if available, else brute force
    try:
        from scipy.spatial import cKDTree
        import numpy as np
        coords_arr = np.array(node_coords)
        kd_tree = cKDTree(coords_arr)
        use_kdtree = True
        print("  Using scipy cKDTree for fast snapping")
    except ImportError:
        use_kdtree = False
        print("  scipy not available; using brute-force snapping (slower)")

    def snap_point(easting, northing):
        if use_kdtree:
            dist, idx = kd_tree.query([easting, northing])
            return node_ids[idx], float(dist)
        else:
            best_id, best_d = None, float("inf")
            for nid, (ne, nn) in zip(node_ids, node_coords):
                d = math.sqrt((easting - ne)**2 + (northing - nn)**2)
                if d < best_d:
                    best_d = d
                    best_id = nid
            return best_id, best_d

    # ── 5. Snap POIs to network ──────────────────────────────────────────────
    print("\n[5/7] Snapping POIs to road network ...")
    category_snapped = {}  # { category: [ {name, lon, lat, easting, northing, node_id, snap_dist} ] }

    for cat, pois in category_pois.items():
        snapped = []
        for poi in pois:
            e, n = wgs84_to_cgcs2000(poi["lon"], poi["lat"])
            nid, sd = snap_point(e, n)
            snapped.append({
                "name": poi["name"],
                "lon": poi["lon"],
                "lat": poi["lat"],
                "easting": e,
                "northing": n,
                "node_id": nid,
                "snap_dist": sd,
            })
        category_snapped[cat] = snapped
        avg_snap = sum(p["snap_dist"] for p in snapped) / max(len(snapped), 1)
        max_snap = max((p["snap_dist"] for p in snapped), default=0)
        print(f"  {cat}: {len(snapped)} POIs snapped (avg snap={avg_snap:.1f}m, max={max_snap:.1f}m)")

    # ── 6. Compute OD matrices ───────────────────────────────────────────────
    print("\n[6/7] Computing OD matrices (Dijkstra shortest paths) ...")

    # For each community, compute shortest distance to all network nodes
    # Then for each category, find nearest POI by network distance.

    # Pre-compute: for each community, run Dijkstra from its network node
    community_nodes = {}  # community_id -> node_id
    for c in communities:
        cid, cname, caddr, clon, clat, ce, cn, cnode, csnap = c
        community_nodes[cid] = cnode

    # Collect unique community network nodes (many communities may share a node)
    unique_comm_nodes = set(community_nodes.values())
    print(f"  Unique community network nodes: {len(unique_comm_nodes)}")

    # Compute Dijkstra from each unique community node
    dijkstra_results = {}  # node_id -> {target_node: distance_m}
    computed = 0
    for src_node in unique_comm_nodes:
        if src_node is None or src_node not in G:
            continue
        lengths = nx.single_source_dijkstra_path_length(G, src_node, weight="weight")
        dijkstra_results[src_node] = lengths
        computed += 1
        if computed % 20 == 0:
            print(f"    Dijkstra computed: {computed}/{len(unique_comm_nodes)}")
    print(f"    Dijkstra computed: {computed}/{len(unique_comm_nodes)} (done)")

    # Now build the OD matrix v2: for each community, for each category,
    # find the nearest POI (by network distance).
    od_rows = []  # (community_id, community_name, category, nearest_poi_name, nearest_distance_m, nearest_poi_lon, nearest_poi_lat)
    od_all_pairs = []  # for statistics: all (community, category, distance) triples

    # For each category, pre-group POIs by their network node for faster lookup
    category_by_node = {}  # cat -> { node_id: [poi_dict, ...] }
    for cat, snapped_list in category_snapped.items():
        by_node = defaultdict(list)
        for p in snapped_list:
            by_node[p["node_id"]].append(p)
        category_by_node[cat] = by_node

    for c in communities:
        cid, cname, caddr, clon, clat, ce, cn, cnode, csnap = c
        if cnode is None or cnode not in dijkstra_results:
            continue
        lengths = dijkstra_results[cnode]

        for cat in category_snapped:
            best_dist = float("inf")
            best_poi = None
            by_node = category_by_node[cat]

            # Check all POI network nodes that are reachable
            for poi_node, poi_list in by_node.items():
                if poi_node in lengths:
                    net_dist = lengths[poi_node]
                    # Add snap distances for more accurate total
                    for p in poi_list:
                        total = net_dist + p["snap_dist"]
                        if total < best_dist:
                            best_dist = total
                            best_poi = p

            if best_poi is not None:
                od_rows.append((cid, cname, cat, best_poi["name"],
                                round(best_dist, 1),
                                best_poi["lon"], best_poi["lat"]))
                od_all_pairs.append((cid, cname, cat, best_dist))
            else:
                od_rows.append((cid, cname, cat, None, None, None, None))

    print(f"  OD matrix v2: {len(od_rows)} rows ({len(communities)} communities x {len(category_snapped)} categories)")

    # ── Compute statistics ───────────────────────────────────────────────────
    print("\n  Computing statistics ...")
    stats_rows = []
    for cat in category_snapped:
        dists = [d for (_, _, c, d) in od_all_pairs if c == cat and d is not None]
        if not dists:
            continue
        n_facilities = len(category_snapped[cat])
        avg_d = sum(dists) / len(dists)
        med_d = median(dists)
        max_d = max(dists)
        within_1km = sum(1 for d in dists if d <= 1000) / len(dists) * 100
        within_2km = sum(1 for d in dists if d <= 2000) / len(dists) * 100
        stats_rows.append((cat, n_facilities, round(avg_d, 1), round(med_d, 1),
                           round(max_d, 1), round(within_1km, 1), round(within_2km, 1)))
        print(f"    {cat}: facilities={n_facilities}, avg={avg_d:.0f}m, median={med_d:.0f}m, "
              f"max={max_d:.0f}m, 1km={within_1km:.1f}%, 2km={within_2km:.1f}%")

    # ── 7. Write new database and CSVs ───────────────────────────────────────
    print("\n[7/7] Writing output database and CSV files ...")

    # Remove old DB if exists
    if os.path.exists(NEW_DB):
        os.remove(NEW_DB)

    conn_new = sqlite3.connect(NEW_DB)
    cur_new = conn_new.cursor()

    # od_matrix_v2
    cur_new.execute("""
        CREATE TABLE od_matrix_v2 (
            community_id    INTEGER,
            community_name  TEXT,
            category        TEXT,
            nearest_poi_name TEXT,
            nearest_distance_m REAL,
            nearest_poi_lon REAL,
            nearest_poi_lat REAL
        )
    """)
    cur_new.executemany(
        "INSERT INTO od_matrix_v2 VALUES (?,?,?,?,?,?,?)",
        od_rows
    )

    # od_statistics_v2
    cur_new.execute("""
        CREATE TABLE od_statistics_v2 (
            category        TEXT,
            facility_count  INTEGER,
            avg_dist        REAL,
            median_dist     REAL,
            max_dist        REAL,
            within_1km_pct  REAL,
            within_2km_pct  REAL
        )
    """)
    cur_new.executemany(
        "INSERT INTO od_statistics_v2 VALUES (?,?,?,?,?,?,?)",
        stats_rows
    )

    # real_routes table
    cur_new.execute("""
        CREATE TABLE real_routes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            route_type      TEXT,
            origin          TEXT,
            destination     TEXT,
            category        TEXT,
            dest_lon        REAL,
            dest_lat        REAL,
            distance_m      REAL,
            duration_min    REAL,
            extra_info      TEXT
        )
    """)

    route_rows = []
    for r in walking_routes:
        extra = json.dumps({
            "duration_s": r.get("duration_s"),
            "steps_count": r.get("steps_count"),
        }, ensure_ascii=False)
        route_rows.append(("walking", r["origin"], r["destination"], r["category"],
                           r["dest_lon"], r["dest_lat"], r["distance_m"],
                           r["duration_min"], extra))

    for r in transit_routes:
        extra = json.dumps({
            "walking_distance_m": r.get("walking_distance_m"),
            "cost": r.get("cost"),
            "nightflag": r.get("nightflag"),
            "segments_count": r.get("segments_count"),
            "bus_lines": r.get("bus_lines"),
            "metro_used": r.get("metro_used"),
        }, ensure_ascii=False)
        route_rows.append(("transit", r["origin"], r["destination"], r["category"],
                           r["dest_lon"], r["dest_lat"], r["distance_m"],
                           r["duration_min"], extra))

    for r in driving_routes:
        extra = json.dumps({
            "toll_cost": r.get("toll_cost"),
            "traffic_lights": r.get("traffic_lights"),
            "strategy": r.get("strategy"),
        }, ensure_ascii=False)
        route_rows.append(("driving", r["origin"], r["destination"], r["category"],
                           r["dest_lon"], r["dest_lat"], r["distance_m"],
                           r["duration_min"], extra))

    cur_new.executemany(
        "INSERT INTO real_routes (route_type, origin, destination, category, dest_lon, dest_lat, distance_m, duration_min, extra_info) VALUES (?,?,?,?,?,?,?,?,?)",
        route_rows
    )

    # Also copy communities and poi_facilities for reference
    cur_new.execute("""
        CREATE TABLE communities (
            community_id INTEGER PRIMARY KEY,
            name TEXT, address TEXT,
            lon_wgs84 REAL, lat_wgs84 REAL,
            easting REAL, northing REAL,
            network_node INTEGER, snap_dist_m REAL
        )
    """)
    cur_new.executemany(
        "INSERT INTO communities VALUES (?,?,?,?,?,?,?,?,?)",
        communities
    )

    # POI facilities table (all snapped POIs)
    cur_new.execute("""
        CREATE TABLE poi_facilities_v2 (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT,
            name        TEXT,
            lon         REAL,
            lat         REAL,
            easting     REAL,
            northing    REAL,
            network_node INTEGER,
            snap_dist_m REAL,
            source_cat  TEXT
        )
    """)
    poi_id = 0
    for cat, snapped_list in category_snapped.items():
        for p in snapped_list:
            poi_id += 1
            cur_new.execute(
                "INSERT INTO poi_facilities_v2 VALUES (?,?,?,?,?,?,?,?,?,?)",
                (poi_id, cat, p["name"], p["lon"], p["lat"],
                 p["easting"], p["northing"], p["node_id"], p["snap_dist"], p.get("source_cat", ""))
            )

    # Bus stations table
    cur_new.execute("""
        CREATE TABLE bus_stations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT,
            lon             REAL,
            lat             REAL,
            buslines_count  INTEGER,
            buslines_names  TEXT,
            buslines_types  TEXT
        )
    """)
    for bs in bus_stations:
        cur_new.execute(
            "INSERT INTO bus_stations (name, lon, lat, buslines_count, buslines_names, buslines_types) VALUES (?,?,?,?,?,?)",
            (bs["name"], bs["lon"], bs["lat"], bs.get("buslines_count", 0),
             bs.get("buslines_names", ""), bs.get("buslines_types", ""))
        )

    conn_new.commit()
    conn_new.close()
    print(f"  Database written: {NEW_DB}")

    # ── Export CSVs ──────────────────────────────────────────────────────────
    # od_matrix_v2.csv
    csv_od = os.path.join(DB_DIR, "od_matrix_v2.csv")
    with open(csv_od, "w", encoding="utf-8-sig") as f:
        f.write("community_id,community_name,category,nearest_poi_name,nearest_distance_m,nearest_poi_lon,nearest_poi_lat\n")
        for row in od_rows:
            cid, cname, cat, pname, dist, plon, plat = row
            # Escape commas in names
            cname_q = f'"{cname}"' if "," in (cname or "") else (cname or "")
            pname_q = f'"{pname}"' if "," in (pname or "") else (pname or "")
            dist_s = f"{dist:.1f}" if dist is not None else ""
            plon_s = f"{plon}" if plon is not None else ""
            plat_s = f"{plat}" if plat is not None else ""
            f.write(f"{cid},{cname_q},{cat},{pname_q},{dist_s},{plon_s},{plat_s}\n")
    print(f"  CSV written: {csv_od}")

    # od_statistics_v2.csv
    csv_stats = os.path.join(DB_DIR, "od_statistics_v2.csv")
    with open(csv_stats, "w", encoding="utf-8-sig") as f:
        f.write("category,facility_count,avg_dist,median_dist,max_dist,within_1km_pct,within_2km_pct\n")
        for row in stats_rows:
            f.write(",".join(str(v) for v in row) + "\n")
    print(f"  CSV written: {csv_stats}")

    # real_routes_comparison.csv
    csv_routes = os.path.join(DB_DIR, "real_routes_comparison.csv")

    # Build comparison: match walking/transit/driving by (origin, destination)
    walk_dict = {}
    for r in walking_routes:
        key = (r["origin"], r["destination"])
        walk_dict[key] = r

    transit_dict = {}
    for r in transit_routes:
        key = (r["origin"], r["destination"])
        transit_dict[key] = r

    driving_dict = {}
    for r in driving_routes:
        key = (r["origin"], r["destination"])
        driving_dict[key] = r

    # All unique destinations
    all_dests = set(walk_dict.keys()) | set(transit_dict.keys()) | set(driving_dict.keys())

    with open(csv_routes, "w", encoding="utf-8-sig") as f:
        f.write("origin,destination,category,"
                "walk_dist_m,walk_time_min,"
                "transit_dist_m,transit_time_min,transit_cost,transit_metro,"
                "drive_dist_m,drive_time_min,drive_tolls\n")
        for (origin, dest) in sorted(all_dests):
            w = walk_dict.get((origin, dest), {})
            t = transit_dict.get((origin, dest), {})
            d = driving_dict.get((origin, dest), {})
            cat = w.get("category") or t.get("category") or d.get("category", "")
            f.write(f"{origin},{dest},{cat},"
                    f"{w.get('distance_m','')},{w.get('duration_min','')},"
                    f"{t.get('distance_m','')},{t.get('duration_min','')},{t.get('cost','')},{t.get('metro_used','')},"
                    f"{d.get('distance_m','')},{d.get('duration_min','')},{d.get('toll_cost','')}\n")
    print(f"  CSV written: {csv_routes}")

    # ── 8. Comparison: old vs new ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  COMPARISON: Old OD Statistics vs New OD v2 Statistics")
    print("=" * 70)

    # Map old categories to new (exact names from bantian_multi_service_od.db)
    # Old query columns: 0=category, 1=facility_count, 2=avg_min_dist_m, 3=median_min_dist_m,
    #                   4=max_min_dist_m, 5=within_1km_pct, 6=within_2km_pct
    old_to_new = {
        "餐饮商业":  "商业服务",
        "商超便利店": "商业服务",
        "地铁站":    "地铁站",
        "公交站":    "公交站",
        "公园绿地":  "公园绿地",
        "教育设施":  "教育设施",
        "社康诊所":  "医疗设施",
    }

    # New stats tuple: 0=cat, 1=facility_count, 2=avg, 3=median, 4=max, 5=within_1km, 6=within_2km
    print(f"\n{'Category':<16} {'Old Avg':>10} {'New Avg':>10} {'Old Med':>10} {'New Med':>10} {'Old 1km%':>10} {'New 1km%':>10} {'Old 2km%':>10} {'New 2km%':>10}")
    print("-" * 106)

    new_stats_dict = {row[0]: row for row in stats_rows}
    printed_new_cats = set()
    for old_cat, new_cat in old_to_new.items():
        old = old_stats.get(old_cat)
        new = new_stats_dict.get(new_cat)
        if old and new:
            printed_new_cats.add(new_cat)
            print(f"{new_cat:<16} {old[2]:>10.0f} {new[2]:>10.0f} {old[3]:>10.0f} {new[3]:>10.0f} {old[5]:>10.1f} {new[5]:>10.1f} {old[6]:>10.1f} {new[6]:>10.1f}")
        elif new:
            printed_new_cats.add(new_cat)
            print(f"{new_cat:<16} {'N/A':>10} {new[2]:>10.0f} {'N/A':>10} {new[3]:>10.0f} {'N/A':>10} {new[5]:>10.1f} {'N/A':>10} {new[6]:>10.1f}")

    # Also print new categories not yet printed
    for cat, row in new_stats_dict.items():
        if cat not in printed_new_cats:
            print(f"{cat:<16} {'N/A':>10} {row[2]:>10.0f} {'N/A':>10} {row[3]:>10.0f} {'N/A':>10} {row[5]:>10.1f} {'N/A':>10} {row[6]:>10.1f}")

    # ── Real routes comparison summary ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("  REAL ROUTES COMPARISON (Gaode API: Walking vs Transit vs Driving)")
    print("=" * 70)

    # Find OD pairs that have both walking and transit
    walk_transit_pairs = set(walk_dict.keys()) & set(transit_dict.keys())
    walk_drive_pairs = set(walk_dict.keys()) & set(driving_dict.keys())
    all_three = set(walk_dict.keys()) & set(transit_dict.keys()) & set(driving_dict.keys())

    print(f"\n  Walking routes:        {len(walking_routes)}")
    print(f"  Transit routes:        {len(transit_routes)}")
    print(f"  Driving routes:        {len(driving_routes)}")
    print(f"  Walk+Transit overlap:  {len(walk_transit_pairs)}")
    print(f"  Walk+Drive overlap:    {len(walk_drive_pairs)}")
    print(f"  All three modes:       {len(all_three)}")

    if all_three:
        print(f"\n  {'Destination':<30} {'Walk(m)':>8} {'Walk(min)':>10} {'Transit(m)':>11} {'Transit(min)':>13} {'Drive(m)':>9} {'Drive(min)':>11}")
        print("  " + "-" * 96)
        for (origin, dest) in sorted(all_three):
            w = walk_dict[(origin, dest)]
            t = transit_dict[(origin, dest)]
            d = driving_dict[(origin, dest)]
            dest_short = dest[:28]
            print(f"  {dest_short:<30} {w['distance_m']:>8} {w['duration_min']:>10.1f} {t['distance_m']:>11} {t['duration_min']:>13.1f} {d['distance_m']:>9} {d['duration_min']:>11.1f}")

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  DONE in {elapsed:.1f} seconds")
    print(f"  Database: {NEW_DB}")
    print(f"  CSV files: od_matrix_v2.csv, od_statistics_v2.csv, real_routes_comparison.csv")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Supplementary data collection for Huawei spatial analysis.
Four dimensions:
  1. Similar communities near Huawei Bantian base
  2. Schools distribution + walking distance from each community
  3. Public transit (bus stops) coverage within 500m
  4. Competitor enterprise housing comparison
  5. Real estate agency density (market-ization proxy)

API quotas: keyword/nearby search 1000/day, walking route 300k/day
"""

import requests, json, time, os, sys

API_KEY = "b5470a516f71e53cd79deaa7f2d48ec0"
HUAWEI_BASE = "114.0645,22.6570"
QIUGANG = "114.075434,22.668739"
BANTIAN_CENTER = "114.075434,22.668739"  # use Qiugang as Bantian center

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gaode_supplement")
os.makedirs(OUT_DIR, exist_ok=True)

call_count = 0

def api_get(url, params, delay=0.12):
    global call_count
    call_count += 1
    params["key"] = API_KEY
    params["output"] = "json"
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        time.sleep(delay)
        return data
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return None

def save_json(name, data):
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [SAVED] {path} ({len(json.dumps(data, ensure_ascii=False))} chars)")

# ============================================================
# PHASE 1: Identify similar communities near Huawei base
# ============================================================
def phase1_communities():
    print("\n" + "="*60)
    print("PHASE 1: Identify residential communities near Huawei base")
    print("="*60)

    all_communities = []
    # Search keywords that might find enterprise housing / residential compounds
    search_terms = [
        ("住宅区", "住宅区"),
        ("公寓", "公寓"),
        ("花园", "花园"),
        ("宿舍", "宿舍"),
        ("社区", "社区"),
        ("人才房", "人才房"),
        ("保障房", "保障房"),
    ]

    for keyword, label in search_terms:
        print(f"\n  Searching '{keyword}' near Huawei base (3km)...")
        data = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": HUAWEI_BASE,
                "keywords": keyword,
                "radius": "3000",
                "types": "120000",  # 商务住宅
                "offset": "25",
                "page": "1",
                "extensions": "all",
            }
        )
        if data and data.get("status") == "1" and data.get("pois"):
            pois = data["pois"]
            print(f"    Found {len(pois)} results (total: {data.get('count', '?')})")
            for p in pois:
                loc = p.get("location", "")
                coords = [float(x) for x in loc.split(",")] if loc else None
                comm = {
                    "name": p.get("name", ""),
                    "address": p.get("address", ""),
                    "type": p.get("type", ""),
                    "typecode": p.get("typecode", ""),
                    "location": loc,
                    "coords": coords,
                    "search_term": label,
                    "distance": p.get("distance", ""),
                }
                all_communities.append(comm)

    # Also search specifically for known enterprise housing keywords
    print(f"\n  Searching '华为' residential near base...")
    data = api_get(
        "https://restapi.amap.com/v3/place/around",
        {
            "location": HUAWEI_BASE,
            "keywords": "华为",
            "radius": "5000",
            "types": "120000",
            "offset": "25",
            "page": "1",
        }
    )
    if data and data.get("status") == "1" and data.get("pois"):
        pois = data["pois"]
        print(f"    Found {len(pois)} '华为' residential results")
        for p in pois:
            loc = p.get("location", "")
            coords = [float(x) for x in loc.split(",")] if loc else None
            all_communities.append({
                "name": p.get("name", ""),
                "address": p.get("address", ""),
                "type": p.get("type", ""),
                "typecode": p.get("typecode", ""),
                "location": loc,
                "coords": coords,
                "search_term": "华为住宅",
                "distance": p.get("distance", ""),
            })

    # Deduplicate by name
    seen = set()
    unique = []
    for c in all_communities:
        if c["name"] and c["name"] not in seen:
            seen.add(c["name"])
            unique.append(c)

    print(f"\n  Total unique communities found: {len(unique)}")
    save_json("communities_near_huawei", {
        "search_center": HUAWEI_BASE,
        "search_radius": "3000m",
        "total_found": len(unique),
        "communities": unique
    })
    return unique

# ============================================================
# PHASE 2: Schools distribution + walking routes
# ============================================================
def phase2_schools(communities):
    print("\n" + "="*60)
    print("PHASE 2: Schools distribution + walking distances")
    print("="*60)

    # First, find all schools in Bantian area
    all_schools = []
    for school_type, typecode in [("幼儿园", "141203"), ("小学", "141203")]:
        # Use keyword search for broader coverage
        print(f"\n  Searching all '{school_type}' in Bantian (3km from center)...")
        for page in range(1, 4):  # up to 3 pages
            data = api_get(
                "https://restapi.amap.com/v3/place/around",
                {
                    "location": BANTIAN_CENTER,
                    "keywords": school_type,
                    "radius": "3000",
                    "types": typecode,
                    "offset": "25",
                    "page": str(page),
                }
            )
            if data and data.get("status") == "1" and data.get("pois"):
                pois = data["pois"]
                print(f"    Page {page}: {len(pois)} results")
                for p in pois:
                    loc = p.get("location", "")
                    all_schools.append({
                        "name": p.get("name", ""),
                        "type": school_type,
                        "location": loc,
                        "address": p.get("address", ""),
                    })
                if len(pois) < 25:
                    break
            else:
                break

    # Deduplicate schools
    seen_schools = set()
    unique_schools = []
    for s in all_schools:
        if s["name"] not in seen_schools:
            seen_schools.add(s["name"])
            unique_schools.append(s)
    print(f"\n  Total unique schools found: {len(unique_schools)}")

    save_json("schools_bantian", {
        "search_center": BANTIAN_CENTER,
        "search_radius": "3000m",
        "total": len(unique_schools),
        "schools": unique_schools
    })

    # Now compute walking routes from each key community to nearest school
    # Limit to ~8 communities to save API calls
    key_communities = communities[:8] if len(communities) > 8 else communities

    # Always include 秋港花园
    qiugang_entry = {
        "name": "秋港花园",
        "location": QIUGANG,
        "coords": [114.075434, 22.668739],
    }
    if not any(c["name"] == "秋港花园" for c in key_communities):
        key_communities.insert(0, qiugang_entry)

    school_routes = []
    for comm in key_communities:
        loc = comm.get("location", "")
        if not loc:
            continue

        # Find nearest school by straight-line distance first
        nearest = None
        min_dist = float("inf")
        for s in unique_schools:
            if s["location"]:
                slon, slat = [float(x) for x in s["location"].split(",")]
                clon, clat = [float(x) for x in loc.split(",")]
                # Rough distance in meters
                d = ((slon - clon) * 100000) ** 2 + ((slat - clat) * 110000) ** 2
                if d < min_dist:
                    min_dist = d
                    nearest = s

        if nearest and nearest["location"]:
            print(f"\n  Walking route: {comm['name']} -> {nearest['name']}")
            route_data = api_get(
                "https://restapi.amap.com/v3/direction/walking",
                {
                    "origin": loc,
                    "destination": nearest["location"],
                }
            )
            route_info = {"community": comm["name"], "school": nearest["name"],
                          "school_type": nearest["type"]}
            if route_data and route_data.get("status") == "1":
                paths = route_data.get("route", {}).get("paths", [])
                if paths:
                    p = paths[0]
                    route_info["distance_m"] = int(p.get("distance", 0))
                    route_info["duration_min"] = round(int(p.get("duration", 0)) / 60, 1)
                    route_info["steps_count"] = len(p.get("steps", []))
                    print(f"    {route_info['distance_m']}m / {route_info['duration_min']}min")
            else:
                route_info["error"] = "API failed"
                print(f"    API failed")

            school_routes.append(route_info)

    save_json("school_walking_routes", {
        "total_routes": len(school_routes),
        "routes": school_routes
    })

    return unique_schools, school_routes

# ============================================================
# PHASE 3: Public transit coverage
# ============================================================
def phase3_transit(communities):
    print("\n" + "="*60)
    print("PHASE 3: Public transit coverage (bus stops within 500m)")
    print("="*60)

    key_communities = communities[:8] if len(communities) > 8 else communities

    # Always include 秋港花园
    qiugang_entry = {
        "name": "秋港花园",
        "location": QIUGANG,
    }
    if not any(c["name"] == "秋港花园" for c in key_communities):
        key_communities.insert(0, qiugang_entry)

    transit_data = []
    for comm in key_communities:
        loc = comm.get("location", "")
        if not loc:
            continue

        print(f"\n  Bus stops near {comm['name']} (500m)...")
        data = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": loc,
                "keywords": "公交站",
                "types": "150700",  # 公交车站
                "radius": "500",
                "offset": "25",
                "page": "1",
            }
        )

        stops = []
        if data and data.get("status") == "1" and data.get("pois"):
            for p in data["pois"]:
                buslines = p.get("buslines", [])
                stop_info = {
                    "name": p.get("name", ""),
                    "location": p.get("location", ""),
                    "distance": p.get("distance", ""),
                    "buslines_count": len(buslines),
                    "buslines": [b.get("name", "") for b in buslines] if buslines else [],
                }
                stops.append(stop_info)

        # Count unique bus lines across all stops
        all_lines = set()
        for s in stops:
            for line in s["buslines"]:
                all_lines.add(line)

        entry = {
            "community": comm["name"],
            "stops_within_500m": len(stops),
            "unique_bus_lines": len(all_lines),
            "bus_lines_list": sorted(list(all_lines)),
            "stops_detail": stops,
        }
        print(f"    {entry['stops_within_500m']} stops, {entry['unique_bus_lines']} unique lines")
        transit_data.append(entry)

    save_json("transit_coverage", {
        "search_radius": "500m",
        "total_communities": len(transit_data),
        "communities": transit_data
    })

    return transit_data

# ============================================================
# PHASE 4: Competitor enterprises + their housing
# ============================================================
def phase4_competitors():
    print("\n" + "="*60)
    print("PHASE 4: Competitor enterprises in Bantian")
    print("="*60)

    # Search for major companies in Bantian area
    competitor_keywords = [
        "富士康", "Foxconn",
        "神舟电脑", "Hasee",
        "康冠", "KTC",
        "比亚迪", "BYD",
        "天安云谷",  # already known but check for other tenants
        "科技园", "产业园",
        "工业区",
    ]

    all_competitors = []
    for kw in competitor_keywords:
        print(f"\n  Searching '{kw}' near Bantian (5km)...")
        data = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": BANTIAN_CENTER,
                "keywords": kw,
                "radius": "5000",
                "types": "170000",  # 公司企业
                "offset": "25",
                "page": "1",
            }
        )
        if data and data.get("status") == "1" and data.get("pois"):
            pois = data["pois"]
            print(f"    Found {len(pois)} results")
            for p in pois:
                loc = p.get("location", "")
                all_competitors.append({
                    "name": p.get("name", ""),
                    "type": p.get("type", ""),
                    "typecode": p.get("typecode", ""),
                    "address": p.get("address", ""),
                    "location": loc,
                    "search_keyword": kw,
                })

    # Deduplicate
    seen = set()
    unique_comp = []
    for c in all_competitors:
        if c["name"] not in seen:
            seen.add(c["name"])
            unique_comp.append(c)

    print(f"\n  Total unique enterprise entries: {len(unique_comp)}")

    # For major competitors, search for nearby residential
    major_names = ["富士康", "神舟", "康冠", "比亚迪"]
    competitor_housing = []

    for comp in unique_comp:
        is_major = any(mn in comp["name"] for mn in major_names)
        if not is_major or not comp["location"]:
            continue

        print(f"\n  Searching residential near {comp['name']}...")
        data = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": comp["location"],
                "keywords": "宿舍|公寓|花园|住宅",
                "radius": "1000",
                "types": "120000",
                "offset": "25",
                "page": "1",
            }
        )
        nearby_res = []
        if data and data.get("status") == "1" and data.get("pois"):
            for p in data["pois"]:
                nearby_res.append({
                    "name": p.get("name", ""),
                    "location": p.get("location", ""),
                    "distance": p.get("distance", ""),
                })

        # Also search for internal facilities (like we did for Qiugang)
        print(f"  Searching internal facilities near {comp['name']} (200m)...")
        data2 = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": comp["location"],
                "radius": "200",
                "offset": "25",
                "page": "1",
            }
        )
        internal = []
        if data2 and data2.get("status") == "1" and data2.get("pois"):
            for p in data2["pois"]:
                internal.append({
                    "name": p.get("name", ""),
                    "type": p.get("type", ""),
                })

        competitor_housing.append({
            "enterprise": comp["name"],
            "enterprise_location": comp["location"],
            "nearby_residential_count": len(nearby_res),
            "nearby_residential": nearby_res,
            "internal_facilities_count": len(internal),
            "internal_facilities": internal,
        })

    save_json("competitor_enterprises", {
        "search_center": BANTIAN_CENTER,
        "total_enterprises_found": len(unique_comp),
        "enterprises": unique_comp,
    })

    save_json("competitor_housing", {
        "total_analyzed": len(competitor_housing),
        "analysis": competitor_housing
    })

    return unique_comp, competitor_housing

# ============================================================
# PHASE 5: Real estate agency density
# ============================================================
def phase5_realestate(communities):
    print("\n" + "="*60)
    print("PHASE 5: Real estate agency density (market proxy)")
    print("="*60)

    key_communities = communities[:8] if len(communities) > 8 else communities

    # Always include 秋港花园
    qiugang_entry = {
        "name": "秋港花园",
        "location": QIUGANG,
    }
    if not any(c["name"] == "秋港花园" for c in key_communities):
        key_communities.insert(0, qiugang_entry)

    realestate_data = []
    for comm in key_communities:
        loc = comm.get("location", "")
        if not loc:
            continue

        # Search for 房产中介 near community
        print(f"\n  Real estate agencies near {comm['name']} (500m)...")
        data = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": loc,
                "keywords": "房产中介|地产|链家|贝壳|乐有家",
                "radius": "500",
                "offset": "25",
                "page": "1",
            }
        )
        agencies = []
        if data and data.get("status") == "1" and data.get("pois"):
            for p in data["pois"]:
                agencies.append({
                    "name": p.get("name", ""),
                    "type": p.get("type", ""),
                    "distance": p.get("distance", ""),
                })

        # Also count convenience stores/restaurants as "commercial vibrancy" proxy
        print(f"  Commercial vibrancy near {comm['name']} (200m)...")
        data2 = api_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": loc,
                "keywords": "餐饮|超市|便利店",
                "radius": "200",
                "offset": "25",
                "page": "1",
            }
        )
        commercial = []
        if data2 and data2.get("status") == "1" and data2.get("pois"):
            for p in data2["pois"]:
                commercial.append({
                    "name": p.get("name", ""),
                    "type": p.get("type", ""),
                })

        entry = {
            "community": comm["name"],
            "realestate_agencies_500m": len(agencies),
            "agencies_detail": agencies,
            "commercial_200m": len(commercial),
            "commercial_detail": commercial,
        }
        print(f"    Agencies: {entry['realestate_agencies_500m']}, Commercial: {entry['commercial_200m']}")
        realestate_data.append(entry)

    save_json("realestate_density", {
        "total_communities": len(realestate_data),
        "communities": realestate_data
    })

    return realestate_data

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("SUPPLEMENTARY DATA COLLECTION")
    print("Huawei Bantian Spatial Analysis - Extended Dimensions")
    print("=" * 60)

    # Phase 1: Find communities
    communities = phase1_communities()

    # Phase 2: Schools
    schools, school_routes = phase2_schools(communities)

    # Phase 3: Transit
    transit = phase3_transit(communities)

    # Phase 4: Competitors
    competitors, comp_housing = phase4_competitors()

    # Phase 5: Real estate
    realestate = phase5_realestate(communities)

    # Summary
    print("\n" + "=" * 60)
    print(f"DATA COLLECTION COMPLETE - {call_count} API calls used")
    print("=" * 60)
    print(f"  Communities found: {len(communities)}")
    print(f"  Schools found: {len(schools)}")
    print(f"  School routes computed: {len(school_routes)}")
    print(f"  Transit coverage: {len(transit)} communities")
    print(f"  Competitors found: {len(competitors)}")
    print(f"  Competitor housing analyzed: {len(comp_housing)}")
    print(f"  Real estate data: {len(realestate)} communities")
    print(f"\nAll data saved to: {OUT_DIR}")

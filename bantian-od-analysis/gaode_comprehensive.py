"""
高德API全面数据采集脚本
充分利用高德Web服务API的各类接口
"""
import requests, json, time, os, csv, math
from collections import defaultdict

WORK = r'C:\Users\Administrator\.qoderwork\workspace\mq86irc1jqgzw5w6'
KEY = 'b5470a516f71e53cd79deaa7f2d48ec0'

# 秋港花园中心坐标
CENTER = '114.075434,22.668739'
CENTER_LON = 114.075434
CENTER_LAT = 22.668739

# 坂田片区范围（多边形搜索用）
# 大致范围：114.04-114.12°E, 22.62-22.71°N
BANTIAN_POLYGON = '114.04,22.62|114.12,22.62|114.12,22.71|114.04,22.71'

# 搜索半径
RADIUS = 3000  # 3km

api_calls = 0

def api_get(url, params):
    """统一的API调用接口"""
    global api_calls
    params['key'] = KEY
    params['output'] = 'json'
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        api_calls += 1
        if data.get('status') != '1':
            print(f"  API Error: {data.get('info', 'unknown')} ({url})")
            return None
        return data
    except Exception as e:
        print(f"  Request failed: {e}")
        return None

# ============================================================
# 1. 周边搜索：全面采集各类POI
# ============================================================
print("=" * 60)
print("1. 周边搜索 (Nearby Search)")
print("=" * 60)

# 搜索类型（高德POI类型编码 + 关键字）
nearby_categories = [
    # 交通设施
    ('公交', '150700', '公交站'),
    ('地铁', '150500', '地铁站'),
    ('停车场', '150900', '停车场'),
    ('加油站', '010100', '加油站'),
    ('充电站', '011100', '充电站'),
    # 教育设施
    ('小学', '141203', '小学'),
    ('中学', '141204', '中学'),
    ('幼儿园', '141201', '幼儿园'),
    ('大学', '141202', '大学'),
    ('培训学校', '141205', '培训机构'),
    # 医疗设施
    ('医院', '090100', '综合医院'),
    ('社区医院', '090200', '社区医院'),
    ('诊所', '090300', '诊所'),
    ('药店', '090600', '药店'),
    ('体检中心', '090400', '体检中心'),
    # 商业服务
    ('超市', '060400', '超市'),
    ('便利店', '060200', '便利店'),
    ('商场', '060100', '商场'),
    ('菜市场', '060700', '菜市场'),
    ('餐饮', '050000', '餐饮'),
    ('咖啡厅', '050500', '咖啡厅'),
    ('银行', '160100', '银行'),
    ('ATM', '160300', 'ATM'),
    # 生活服务
    ('公园', '110100', '公园'),
    ('广场', '110105', '广场'),
    ('体育场馆', '080100', '体育场馆'),
    ('健身房', '080104', '健身房'),
    ('电影院', '080601', '电影院'),
    ('图书馆', '140100', '图书馆'),
    ('文化活动中心', '140200', '文化宫'),
    # 住宅
    ('住宅小区', '120300', '住宅区'),
    ('写字楼', '120200', '写字楼'),
    # 政府
    ('政府机构', '130100', '政府机关'),
    ('派出所', '130400', '公安'),
    ('居委会', '130600', '居委会'),
    # 企业
    ('产业园区', '120100', '产业园区'),
]

all_nearby_pois = {}  # category_name -> [poi_list]

for keyword, typecode, label in nearby_categories:
    pois = []
    page = 1
    while page <= 3:  # 最多3页（每页25条）
        data = api_get('https://restapi.amap.com/v3/place/around', {
            'location': CENTER,
            'keywords': keyword,
            'types': typecode,
            'radius': RADIUS,
            'offset': 25,
            'page': page,
            'extensions': 'all',
            'sortrule': 'distance',
        })
        if not data or not data.get('pois'):
            break
        for p in data['pois']:
            pois.append({
                'id': p.get('id', ''),
                'name': p.get('name', ''),
                'address': p.get('address', ''),
                'tel': p.get('tel', ''),
                'type': p.get('type', ''),
                'typecode': p.get('typecode', ''),
                'location': p.get('location', ''),
                'lon': float(p['location'].split(',')[0]) if ',' in p.get('location', '') else 0,
                'lat': float(p['location'].split(',')[1]) if ',' in p.get('location', '') else 0,
                'distance': p.get('distance', ''),
                'biz_ext': p.get('biz_ext', {}),
                'photos': len(p.get('photos', [])),
                'business_area': p.get('business_area', ''),
                'citycode': p.get('citycode', ''),
                'adcode': p.get('adcode', ''),
                'opentime': p.get('biz_ext', {}).get('opentime', '') if isinstance(p.get('biz_ext'), dict) else '',
                'rating': p.get('biz_ext', {}).get('rating', '') if isinstance(p.get('biz_ext'), dict) else '',
                'cost': p.get('biz_ext', {}).get('cost', '') if isinstance(p.get('biz_ext'), dict) else '',
                'search_keyword': keyword,
                'category_label': label,
            })
        if len(data['pois']) < 25:
            break
        page += 1
        time.sleep(0.1)
    
    all_nearby_pois[label] = pois
    total = len(pois)
    print(f"  {label}: {total} 个")

# ============================================================
# 2. 关键字搜索：更大范围搜索坂田片区
# ============================================================
print("\n" + "=" * 60)
print("2. 关键字搜索 (Keyword Search)")
print("=" * 60)

keyword_searches = [
    ('坂田 学校', '教育设施'),
    ('坂田 公园', '公园绿地'),
    ('坂田 地铁站', '地铁站'),
    ('坂田 公交', '公交站'),
    ('坂田 医院', '医疗设施'),
    ('坂田 幼儿园', '幼儿园'),
    ('坂田 商场', '商场'),
    ('坂田 菜市场', '菜市场'),
    ('坂田 图书馆', '图书馆'),
    ('坂田 体育馆', '体育场馆'),
    ('坂田 社区服务中心', '社区服务'),
    ('华为 宿舍', '华为宿舍'),
    ('天安云谷', '天安云谷'),
    ('秋港花园', '秋港花园'),
    ('坂田 万科', '万科楼盘'),
    ('坂田 佳兆业', '佳兆业楼盘'),
]

keyword_pois = {}
for query, label in keyword_searches:
    data = api_get('https://restapi.amap.com/v3/place/text', {
        'keywords': query,
        'city': '深圳',
        'citylimit': 'true',
        'offset': 25,
        'page': 1,
        'extensions': 'all',
    })
    if data and data.get('pois'):
        pois = []
        for p in data['pois']:
            loc = p.get('location', '')
            if ',' in loc:
                lon, lat = float(loc.split(',')[0]), float(loc.split(',')[1])
                # 只保留坂田范围内的
                if 114.02 <= lon <= 114.14 and 22.60 <= lat <= 22.72:
                    pois.append({
                        'id': p.get('id', ''),
                        'name': p.get('name', ''),
                        'address': p.get('address', ''),
                        'tel': p.get('tel', ''),
                        'type': p.get('type', ''),
                        'lon': lon,
                        'lat': lat,
                        'adcode': p.get('adcode', ''),
                        'search_query': query,
                        'category_label': label,
                    })
        keyword_pois[label] = pois
        print(f"  '{query}': {len(pois)} 个 (坂田范围内)")
    time.sleep(0.1)

# ============================================================
# 3. 行政区查询：获取坂田街道边界
# ============================================================
print("\n" + "=" * 60)
print("3. 行政区查询 (District Query)")
print("=" * 60)

data = api_get('https://restapi.amap.com/v3/config/district', {
    'keywords': '坂田街道',
    'subdistrict': 0,
    'extensions': 'all',
})
bantian_boundary = None
if data and data.get('districts'):
    dist = data['districts'][0]
    print(f"  名称: {dist.get('name')}")
    print(f"  级别: {dist.get('level')}")
    print(f"  中心: {dist.get('center')}")
    print(f"  编码: {dist.get('adcode')}")
    polyline = dist.get('polyline', '')
    if polyline:
        # 解析边界线
        rings = polyline.split('|')
        bantian_boundary = []
        for ring in rings:
            coords = []
            for pt in ring.split(';'):
                parts = pt.split(',')
                if len(parts) == 2:
                    coords.append((float(parts[0]), float(parts[1])))
            if coords:
                bantian_boundary.append(coords)
        print(f"  边界: {len(bantian_boundary)} 段, 共{sum(len(r) for r in bantian_boundary)}个点")

# ============================================================
# 4. 步行路径规划：秋港花园 → 各类代表性设施
# ============================================================
print("\n" + "=" * 60)
print("4. 步行路径规划 (Walking Route)")
print("=" * 60)

# 选取代表性目的地
route_destinations = []

# 从周边搜索结果中选取
for label, pois in all_nearby_pois.items():
    if pois:
        # 选最近的和稍远的各1个
        sorted_pois = sorted(pois, key=lambda p: float(p.get('distance', 99999)))
        if sorted_pois[0]['lon'] > 0:
            route_destinations.append({
                'name': sorted_pois[0]['name'],
                'category': label,
                'lon': sorted_pois[0]['lon'],
                'lat': sorted_pois[0]['lat'],
                'location': sorted_pois[0]['location'],
            })
        # 如果有多个，再加一个远的
        if len(sorted_pois) > 5:
            far_poi = sorted_pois[min(len(sorted_pois)-1, 10)]
            if far_poi['lon'] > 0 and far_poi['name'] != sorted_pois[0]['name']:
                route_destinations.append({
                    'name': far_poi['name'],
                    'category': label,
                    'lon': far_poi['lon'],
                    'lat': far_poi['lat'],
                    'location': far_poi['location'],
                })

walking_routes = []
for dest in route_destinations[:40]:  # 最多40个步行路径
    data = api_get('https://restapi.amap.com/v3/direction/walking', {
        'origin': CENTER,
        'destination': dest['location'],
    })
    if data and data.get('route') and data['route'].get('paths'):
        path = data['route']['paths'][0]
        walking_routes.append({
            'origin': '秋港花园',
            'destination': dest['name'],
            'category': dest['category'],
            'dest_lon': dest['lon'],
            'dest_lat': dest['lat'],
            'distance_m': int(path.get('distance', 0)),
            'duration_s': int(path.get('duration', 0)),
            'duration_min': round(int(path.get('duration', 0)) / 60, 1),
            'steps_count': len(path.get('steps', [])),
        })
        print(f"  步行 → {dest['name']}: {path.get('distance')}m, "
              f"{round(int(path.get('duration',0))/60,1)}min")
    time.sleep(0.05)

# ============================================================
# 5. 公交路径规划：秋港花园 → 医院/地铁站/学校
# ============================================================
print("\n" + "=" * 60)
print("5. 公交路径规划 (Transit Route)")
print("=" * 60)

transit_targets = []
# 医院
for label in ['综合医院', '社区医院', '医疗设施']:
    for p in all_nearby_pois.get(label, [])[:3]:
        if p['lon'] > 0:
            transit_targets.append({'name': p['name'], 'category': '医院', 
                                   'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 地铁站
for p in all_nearby_pois.get('地铁站', [])[:5]:
    if p['lon'] > 0:
        transit_targets.append({'name': p['name'], 'category': '地铁站',
                               'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 学校
for label in ['小学', '中学', '幼儿园', '教育设施']:
    for p in all_nearby_pois.get(label, [])[:3]:
        if p['lon'] > 0:
            transit_targets.append({'name': p['name'], 'category': '教育',
                                   'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 公园
for p in all_nearby_pois.get('公园', [])[:3]:
    if p['lon'] > 0:
        transit_targets.append({'name': p['name'], 'category': '公园',
                               'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})

# 去重
seen_names = set()
unique_targets = []
for t in transit_targets:
    if t['name'] not in seen_names:
        seen_names.add(t['name'])
        unique_targets.append(t)
transit_targets = unique_targets[:25]

transit_routes = []
for target in transit_targets:
    data = api_get('https://restapi.amap.com/v3/direction/transit/integrated', {
        'origin': CENTER,
        'destination': target['location'],
        'city': '深圳',
        'strategy': 0,  # 最快捷
    })
    if data and data.get('route') and data['route'].get('transits'):
        transit = data['route']['transits'][0]
        transit_routes.append({
            'origin': '秋港花园',
            'destination': target['name'],
            'category': target['category'],
            'dest_lon': target['lon'],
            'dest_lat': target['lat'],
            'distance_m': int(data['route'].get('distance', 0)),
            'duration_min': round(int(transit.get('duration', 0)) / 60, 1),
            'walking_distance_m': int(transit.get('walking_distance', 0)),
            'cost': transit.get('cost', ''),
            'nightflag': transit.get('nightflag', '0'),
            'segments_count': len(transit.get('segments', [])),
            # 解析公交方式
            'bus_lines': ';'.join([
                seg.get('bus', {}).get('buslines', [{}])[0].get('name', '')
                for seg in transit.get('segments', [])
                if seg.get('bus', {}).get('buslines')
            ]),
            'metro_used': any(
                '地铁' in seg.get('bus', {}).get('buslines', [{}])[0].get('name', '')
                for seg in transit.get('segments', [])
                if seg.get('bus', {}).get('buslines')
            ),
        })
        bus_info = transit_routes[-1]['bus_lines'] or '无公交'
        print(f"  公交 → {target['name']}: {transit_routes[-1]['distance_m']}m, "
              f"{transit_routes[-1]['duration_min']}min [{bus_info}]")
    time.sleep(0.05)

# ============================================================
# 6. 驾车路径规划：秋港花园 → 远距离设施
# ============================================================
print("\n" + "=" * 60)
print("6. 驾车路径规划 (Driving Route)")
print("=" * 60)

driving_targets = []
# 三甲医院
for p in all_nearby_pois.get('综合医院', [])[:5]:
    if p['lon'] > 0:
        driving_targets.append({'name': p['name'], 'category': '医院',
                               'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 远距离地铁站
for p in all_nearby_pois.get('地铁站', [])[:3]:
    if p['lon'] > 0:
        driving_targets.append({'name': p['name'], 'category': '地铁站',
                               'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 商场
for p in all_nearby_pois.get('商场', [])[:3]:
    if p['lon'] > 0:
        driving_targets.append({'name': p['name'], 'category': '商场',
                               'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})
# 学校
for label in ['小学', '中学']:
    for p in all_nearby_pois.get(label, [])[:2]:
        if p['lon'] > 0:
            driving_targets.append({'name': p['name'], 'category': '教育',
                                   'location': p['location'], 'lon': p['lon'], 'lat': p['lat']})

driving_routes = []
seen = set()
for target in driving_targets:
    if target['name'] in seen:
        continue
    seen.add(target['name'])
    
    data = api_get('https://restapi.amap.com/v3/direction/driving', {
        'origin': CENTER,
        'destination': target['location'],
        'strategy': 0,
    })
    if data and data.get('route') and data['route'].get('paths'):
        path = data['route']['paths'][0]
        driving_routes.append({
            'origin': '秋港花园',
            'destination': target['name'],
            'category': target['category'],
            'dest_lon': target['lon'],
            'dest_lat': target['lat'],
            'distance_m': int(path.get('distance', 0)),
            'duration_min': round(int(path.get('duration', 0)) / 60, 1),
            'toll_cost': path.get('tolls', ''),
            'traffic_lights': path.get('traffic_lights', ''),
            'strategy': path.get('strategy', ''),
        })
        print(f"  驾车 → {target['name']}: {path.get('distance')}m, "
              f"{round(int(path.get('duration',0))/60,1)}min, "
              f"红绿灯{path.get('traffic_lights','?')}个")
    time.sleep(0.05)

# ============================================================
# 7. 公交站点详细查询
# ============================================================
print("\n" + "=" * 60)
print("7. 公交站点查询 (Bus Station)")
print("=" * 60)

bus_stations = []
for p in all_nearby_pois.get('公交站', []):
    if p.get('id'):
        data = api_get('https://restapi.amap.com/v3/bus/stopid', {
            'id': p['id'],
            'city': '深圳',
        })
        if data and data.get('busstops'):
            for bs in data['busstops']:
                buslines = bs.get('buslines', [])
                bus_stations.append({
                    'name': bs.get('name', ''),
                    'location': bs.get('location', ''),
                    'lon': float(bs['location'].split(',')[0]) if ',' in bs.get('location', '') else 0,
                    'lat': float(bs['location'].split(',')[1]) if ',' in bs.get('location', '') else 0,
                    'buslines_count': len(buslines),
                    'buslines_names': ';'.join([bl.get('name', '') for bl in buslines]),
                    'buslines_types': ';'.join([bl.get('type', '') for bl in buslines]),
                })
                print(f"  {bs.get('name')}: {len(buslines)}条线路 "
                      f"({';'.join([bl.get('name','')[:10] for bl in buslines[:5]])})")
        time.sleep(0.05)

# ============================================================
# 8. 保存所有数据
# ============================================================
print("\n" + "=" * 60)
print("8. 保存数据")
print("=" * 60)

OUT = os.path.join(WORK, 'gaode_comprehensive')
os.makedirs(OUT, exist_ok=True)

# 周边搜索POI
with open(os.path.join(OUT, 'nearby_pois.json'), 'w', encoding='utf-8') as f:
    json.dump(all_nearby_pois, f, ensure_ascii=False, indent=2)
total_nearby = sum(len(v) for v in all_nearby_pois.values())
print(f"  周边搜索POI: {total_nearby} 个")

# 关键字搜索POI
with open(os.path.join(OUT, 'keyword_pois.json'), 'w', encoding='utf-8') as f:
    json.dump(keyword_pois, f, ensure_ascii=False, indent=2)
total_keyword = sum(len(v) for v in keyword_pois.values())
print(f"  关键字搜索POI: {total_keyword} 个")

# 行政区边界
if bantian_boundary:
    with open(os.path.join(OUT, 'bantian_boundary.json'), 'w', encoding='utf-8') as f:
        json.dump(bantian_boundary, f, ensure_ascii=False, indent=2)
    print(f"  坂田边界: {len(bantian_boundary)} 段")

# 步行路径
with open(os.path.join(OUT, 'walking_routes.json'), 'w', encoding='utf-8') as f:
    json.dump(walking_routes, f, ensure_ascii=False, indent=2)
print(f"  步行路径: {len(walking_routes)} 条")

# 公交路径
with open(os.path.join(OUT, 'transit_routes.json'), 'w', encoding='utf-8') as f:
    json.dump(transit_routes, f, ensure_ascii=False, indent=2)
print(f"  公交路径: {len(transit_routes)} 条")

# 驾车路径
with open(os.path.join(OUT, 'driving_routes.json'), 'w', encoding='utf-8') as f:
    json.dump(driving_routes, f, ensure_ascii=False, indent=2)
print(f"  驾车路径: {len(driving_routes)} 条")

# 公交站点
with open(os.path.join(OUT, 'bus_stations.json'), 'w', encoding='utf-8') as f:
    json.dump(bus_stations, f, ensure_ascii=False, indent=2)
print(f"  公交站点详情: {len(bus_stations)} 个")

# CSV导出
# 步行OD
if walking_routes:
    with open(os.path.join(OUT, 'walking_od.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=walking_routes[0].keys())
        w.writeheader()
        w.writerows(walking_routes)

# 公交OD
if transit_routes:
    with open(os.path.join(OUT, 'transit_od.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=transit_routes[0].keys())
        w.writeheader()
        w.writerows(transit_routes)

# 驾车OD
if driving_routes:
    with open(os.path.join(OUT, 'driving_od.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=driving_routes[0].keys())
        w.writeheader()
        w.writerows(driving_routes)

# 综合POI CSV
all_pois_flat = []
for label, pois in all_nearby_pois.items():
    for p in pois:
        p['source_type'] = 'nearby'
        all_pois_flat.append(p)
for label, pois in keyword_pois.items():
    for p in pois:
        p['source_type'] = 'keyword'
        p['category_label'] = label
        all_pois_flat.append(p)

if all_pois_flat:
    # 统一字段
    fieldnames = ['id', 'name', 'address', 'tel', 'type', 'lon', 'lat',
                  'distance', 'adcode', 'category_label', 'source_type']
    with open(os.path.join(OUT, 'all_pois.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for p in all_pois_flat:
            w.writerow(p)

print(f"  综合POI: {len(all_pois_flat)} 个")

# API使用统计
print(f"\n{'='*60}")
print(f"API调用统计: {api_calls} 次")
print(f"{'='*60}")

# 摘要
print("\n采集摘要:")
print(f"  周边搜索: {len(all_nearby_pois)} 类, {total_nearby} 个POI")
print(f"  关键字搜索: {len(keyword_pois)} 类, {total_keyword} 个POI")
print(f"  坂田边界: {'有' if bantian_boundary else '无'}")
print(f"  步行OD: {len(walking_routes)} 条 (秋港花园 → 各类设施)")
print(f"  公交OD: {len(transit_routes)} 条 (含公交线路信息)")
print(f"  驾车OD: {len(driving_routes)} 条 (含红绿灯/过路费)")
print(f"  公交站点详情: {len(bus_stations)} 个 (含线路列表)")

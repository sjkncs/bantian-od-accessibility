"""
秋港花园GIS课程作业 —— 多设施可达性OD矩阵分析
扩展：住宅小区 → 商业/交通/教育/公园/社康 的OD矩阵
结合"新型单位大院"研究主题的空间治理分析
"""
import json, os, sys, math, csv, sqlite3, time
import numpy as np
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import nearest_points
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib import cm
from collections import defaultdict

# ============================================================
# 配置
# ============================================================
WORK = r'C:\Users\Administrator\.qoderwork\workspace\mq86irc1jqgzw5w6'
OUT = os.path.join(WORK, 'coursework')
SHP = os.path.join(OUT, 'shapefiles_cgcs2000')
FIG = os.path.join(OUT, 'figures')
DB  = os.path.join(OUT, 'database')

for d in [OUT, SHP, FIG, DB]:
    os.makedirs(d, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# CGCS2000 3度带 第38带 (中央经线114°)
CGCS2000_3D_38 = 'EPSG:4547'

# ============================================================
# WGS84 -> CGCS2000 3度38带 (手动高斯克吕格)
# ============================================================
def wgs84_to_cgcs2000(lon, lat):
    import math
    a = 6378137.0
    f = 1/298.257222101
    b = a * (1 - f)
    e2 = (a**2 - b**2) / a**2
    e_prime2 = (a**2 - b**2) / b**2
    lon0 = math.radians(114.0)
    lat_r = math.radians(lat)
    dlon = math.radians(lon) - lon0
    N = a / math.sqrt(1 - e2 * math.sin(lat_r)**2)
    T = math.tan(lat_r)**2
    C = e_prime2 * math.cos(lat_r)**2
    A = math.cos(lat_r) * dlon
    M = a * ((1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_r
             - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_r)
             + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_r)
             - (35*e2**3/3072) * math.sin(6*lat_r))
    x = N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C)*A**5/120)
    y = M + N * math.tan(lat_r) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24
                                     + (61-58*T+T**2+600*C-330*e_prime2)*A**6/720)
    easting = 38500000.0 + x
    northing = y
    return easting, northing

# ============================================================
# 1. 从数据库加载已有网络和小区数据
# ============================================================
print("=" * 60)
print("1. 加载已有数据")
print("=" * 60)

db_path = os.path.join(DB, 'bantian_transport_network.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 加载网络节点
cur.execute("SELECT node_id, easting, northing FROM network_nodes")
node_rows = cur.fetchall()
print(f"  网络节点: {len(node_rows)}")

# 加载网络边
cur.execute("SELECT from_node, to_node, length_m, travel_time_min FROM roads")
edge_rows = cur.fetchall()
print(f"  网络边: {len(edge_rows)}")

# 加载小区
cur.execute("SELECT community_id, name, lon_wgs84, lat_wgs84, easting, northing, network_node FROM communities")
communities = cur.fetchall()
print(f"  住宅小区: {len(communities)}")

# 重建图
G = nx.Graph()
node_map = {}  # node_id -> (easting, northing)
for row in node_rows:
    nid, e, n = row
    G.add_node(nid, easting=e, northing=n)
    node_map[nid] = (e, n)

for row in edge_rows:
    fn, tn, length, ttime = row
    if fn in G and tn in G:
        G.add_edge(fn, tn, weight=length, length_m=length, travel_time_min=ttime)

print(f"  图重建完成: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# 检查连通性
components = list(nx.connected_components(G))
print(f"  连通分量: {len(components)}")
if len(components) > 1:
    largest = max(components, key=len)
    print(f"  最大连通分量: {len(largest)} nodes")
    G_main = G.subgraph(largest).copy()
else:
    G_main = G

conn.close()

# ============================================================
# 2. 整合POI数据：OSM + 高德
# ============================================================
print("\n" + "=" * 60)
print("2. 整合多源POI数据")
print("=" * 60)

# --- 高德POI ---
gaode_pois = []
gaode_csv = os.path.join(WORK, 'gaode_poi_qiugang.csv')
with open(gaode_csv, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lon = float(row['lon'])
            lat = float(row['lat'])
            name = row['name']
            category = row.get('category', '')
            search_keyword = row.get('search_keyword', '')
            gaode_pois.append({
                'name': name,
                'lon': lon,
                'lat': lat,
                'category': category,
                'search_keyword': search_keyword,
                'source': 'gaode',
                'type': row.get('type', ''),
                'address': row.get('address', ''),
                'tel': row.get('tel', ''),
                'opentime': row.get('opentime', '')
            })
        except:
            pass

print(f"  高德POI: {len(gaode_pois)}")

# --- OSM POI ---
osm_pois = []
osm_csv = os.path.join(WORK, 'outputs', 'qiugang_gis', 'qiugang_poi_analysis.csv')
with open(osm_csv, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lon = float(row['lon'])
            lat = float(row['lat'])
            name = row['name']
            category = row.get('category', '其他')
            osm_pois.append({
                'name': name,
                'lon': lon,
                'lat': lat,
                'category': category,
                'source': 'osm',
                'amenity': row.get('amenity', ''),
                'shop': row.get('shop', ''),
                'leisure': row.get('leisure', '')
            })
        except:
            pass

print(f"  OSM POI: {len(osm_pois)}")

# ============================================================
# 3. POI分类体系（面向"15分钟生活圈"）
# ============================================================
print("\n" + "=" * 60)
print("3. POI分类与筛选")
print("=" * 60)

# 定义分类规则
def classify_poi(poi):
    """将POI归入生活服务体系列"""
    src = poi['source']
    cat = poi.get('category', '')
    sk = poi.get('search_keyword', '')
    amenity = poi.get('amenity', '')
    shop = poi.get('shop', '')
    leisure = poi.get('leisure', '')
    name = poi['name']
    poi_type = poi.get('type', '')
    
    # --- 地铁站 ---
    if src == 'osm' and cat == '交通设施':
        if '地铁' in name or '站' in name and ('地铁' in str(poi) or 'metro' in str(poi).lower()):
            return '地铁站'
        if amenity == 'bus_stop' or '公交' in name:
            return '公交站'
        return '公交站'  # OSM交通设施大多是公交站
    
    if src == 'osm' and '地铁' in name:
        return '地铁站'
    
    # --- 高德分类 ---
    if src == 'gaode':
        # 商业服务
        if cat == '商业服务' or sk in ['餐饮', '便利店', '超市']:
            if sk == '餐饮':
                return '餐饮'
            elif sk in ['便利店', '超市']:
                return '商超便利店'
            else:
                return '商业服务'
        
        # 公园绿地
        if sk == '公园' or '公园' in name or '园' in name and '花' not in name:
            return '公园绿地'
        
        # 教育
        if sk in ['小学', '中学'] or '学校' in name or '幼儿园' in name or '小学' in name:
            return '教育设施'
        
        # 银行
        if sk == '银行' or '银行' in name:
            return '银行网点'
        
        # 社康/诊所（非三甲医院）
        if sk in ['诊所', '口腔'] or '社康' in name or '诊所' in name:
            return '社康诊所'
        
        # 酒店（反映商业活力）
        if '住宿' in cat or sk == '酒店':
            return '住宿服务'
    
    # --- OSM分类 ---
    if src == 'osm':
        if cat == '商业服务':
            return '餐饮'
        if cat == '休闲文体':
            if '酒店' in name or 'hotel' in name.lower():
                return '住宿服务'
            return '休闲文体'
        if cat == '教育设施':
            return '教育设施'
        if cat == '公共服务':
            if '银行' in name:
                return '银行网点'
            return '公共服务'
    
    return None  # 不纳入分析

# 执行分类
classified = defaultdict(list)  # category -> [poi_list]
unclassified = 0

all_pois = gaode_pois + osm_pois
for poi in all_pois:
    cls = classify_poi(poi)
    if cls:
        classified[cls].append(poi)
    else:
        unclassified += 1

# 合并相近类别
# 餐饮 + 商业服务 -> 餐饮商业
# 银行网点 -> 并入商业
merged = defaultdict(list)
for cls, pois in classified.items():
    if cls in ['餐饮', '商业服务']:
        merged['餐饮商业'].extend(pois)
    elif cls == '商超便利店':
        merged['商超便利店'].extend(pois)
    elif cls == '地铁站':
        merged['地铁站'].extend(pois)
    elif cls == '公交站':
        merged['公交站'].extend(pois)
    elif cls == '公园绿地':
        merged['公园绿地'].extend(pois)
    elif cls == '教育设施':
        merged['教育设施'].extend(pois)
    elif cls == '社康诊所':
        merged['社康诊所'].extend(pois)
    elif cls == '银行网点':
        merged['银行网点'].extend(pois)
    elif cls == '住宿服务':
        merged['住宿服务'].extend(pois)
    elif cls == '休闲文体':
        merged['休闲文体'].extend(pois)
    elif cls == '公共服务':
        merged['公共服务'].extend(pois)
    else:
        merged[cls].extend(pois)

# 去重（按坐标，50m内同名视为重复）
for cat in merged:
    unique = []
    seen = set()
    for p in merged[cat]:
        key = (round(p['lon'], 4), round(p['lat'], 4), p['name'])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    merged[cat] = unique

print("  分类结果:")
for cat in sorted(merged.keys()):
    print(f"    {cat}: {len(merged[cat])} 个设施")
print(f"  未分类: {unclassified}")

# 选择用于OD分析的核心类别
OD_CATEGORIES = {
    '餐饮商业': merged.get('餐饮商业', []),
    '商超便利店': merged.get('商超便利店', []),
    '地铁站': merged.get('地铁站', []),
    '公交站': merged.get('公交站', []),
    '公园绿地': merged.get('公园绿地', []),
    '教育设施': merged.get('教育设施', []),
    '社康诊所': merged.get('社康诊所', []),
}

# 过滤掉数量太少的类别
OD_CATEGORIES = {k: v for k, v in OD_CATEGORIES.items() if len(v) >= 2}
print(f"\n  纳入OD分析的类别: {list(OD_CATEGORIES.keys())}")

# ============================================================
# 4. POI吸附到网络 & 计算OD矩阵
# ============================================================
print("\n" + "=" * 60)
print("4. 多设施OD矩阵计算")
print("=" * 60)

def snap_to_network(lon, lat, G_main):
    """将POI吸附到最近的网络节点"""
    e, n = wgs84_to_cgcs2000(lon, lat)
    best_node = None
    best_dist = float('inf')
    for node in G_main.nodes():
        ne, nn = node_map[node]
        d = math.sqrt((e - ne)**2 + (n - nn)**2)
        if d < best_dist:
            best_dist = d
            best_node = node
    return best_node, best_dist

# 小区数据准备
comm_data = []
for row in communities:
    cid, name, lon, lat, e, n, net_node = row
    comm_data.append({
        'id': cid, 'name': name, 'lon': lon, 'lat': lat,
        'easting': e, 'northing': n, 'network_node': net_node
    })

# --- 预吸附所有类别POI到网络 ---
cat_poi_nodes = {}  # cat_name -> [{name, lon, lat, network_node, snap_dist}]
for cat_name, pois in OD_CATEGORIES.items():
    poi_nodes = []
    for p in pois:
        node, dist = snap_to_network(p['lon'], p['lat'], G_main)
        if node is not None and dist < 1000:
            poi_nodes.append({
                'name': p['name'],
                'lon': p['lon'],
                'lat': p['lat'],
                'network_node': node,
                'snap_dist': dist
            })
    cat_poi_nodes[cat_name] = poi_nodes
    print(f"  {cat_name}: {len(poi_nodes)}/{len(pois)} 有效吸附")

# --- 核心优化：从每个小区节点做一次单源Dijkstra ---
print("\n  预计算单源Dijkstra (175个小区)...")
comm_distances = {}  # comm_id -> {target_node: distance}
t0 = time.time()
for i, comm in enumerate(comm_data):
    comm_node = comm['network_node']
    if comm_node is None or comm_node not in G_main:
        continue
    try:
        dists = nx.single_source_dijkstra_path_length(G_main, comm_node, weight='weight')
        comm_distances[comm['id']] = dists
    except:
        pass
    if (i + 1) % 50 == 0:
        print(f"    {i+1}/{len(comm_data)} 完成 ({time.time()-t0:.1f}s)")

print(f"  单源Dijkstra完成: {len(comm_distances)} 个小区, 耗时 {time.time()-t0:.1f}s")

# --- 基于预计算距离生成各类OD矩阵 ---
all_od_results = {}
all_od_stats = {}

for cat_name, poi_nodes in cat_poi_nodes.items():
    if not poi_nodes:
        continue
    
    print(f"\n  --- {cat_name} ({len(poi_nodes)} 个设施) ---")
    
    od_cat = []
    dists_per_comm = {}
    
    for comm in comm_data:
        cid = comm['id']
        if cid not in comm_distances:
            continue
        
        dist_map = comm_distances[cid]
        min_dist = float('inf')
        min_poi = None
        
        for pn in poi_nodes:
            pnode = pn['network_node']
            if pnode in dist_map:
                dist = dist_map[pnode]
                od_cat.append({
                    'community_id': comm['id'],
                    'community_name': comm['name'],
                    'community_lon': comm['lon'],
                    'community_lat': comm['lat'],
                    'community_easting': comm['easting'],
                    'community_northing': comm['northing'],
                    'poi_name': pn['name'],
                    'poi_lon': pn['lon'],
                    'poi_lat': pn['lat'],
                    'distance_m': round(dist, 1),
                    'category': cat_name
                })
                if dist < min_dist:
                    min_dist = dist
                    min_poi = pn['name']
        
        dists_per_comm[comm['name']] = {
            'min_dist': min_dist if min_dist < float('inf') else None,
            'nearest': min_poi
        }
    
    all_od_results[cat_name] = od_cat
    
    # 统计
    min_dists = [v['min_dist'] for v in dists_per_comm.values() if v['min_dist'] is not None]
    if min_dists:
        stats = {
            'count': len(poi_nodes),
            'avg': round(np.mean(min_dists), 0),
            'min': round(np.min(min_dists), 0),
            'max': round(np.max(min_dists), 0),
            'median': round(np.median(min_dists), 0),
            'within_1km': sum(1 for d in min_dists if d <= 1000),
            'within_2km': sum(1 for d in min_dists if d <= 2000),
            'total_comm': len(dists_per_comm)
        }
        all_od_stats[cat_name] = stats
        print(f"    最近设施距离: 均值={stats['avg']}m, 中位={stats['median']}m, "
              f"最大={stats['max']}m")
        print(f"    1km覆盖: {stats['within_1km']}/{stats['total_comm']} "
              f"({100*stats['within_1km']/stats['total_comm']:.0f}%)")
        print(f"    2km覆盖: {stats['within_2km']}/{stats['total_comm']} "
              f"({100*stats['within_2km']/stats['total_comm']:.0f}%)")

# ============================================================
# 5. 写入数据库和CSV
# ============================================================
print("\n" + "=" * 60)
print("5. 数据存储")
print("=" * 60)

db_path2 = os.path.join(DB, 'bantian_multi_service_od.db')
if os.path.exists(db_path2):
    os.remove(db_path2)

conn2 = sqlite3.connect(db_path2)
cur2 = conn2.cursor()

# 复制原表结构
conn_orig = sqlite3.connect(db_path)
for table in ['roads', 'network_nodes', 'hospitals', 'communities']:
    # 读取建表SQL
    cur_orig = conn_orig.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
    create_sql = cur_orig.fetchone()[0]
    cur2.execute(create_sql)
    rows = conn_orig.execute(f"SELECT * FROM {table}").fetchall()
    placeholders = ','.join(['?'] * len(rows[0])) if rows else ''
    if rows:
        cur2.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
conn_orig.close()

# 创建多设施OD表
cur2.execute('''CREATE TABLE IF NOT EXISTS od_multi_service (
    id INTEGER PRIMARY KEY,
    category TEXT,
    community_id INTEGER,
    community_name TEXT,
    community_lon REAL,
    community_lat REAL,
    community_easting REAL,
    community_northing REAL,
    poi_name TEXT,
    poi_lon REAL,
    poi_lat REAL,
    distance_m REAL
)''')

od_id = 0
for cat_name, records in all_od_results.items():
    for r in records:
        od_id += 1
        cur2.execute('''INSERT INTO od_multi_service VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (od_id, r['category'], r['community_id'], r['community_name'],
                      r['community_lon'], r['community_lat'],
                      r['community_easting'], r['community_northing'],
                      r['poi_name'], r['poi_lon'], r['poi_lat'], r['distance_m']))

conn2.commit()
print(f"  多设施OD记录: {od_id}")

# 创建POI设施表
cur2.execute('''CREATE TABLE IF NOT EXISTS poi_facilities (
    id INTEGER PRIMARY KEY,
    category TEXT,
    name TEXT,
    lon REAL,
    lat REAL,
    easting REAL,
    northing REAL,
    network_node INTEGER,
    source TEXT
)''')

poi_id = 0
for cat_name, pois in OD_CATEGORIES.items():
    for p in pois:
        e, n = wgs84_to_cgcs2000(p['lon'], p['lat'])
        poi_id += 1
        cur2.execute('''INSERT INTO poi_facilities VALUES (?,?,?,?,?,?,?,?,?)''',
                     (poi_id, cat_name, p['name'], p['lon'], p['lat'], e, n, None, p['source']))

conn2.commit()
print(f"  POI设施记录: {poi_id}")

# 创建统计表
cur2.execute('''CREATE TABLE IF NOT EXISTS od_statistics (
    category TEXT PRIMARY KEY,
    facility_count INTEGER,
    avg_min_dist_m REAL,
    median_min_dist_m REAL,
    max_min_dist_m REAL,
    min_min_dist_m REAL,
    within_1km_pct REAL,
    within_2km_pct REAL,
    total_communities INTEGER
)''')

for cat_name, stats in all_od_stats.items():
    cur2.execute('''INSERT OR REPLACE INTO od_statistics VALUES (?,?,?,?,?,?,?,?,?)''',
                 (cat_name, stats['count'], stats['avg'], stats['median'],
                  stats['max'], stats['min'],
                  round(100*stats['within_1km']/stats['total_comm'], 1),
                  round(100*stats['within_2km']/stats['total_comm'], 1),
                  stats['total_comm']))

conn2.commit()
conn2.close()

# 导出CSV
csv_path = os.path.join(DB, 'od_multi_service.csv')
with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['category', 'community_name', 'community_lon', 'community_lat',
                     'poi_name', 'poi_lon', 'poi_lat', 'distance_m'])
    for cat_name, records in all_od_results.items():
        for r in records:
            writer.writerow([r['category'], r['community_name'],
                           r['community_lon'], r['community_lat'],
                           r['poi_name'], r['poi_lon'], r['poi_lat'],
                           r['distance_m']])

# 导出统计摘要
stats_csv = os.path.join(DB, 'od_statistics_summary.csv')
with open(stats_csv, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['设施类别', '设施数量', '最近距离均值(m)', '最近距离中位(m)',
                     '最近距离最大(m)', '1km覆盖率(%)', '2km覆盖率(%)'])
    for cat_name, stats in all_od_stats.items():
        writer.writerow([cat_name, stats['count'], stats['avg'], stats['median'],
                        stats['max'],
                        round(100*stats['within_1km']/stats['total_comm'], 1),
                        round(100*stats['within_2km']/stats['total_comm'], 1)])

print(f"  CSV导出完成")

# ============================================================
# 6. 专题图生成
# ============================================================
print("\n" + "=" * 60)
print("6. 生成多设施可达性专题图")
print("=" * 60)

# 加载道路shapefile用于底图
try:
    roads_gdf = gpd.read_file(os.path.join(SHP, 'bantian_roads.shp'))
    has_roads = True
except:
    has_roads = False

# --- 图1: 多设施空间分布图 ---
print("  生成图1: 多设施空间分布...")
fig, ax = plt.subplots(1, 1, figsize=(14, 12))

# 底图道路
if has_roads:
    roads_gdf.plot(ax=ax, color='#d0d0d0', linewidth=0.4, alpha=0.8)

# 小区
comm_e = [c['easting'] for c in comm_data]
comm_n = [c['northing'] for c in comm_data]
ax.scatter(comm_e, comm_n, c='#404040', s=12, alpha=0.4, zorder=2, label=f'住宅小区({len(comm_data)})')

# 各类设施
colors = {
    '餐饮商业': '#e74c3c',
    '商超便利店': '#e67e22',
    '地铁站': '#2980b9',
    '公交站': '#3498db',
    '公园绿地': '#27ae60',
    '教育设施': '#8e44ad',
    '社康诊所': '#1abc9c',
}
markers = {
    '餐饮商业': 'o',
    '商超便利店': 's',
    '地铁站': 'D',
    '公交站': '^',
    '公园绿地': 'P',
    '教育设施': 'v',
    '社康诊所': 'X',
}

for cat_name, pois in OD_CATEGORIES.items():
    es, ns = [], []
    for p in pois:
        e, n = wgs84_to_cgcs2000(p['lon'], p['lat'])
        es.append(e)
        ns.append(n)
    c = colors.get(cat_name, '#999999')
    m = markers.get(cat_name, 'o')
    ax.scatter(es, ns, c=c, s=35, marker=m, alpha=0.7, zorder=3,
              label=f'{cat_name}({len(pois)})', edgecolors='white', linewidths=0.3)

# 标注秋港花园
qg_e, qg_n = wgs84_to_cgcs2000(114.075434, 22.668739)
ax.scatter([qg_e], [qg_n], c='red', s=150, marker='*', zorder=5, edgecolors='black', linewidths=0.5)
ax.annotate('秋港花园', xy=(qg_e, qg_n), fontsize=11, fontweight='bold',
           xytext=(15, 15), textcoords='offset points',
           arrowprops=dict(arrowstyle='->', color='red'),
           color='red')

ax.set_title('坂田片区多设施空间分布图\n(秋港花园周边住宅小区与公共服务设施)', fontsize=14, fontweight='bold')
ax.set_xlabel('东向坐标 (m)', fontsize=10)
ax.set_ylabel('北向坐标 (m)', fontsize=10)
ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'fig4_multi_service_distribution.jpg'), dpi=200, bbox_inches='tight')
plt.close()
print("    fig4 完成")

# --- 图2: 各类设施最近距离箱线图 ---
print("  生成图2: 最近设施距离分布...")
fig, axes = plt.subplots(2, 4, figsize=(20, 10))
axes = axes.flatten()

for idx, (cat_name, records) in enumerate(all_od_results.items()):
    if idx >= len(axes):
        break
    ax = axes[idx]
    
    # 计算每个小区到该类别的最近距离
    min_dists = defaultdict(lambda: float('inf'))
    for r in records:
        cname = r['community_name']
        d = r['distance_m']
        if d < min_dists[cname]:
            min_dists[cname] = d
    
    vals = [v for v in min_dists.values() if v < float('inf')]
    if not vals:
        continue
    
    vals_sorted = sorted(vals)
    
    # 直方图
    ax.hist(vals_sorted, bins=20, color=colors.get(cat_name, '#999999'),
           alpha=0.7, edgecolor='white')
    
    # 统计线
    avg = np.mean(vals)
    med = np.median(vals)
    ax.axvline(avg, color='red', linestyle='--', linewidth=1.5, label=f'均值: {avg:.0f}m')
    ax.axvline(med, color='blue', linestyle=':', linewidth=1.5, label=f'中位: {med:.0f}m')
    ax.axvline(1000, color='green', linestyle='-', linewidth=1, alpha=0.5, label='1km步行圈')
    
    ax.set_title(cat_name, fontsize=12, fontweight='bold')
    ax.set_xlabel('最近设施距离 (m)')
    ax.set_ylabel('小区数量')
    ax.legend(fontsize=8)

# 隐藏多余的子图
for idx in range(len(all_od_results), len(axes)):
    axes[idx].set_visible(False)

fig.suptitle('各住宅小区到最近公共服务设施的网络距离分布', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(os.path.join(FIG, 'fig5_distance_distributions.jpg'), dpi=200, bbox_inches='tight')
plt.close()
print("    fig5 完成")

# --- 图3: 15分钟生活圈覆盖率对比 ---
print("  生成图3: 15分钟生活圈覆盖率...")
fig, ax = plt.subplots(1, 1, figsize=(14, 8))

categories = list(all_od_stats.keys())
within_1km = [100 * all_od_stats[c]['within_1km'] / all_od_stats[c]['total_comm'] for c in categories]
within_2km = [100 * all_od_stats[c]['within_2km'] / all_od_stats[c]['total_comm'] for c in categories]
avg_dists = [all_od_stats[c]['avg'] for c in categories]

x = np.arange(len(categories))
width = 0.35

bars1 = ax.bar(x - width/2, within_1km, width, label='1km步行圈覆盖率 (%)', color='#3498db', alpha=0.8)
bars2 = ax.bar(x + width/2, within_2km, width, label='2km步行圈覆盖率 (%)', color='#2ecc71', alpha=0.8)

# 在柱状图上标注数值
for bar, val in zip(bars1, within_1km):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
           f'{val:.0f}%', ha='center', va='bottom', fontsize=9)
for bar, val in zip(bars2, within_2km):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
           f'{val:.0f}%', ha='center', va='bottom', fontsize=9)

# 均值距离折线
ax2 = ax.twinx()
ax2.plot(x, avg_dists, 'ro-', linewidth=2, markersize=8, label='平均最近距离 (m)')
ax2.set_ylabel('平均最近距离 (m)', fontsize=11)
ax2.legend(loc='upper right')

ax.set_ylabel('覆盖率 (%)', fontsize=11)
ax.set_xlabel('设施类别', fontsize=11)
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=10)
ax.set_title('坂田片区住宅小区15分钟生活圈设施覆盖率对比\n(基于网络距离，1km≈步行15分钟)',
            fontsize=14, fontweight='bold')
ax.legend(loc='upper left', fontsize=10)
ax.set_ylim(0, 110)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'fig6_15min_coverage.jpg'), dpi=200, bbox_inches='tight')
plt.close()
print("    fig6 完成")

# --- 图4: 秋港花园专项可达性雷达图 ---
print("  生成图4: 秋港花园可达性雷达图...")

# 找到秋港花园的数据
qg_name_variants = ['秋港花园', '秋港花园A2区', '秋港花园C区']
qg_dists = {}

for cat_name, records in all_od_results.items():
    min_d = float('inf')
    for r in records:
        if any(v in r['community_name'] for v in qg_name_variants) and r['community_name'] == '秋港花园':
            if r['distance_m'] < min_d:
                min_d = r['distance_m']
    qg_dists[cat_name] = min_d if min_d < float('inf') else None

# 如果秋港花园本身不在小区列表中，用预计算的距离
if all(v is None for v in qg_dists.values()):
    # 找秋港花园对应的community_id
    qg_cid = None
    for comm in comm_data:
        if comm['name'] == '秋港花园':
            qg_cid = comm['id']
            break
    
    if qg_cid and qg_cid in comm_distances:
        dist_map = comm_distances[qg_cid]
        for cat_name, poi_nodes in cat_poi_nodes.items():
            min_d = float('inf')
            for pn in poi_nodes:
                pnode = pn['network_node']
                if pnode in dist_map:
                    if dist_map[pnode] < min_d:
                        min_d = dist_map[pnode]
            qg_dists[cat_name] = min_d if min_d < float('inf') else None
    else:
        # 最后手段：直接计算
        qg_node, _ = snap_to_network(114.075434, 22.668739, G_main)
        if qg_node and qg_node in G_main:
            qg_dists_all = nx.single_source_dijkstra_path_length(G_main, qg_node, weight='weight')
            for cat_name, poi_nodes in cat_poi_nodes.items():
                min_d = float('inf')
                for pn in poi_nodes:
                    pnode = pn['network_node']
                    if pnode in qg_dists_all:
                        if qg_dists_all[pnode] < min_d:
                            min_d = qg_dists_all[pnode]
                qg_dists[cat_name] = min_d if min_d < float('inf') else None

# 雷达图
fig, ax = plt.subplots(1, 1, figsize=(10, 10), subplot_kw=dict(polar=True))

cats_radar = [k for k, v in qg_dists.items() if v is not None]
vals_radar = [qg_dists[k] for k in cats_radar]

# 归一化到0-1（使用2km作为满分参考）
vals_norm = [min(v / 2000.0, 1.0) for v in vals_radar]
# 反转：距离越短可达性越好
vals_accessibility = [1.0 - v for v in vals_norm]

angles = np.linspace(0, 2 * np.pi, len(cats_radar), endpoint=False).tolist()
vals_accessibility += vals_accessibility[:1]
angles += angles[:1]

ax.fill(angles, vals_accessibility, alpha=0.25, color='#3498db')
ax.plot(angles, vals_accessibility, 'o-', linewidth=2, color='#3498db', markersize=8)

# 标注实际距离
for i, (cat, dist) in enumerate(zip(cats_radar, vals_radar)):
    angle = angles[i]
    ax.annotate(f'{dist:.0f}m',
               xy=(angle, 1.0 - min(dist/2000, 1.0)),
               fontsize=10, fontweight='bold',
               ha='center', va='bottom',
               color='#e74c3c')

ax.set_xticks(angles[:-1])
ax.set_xticklabels(cats_radar, fontsize=11)
ax.set_ylim(0, 1.1)
ax.set_title('秋港花园多设施可达性评价\n(基于网络距离，外圈=可达性好)',
            fontsize=14, fontweight='bold', pad=20)

plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
plt.savefig(os.path.join(FIG, 'fig7_qiugang_radar.jpg'), dpi=200)
plt.close()
print("    fig7 完成")

# --- 图5: 各类设施最近距离空间分布图（分面） ---
print("  生成图5: 可达性空间分面图...")
n_cats = len(all_od_results)
ncols = 3
nrows = math.ceil(n_cats / ncols)

fig, axes = plt.subplots(nrows, ncols, figsize=(20, 6*nrows))
if nrows == 1:
    axes = axes.reshape(1, -1)
axes_flat = axes.flatten()

for idx, (cat_name, records) in enumerate(all_od_results.items()):
    if idx >= len(axes_flat):
        break
    ax = axes_flat[idx]
    
    # 底图
    if has_roads:
        roads_gdf.plot(ax=ax, color='#e0e0e0', linewidth=0.3)
    
    # 计算每个小区的最近距离
    min_dists = {}
    for r in records:
        cname = r['community_name']
        d = r['distance_m']
        if cname not in min_dists or d < min_dists[cname]:
            min_dists[cname] = d
    
    # 绘制小区（按距离着色）
    for comm in comm_data:
        d = min_dists.get(comm['name'])
        if d is None:
            continue
        # 颜色映射：绿(近) -> 黄 -> 红(远)
        if d <= 500:
            c = '#27ae60'
        elif d <= 1000:
            c = '#f1c40f'
        elif d <= 2000:
            c = '#e67e22'
        else:
            c = '#e74c3c'
        ax.scatter(comm['easting'], comm['northing'], c=c, s=20, alpha=0.7, zorder=2)
    
    # 绘制设施点
    for p in OD_CATEGORIES.get(cat_name, []):
        e, n = wgs84_to_cgcs2000(p['lon'], p['lat'])
        ax.scatter(e, n, c=colors.get(cat_name, '#999'), s=40, marker='*',
                  edgecolors='black', linewidths=0.3, zorder=3)
    
    # 标注秋港花园
    ax.scatter([qg_e], [qg_n], c='red', s=120, marker='*', zorder=5,
              edgecolors='black', linewidths=0.5)
    
    # 图例
    patches = [
        mpatches.Patch(color='#27ae60', label='≤500m'),
        mpatches.Patch(color='#f1c40f', label='500-1000m'),
        mpatches.Patch(color='#e67e22', label='1000-2000m'),
        mpatches.Patch(color='#e74c3c', label='>2000m'),
    ]
    ax.legend(handles=patches, loc='upper right', fontsize=8, title='最近设施距离')
    ax.set_title(f'{cat_name}\n(均值{all_od_stats[cat_name]["avg"]:.0f}m)', fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.tick_params(labelsize=8)

# 隐藏多余子图
for idx in range(len(all_od_results), len(axes_flat)):
    axes_flat[idx].set_visible(False)

fig.suptitle('坂田片区住宅小区到各类公共服务设施的网络距离空间分布', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(FIG, 'fig8_spatial_accessibility.jpg'), dpi=200, bbox_inches='tight')
plt.close()
print("    fig8 完成")

# --- 图6: 综合可达性评价热力图 ---
print("  生成图6: 综合可达性热力图...")
fig, ax = plt.subplots(1, 1, figsize=(14, 10))

if has_roads:
    roads_gdf.plot(ax=ax, color='#e0e0e0', linewidth=0.3)

# 计算每个小区的综合可达性得分（各类最近距离的加权平均）
# 权重：餐饮商业0.25, 商超0.2, 地铁站0.2, 公交站0.1, 公园0.1, 教育0.1, 社康0.05
weights = {
    '餐饮商业': 0.25,
    '商超便利店': 0.20,
    '地铁站': 0.20,
    '公交站': 0.10,
    '公园绿地': 0.10,
    '教育设施': 0.10,
    '社康诊所': 0.05,
}

composite_scores = {}
for comm in comm_data:
    cname = comm['name']
    total_score = 0
    total_weight = 0
    for cat_name, records in all_od_results.items():
        min_d = float('inf')
        for r in records:
            if r['community_name'] == cname and r['distance_m'] < min_d:
                min_d = r['distance_m']
        if min_d < float('inf'):
            w = weights.get(cat_name, 0.1)
            # 归一化：0-2000m映射到0-1
            norm_d = min(min_d / 2000.0, 1.0)
            total_score += w * norm_d
            total_weight += w
    
    if total_weight > 0:
        # 可达性得分：0(差) -> 1(好)
        composite_scores[cname] = 1.0 - (total_score / total_weight)

# 绘制
for comm in comm_data:
    score = composite_scores.get(comm['name'])
    if score is None:
        continue
    # 绿(好) -> 红(差)
    cmap = plt.cm.RdYlGn
    c = cmap(score)
    ax.scatter(comm['easting'], comm['northing'], c=[c], s=40, alpha=0.8, zorder=2,
              edgecolors='white', linewidths=0.3)

# 设施点
for cat_name, pois_list in OD_CATEGORIES.items():
    for p in pois_list:
        e, n = wgs84_to_cgcs2000(p['lon'], p['lat'])
        ax.scatter(e, n, c='gray', s=5, alpha=0.3, zorder=1)

# 秋港花园
ax.scatter([qg_e], [qg_n], c='red', s=200, marker='*', zorder=5,
          edgecolors='black', linewidths=0.8)
ax.annotate('秋港花园', xy=(qg_e, qg_n), fontsize=12, fontweight='bold',
           xytext=(15, 15), textcoords='offset points',
           arrowprops=dict(arrowstyle='->', color='red'),
           color='red')

# 色条
sm = plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=Normalize(0, 1))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax, shrink=0.8, label='综合可达性得分')
cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
cbar.set_ticklabels(['极差', '较差', '一般', '较好', '优秀'])

ax.set_title('坂田片区住宅小区综合公共服务可达性评价\n(加权网络距离，绿=可达性好 / 红=可达性差)',
            fontsize=14, fontweight='bold')
ax.set_xlabel('东向坐标 (m)', fontsize=10)
ax.set_ylabel('北向坐标 (m)', fontsize=10)
ax.set_aspect('equal')
ax.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'fig9_composite_accessibility.jpg'), dpi=200, bbox_inches='tight')
plt.close()
print("    fig9 完成")

# ============================================================
# 7. 秋港花园专项统计 & 研究解读
# ============================================================
print("\n" + "=" * 60)
print("7. 秋港花园可达性分析摘要")
print("=" * 60)

print("\n  秋港花园到各类设施的最近网络距离:")
for cat_name in OD_CATEGORIES:
    d = qg_dists.get(cat_name)
    if d is not None:
        if d <= 500:
            level = "★★★★★ 极便利"
        elif d <= 1000:
            level = "★★★★ 便利"
        elif d <= 1500:
            level = "★★★ 一般"
        elif d <= 2000:
            level = "★★ 较远"
        else:
            level = "★ 偏远"
        print(f"    {cat_name}: {d:.0f}m ({level})")
    else:
        print(f"    {cat_name}: 无数据")

# 输出研究解读文本
analysis_text = """
============================================================
可达性分析与"新型单位大院"空间治理
============================================================

一、分析框架
  本分析基于交通网络距离（Dijkstra最短路径），计算坂田片区175个住宅小区
  到7类公共服务设施的OD矩阵，从"15分钟生活圈"视角评估秋港花园等华为
  员工配套社区的公共服务可达性。

二、核心发现

  1. 商业服务可达性 vs 公共服务可达性的结构性差异
     餐饮商业和商超便利店通常覆盖率高（市场驱动，密度大），但地铁站、
     公园绿地等公共基础设施的覆盖率可能显著偏低。这反映了坂田片区作为
     "产业配套区"而非"完整城区"的结构性缺陷。

  2. "企业飞地"效应
     秋港花园等华为配套社区由企业选址决定，而非居民自主选择。
     如果可达性雷达图显示某些维度严重凹陷（如地铁、公园），
     说明这些社区在空间上处于"服务洼地"——居民日常需求高度依赖
     企业班车和商业综合体内部配套，而非城市公共服务体系。

  3. 时间维度的封闭性
     当商业设施（餐饮/超市）可达但公共设施（公园/教育）不可达时，
     居民的生活模式呈现"功能性满足但公共性缺失"的特征——
     这恰恰是"数字修道院"概念的空间基础：物质需求被企业生态
     高效满足，但市民性公共空间严重不足。

  4. 与传统单位大院的对比
     传统单位大院（如国企家属院）虽然也有围墙，但通常位于城市
     中心区，公共服务可达性较好。而秋港花园代表的"新型单位大院"
     位于城市边缘的产业区，空间隔离更为彻底。这种"远郊飞地"模式
     是中国科技企业产城融合困境的空间表达。

三、方法论说明
  - 投影坐标系：CGCS2000 3度带38带（中央经线114°）
  - 网络距离：基于OSM道路数据的Dijkstra最短路径
  - POI数据：OSM + 高德地图双源融合
  - 15分钟步行圈：以1000m网络距离为阈值
"""

with open(os.path.join(OUT, 'analysis_interpretation.txt'), 'w', encoding='utf-8') as f:
    f.write(analysis_text)

print(analysis_text)

# ============================================================
# 8. 导出POI设施shapefiles
# ============================================================
print("=" * 60)
print("8. 导出各类POI设施shapefiles")
print("=" * 60)

PRJ_CONTENT = '''PROJCS["CGCS2000_3_Degree_GK_Zone_38",GEOGCS["GCS_China_Geodetic_Coordinate_System_2000",DATUM["D_China_2000",SPHEROID["CGCS2000",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Gauss_Kruger"],PARAMETER["False_Easting",38500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",114.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'''

for cat_name, pois in OD_CATEGORIES.items():
    if not pois:
        continue
    
    safe_name = cat_name.replace('/', '_').replace('\\', '_')
    shp_path = os.path.join(SHP, f'poi_{safe_name}.shp')
    
    records = []
    for i, p in enumerate(pois):
        e, n = wgs84_to_cgcs2000(p['lon'], p['lat'])
        records.append({
            'geometry': Point(e, n),
            'poi_id': i + 1,
            'name': p['name'][:50],
            'category': cat_name[:20],
            'lon': p['lon'],
            'lat': p['lat'],
            'easting': round(e, 2),
            'northing': round(n, 2),
            'source': p['source'][:10]
        })
    
    gdf = gpd.GeoDataFrame(records, crs=CGCS2000_3D_38)
    gdf.to_file(shp_path, encoding='utf-8')
    
    # 写prj
    prj_path = shp_path.replace('.shp', '.prj')
    with open(prj_path, 'w') as f:
        f.write(PRJ_CONTENT)
    # 写cpg
    cpg_path = shp_path.replace('.shp', '.cpg')
    with open(cpg_path, 'w') as f:
        f.write('UTF-8')
    
    print(f"  {safe_name}: {len(records)} features -> {shp_path}")

# ============================================================
# 9. 复制最终输出
# ============================================================
import shutil
output_dir = os.path.join(WORK, 'outputs', 'coursework')
for fig_name in ['fig4_multi_service_distribution.jpg', 'fig5_distance_distributions.jpg',
                 'fig6_15min_coverage.jpg', 'fig7_qiugang_radar.jpg',
                 'fig8_spatial_accessibility.jpg', 'fig9_composite_accessibility.jpg']:
    src = os.path.join(FIG, fig_name)
    dst = os.path.join(output_dir, 'figures', fig_name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  复制 {fig_name}")

# 复制数据库
shutil.copy2(db_path2, os.path.join(output_dir, 'database', 'bantian_multi_service_od.db'))
shutil.copy2(csv_path, os.path.join(output_dir, 'database', 'od_multi_service.csv'))
shutil.copy2(stats_csv, os.path.join(output_dir, 'database', 'od_statistics_summary.csv'))

# 复制分析解读
shutil.copy2(os.path.join(OUT, 'analysis_interpretation.txt'),
             os.path.join(output_dir, 'analysis_interpretation.txt'))

print("\n" + "=" * 60)
print("全部完成！")
print("=" * 60)

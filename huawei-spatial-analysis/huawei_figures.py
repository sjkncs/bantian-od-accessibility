#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
huawei_figures.py
Generates publication-quality figures (Fig 22-26) for coursework.
"""

import json
import os
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import matplotlib.lines as mlines

# ── Global settings ──────────────────────────────────────────────────────────
plt.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'DejaVu Sans', 'Arial'
]
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['font.size'] = 10

# Muted color palette (Tol's vibrant qualitative, muted feel)
COLORS = ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377']

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'gaode_huawei')
FIG_DIR = os.path.join(BASE_DIR, 'outputs', 'coursework', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 22: 秋港花园服务设施半径衰减
# ═══════════════════════════════════════════════════════════════════════════════
def fig22_radius_decay():
    data = load_json('radius_comparison.json')
    categories = list(data['categories'].keys())
    radii = data['radii']  # ['200m', '500m', '1km', '2km']
    radius_colors = [COLORS[0], COLORS[1], COLORS[2], COLORS[3]]

    n_cats = len(categories)
    n_radii = len(radii)
    x = np.arange(n_cats)
    width = 0.18

    fig, ax = plt.subplots(figsize=(16, 7))

    for i, (radius, color) in enumerate(zip(radii, radius_colors)):
        counts = [data['categories'][cat][radius] for cat in categories]
        bars = ax.bar(x + i * width, counts, width, label=radius, color=color,
                      edgecolor='white', linewidth=0.5)
        # Add value labels on top of bars (only for non-zero values)
        for bar, val in zip(bars, counts):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        str(val), ha='center', va='bottom', fontsize=6.5,
                        fontweight='bold' if val >= 10 else 'normal')

    ax.set_xlabel('')
    ax.set_ylabel('设施数量 (个)', fontsize=12)
    ax.set_title('图22 秋港花园服务设施半径衰减 / Fig.22 Facility Radius Decay from Qiugang Garden',
                 fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(categories, fontsize=9, rotation=25, ha='right')
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 60)

    # Add annotation highlighting the "desert" at small radii
    ax.annotate('200m/500m: 近乎真空',
                xy=(1, 2), xytext=(3, 45),
                fontsize=9, color=COLORS[1],
                arrowprops=dict(arrowstyle='->', color=COLORS[1], lw=1.2),
                fontweight='bold')
    ax.annotate('2km: 设施爆发式增长',
                xy=(5, 52), xytext=(7, 55),
                fontsize=9, color=COLORS[2],
                arrowprops=dict(arrowstyle='->', color=COLORS[2], lw=1.2),
                fontweight='bold')

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, 'fig22_radius_decay.png'))
    plt.close(fig)
    print('[OK] fig22_radius_decay.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 23: 企业配套三极对比
# ═══════════════════════════════════════════════════════════════════════════════
def fig23_tripolar():
    # Load data
    qiugang = load_json('qiugang_internal.json')
    huawei = load_json('huawei_pois.json')
    tayg = load_json('tayg_internal.json')

    # Count Huawei canteens from POIs
    hw_canteens = sum(1 for p in huawei['pois']
                      if '食堂' in p.get('search_query', '')
                      or '餐' in p.get('name', '')
                      or '食堂' in p.get('name', ''))

    # Count Huawei categories
    hw_cats = {}
    for p in huawei['pois']:
        cat = p['category']
        hw_cats[cat] = hw_cats.get(cat, 0) + 1

    # Categories for comparison
    categories = ['餐饮/食堂', '便利店/超市', '药店', '银行/ATM', '停车场',
                  '咖啡厅', '培训中心', '医疗', '快递', '健身', '图书馆']

    # 秋港花园 data
    qg_values = [
        0,  # 餐饮
        qiugang['summary'].get('便利店', 0),  # 便利店/超市
        qiugang['summary'].get('药店', 0),  # 药店
        0,  # 银行/ATM
        0,  # 停车场
        0,  # 咖啡厅
        0,  # 培训中心
        0,  # 医疗
        0,  # 快递
        0,  # 健身
        0,  # 图书馆
    ]

    # 华为坂田 data
    hw_values = [
        hw_canteens,  # 餐饮/食堂
        hw_cats.get('便利店', 0),  # 便利店/超市
        hw_cats.get('药店', 0),  # 药店
        hw_cats.get('银行', 0),  # 银行/ATM
        hw_cats.get('停车', 0),  # 停车场
        hw_cats.get('咖啡', 0),  # 咖啡厅
        hw_cats.get('培训', 0),  # 培训中心
        hw_cats.get('医疗', 0),  # 医疗
        hw_cats.get('快递', 0),  # 快递
        hw_cats.get('健身', 0),  # 健身
        0,  # 图书馆
    ]

    # 天安云谷 data
    tayg_summary = tayg['summary']
    ty_values = [
        tayg_summary.get('餐饮', 0),  # 餐饮
        tayg_summary.get('超市', 0) + tayg_summary.get('便利店', 0),  # 便利店/超市
        tayg_summary.get('药店', 0),  # 药店
        tayg_summary.get('银行', 0) + tayg_summary.get('ATM', 0),  # 银行/ATM
        tayg_summary.get('停车', 0),  # 停车场
        tayg_summary.get('咖啡', 0),  # 咖啡厅
        0,  # 培训中心
        tayg_summary.get('医疗', 0),  # 医疗
        tayg_summary.get('快递', 0),  # 快递
        tayg_summary.get('健身', 0),  # 健身
        tayg_summary.get('图书馆', 0),  # 图书馆
    ]

    locations = ['秋港花园\n(3个)', '华为坂田基地\n({}个)'.format(sum(hw_values)),
                 '天安云谷\n({}个)'.format(sum(ty_values))]
    all_values = [qg_values, hw_values, ty_values]
    location_colors = [COLORS[1], COLORS[2], COLORS[0]]

    n_cats = len(categories)
    n_locs = 3
    x = np.arange(n_cats)
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 7))

    for i, (vals, color, label) in enumerate(zip(all_values, location_colors, locations)):
        bars = ax.bar(x + i * width, vals, width, label=label, color=color,
                      edgecolor='white', linewidth=0.5)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(val), ha='center', va='bottom', fontsize=8,
                        fontweight='bold')

    ax.set_ylabel('设施数量 (个)', fontsize=12)
    ax.set_title('图23 企业配套三极对比 / Fig.23 Enterprise Facility Tripolar Comparison',
                 fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x + width)
    ax.set_xticklabels(categories, fontsize=9, rotation=25, ha='right')
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, max(max(v) for v in all_values) * 1.25)

    # Add summary annotations
    totals = [sum(v) for v in all_values]
    ax.text(0.98, 0.95,
            f'总计: 秋港={totals[0]}, 华为={totals[1]}, 天安={totals[2]}',
            transform=ax.transAxes, fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, 'fig23_tripolar.png'))
    plt.close(fig)
    print('[OK] fig23_tripolar.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 24: 华为-秋港花园空间关系
# ═══════════════════════════════════════════════════════════════════════════════
def fig24_spatial():
    huawei = load_json('huawei_pois.json')
    commute = load_json('commute_routes.json')

    # Key locations
    qg_lon, qg_lat = 114.075434, 22.668739
    tayg_lon, tayg_lat = 114.066711, 22.661316

    fig, ax = plt.subplots(figsize=(12, 10))

    # Plot Huawei campus zones
    zones = [p for p in huawei['pois'] if p['category'] == '园区']
    canteens = [p for p in huawei['pois'] if p['category'] == '食堂']
    other_pois = [p for p in huawei['pois']
                  if p['category'] not in ('园区', '食堂')]

    # Zone markers (green)
    for z in zones:
        ax.scatter(z['lon'], z['lat'], c=COLORS[2], s=80, marker='o',
                   zorder=3, edgecolors='white', linewidths=0.8)
        zone_label = z['name'].replace('华为', '')
        ax.annotate(zone_label, (z['lon'], z['lat']),
                    textcoords='offset points', xytext=(5, 5),
                    fontsize=7, color=COLORS[2], fontweight='bold')

    # Canteen markers (orange)
    for c in canteens:
        ax.scatter(c['lon'], c['lat'], c='#EE8833', s=50, marker='s',
                   zorder=3, edgecolors='white', linewidths=0.5)

    # Other POIs (light gray)
    for p in other_pois:
        ax.scatter(p['lon'], p['lat'], c='#AAAAAA', s=25, marker='.',
                   zorder=2)

    # 秋港花园 (red star)
    ax.scatter(qg_lon, qg_lat, c='red', s=350, marker='*', zorder=5,
               edgecolors='darkred', linewidths=1.0)
    ax.annotate('秋港花园', (qg_lon, qg_lat),
                textcoords='offset points', xytext=(12, 10),
                fontsize=11, fontweight='bold', color='darkred',
                arrowprops=dict(arrowstyle='->', color='darkred', lw=1.0))

    # 天安云谷 (blue diamond)
    ax.scatter(tayg_lon, tayg_lat, c=COLORS[0], s=200, marker='D', zorder=5,
               edgecolors='darkblue', linewidths=1.0)
    ax.annotate('天安云谷', (tayg_lon, tayg_lat),
                textcoords='offset points', xytext=(-50, 15),
                fontsize=11, fontweight='bold', color=COLORS[0],
                arrowprops=dict(arrowstyle='->', color=COLORS[0], lw=1.0))

    # Draw dashed circles at 1km and 2km from 秋港花园
    # At latitude ~22.67: 1 deg lat ≈ 110.6km, 1 deg lon ≈ 102.5km
    lat_km = 110.6
    lon_km = 102.5
    theta = np.linspace(0, 2 * np.pi, 200)

    for radius_km, style in [(1, '--'), (2, '--')]:
        circle_lon = qg_lon + (radius_km / lon_km) * np.cos(theta)
        circle_lat = qg_lat + (radius_km / lat_km) * np.sin(theta)
        ax.plot(circle_lon, circle_lat, linestyle=style, color='gray',
                linewidth=1.0, alpha=0.6)
        # Label the circle
        label_lon = qg_lon + (radius_km / lon_km) * 0.707
        label_lat = qg_lat + (radius_km / lat_km) * 0.707
        ax.text(label_lon + 0.001, label_lat, f'{radius_km}km',
                fontsize=8, color='gray', fontstyle='italic')

    # Arrow from 秋港花园 to 华为基地 center
    hw_center_lon = huawei['center_coords'][0]
    hw_center_lat = huawei['center_coords'][1]
    ax.annotate('',
                xy=(hw_center_lon, hw_center_lat),
                xytext=(qg_lon, qg_lat),
                arrowprops=dict(arrowstyle='->', color=COLORS[4],
                                lw=2.0, connectionstyle='arc3,rad=0.15'))
    # Label on arrow
    mid_lon = (qg_lon + hw_center_lon) / 2 - 0.001
    mid_lat = (qg_lat + hw_center_lat) / 2 + 0.002
    ax.text(mid_lon, mid_lat, '步行33min / 驾车9min',
            fontsize=9, color=COLORS[4], fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=COLORS[4], alpha=0.9))

    # Style
    ax.set_xlabel('经度 (°E)', fontsize=11)
    ax.set_ylabel('纬度 (°N)', fontsize=11)
    ax.set_title('图24 华为-秋港花园空间关系 / Fig.24 Huawei-Qiugang Spatial Relationship',
                 fontsize=13, fontweight='bold', pad=15)

    # Legend
    legend_elements = [
        mlines.Line2D([], [], marker='*', color='w', markerfacecolor='red',
                      markersize=14, label='秋港花园'),
        mlines.Line2D([], [], marker='D', color='w', markerfacecolor=COLORS[0],
                      markersize=10, label='天安云谷'),
        mlines.Line2D([], [], marker='o', color='w', markerfacecolor=COLORS[2],
                      markersize=8, label='华为园区 (A-K区)'),
        mlines.Line2D([], [], marker='s', color='w', markerfacecolor='#EE8833',
                      markersize=7, label='华为食堂'),
        mlines.Line2D([], [], color='gray', linestyle='--', linewidth=1,
                      label='等距圈 (1km/2km)'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9,
              framealpha=0.9)

    ax.set_aspect(1.0 / (lon_km / lat_km))  # Correct aspect ratio
    ax.grid(True, alpha=0.2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, 'fig24_huawei_spatial.png'))
    plt.close(fig)
    print('[OK] fig24_huawei_spatial.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 25: 社区闭合度雷达图
# ═══════════════════════════════════════════════════════════════════════════════
def fig25_closure():
    data = load_json('radius_comparison.json')
    categories = list(data['categories'].keys())

    # Compute closure index = 200m_count / 1km_count
    closure = []
    valid_cats = []
    for cat in categories:
        count_200 = data['categories'][cat]['200m']
        count_1k = data['categories'][cat]['1km']
        if count_1k > 0:
            closure.append(count_200 / count_1k)
            valid_cats.append(cat)
        # Skip categories where 1km count is 0 (avoid division by zero)

    n = len(valid_cats)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    # Close the polygon
    closure_closed = closure + [closure[0]]
    angles_closed = angles + [angles[0]]

    # Reference "ideal danwei" line at 0.3
    ref_value = 0.3
    ref_closed = [ref_value] * n + [ref_value]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))

    # Plot closure index
    ax.plot(angles_closed, closure_closed, 'o-', color=COLORS[1],
            linewidth=2, markersize=6, label='秋港花园闭合度')
    ax.fill(angles_closed, closure_closed, alpha=0.15, color=COLORS[1])

    # Plot reference line
    ax.plot(angles_closed, ref_closed, '--', color=COLORS[2],
            linewidth=1.5, alpha=0.7, label=f'理想单位基准 (0.3)')

    # Set up axes
    ax.set_xticks(angles)
    ax.set_xticklabels(valid_cats, fontsize=9)
    ax.set_ylim(0, max(max(closure) * 1.5, ref_value * 1.3))
    ax.set_yticks([0.05, 0.1, 0.15, 0.2, 0.25, 0.3])
    ax.set_yticklabels(['0.05', '0.10', '0.15', '0.20', '0.25', '0.30'], fontsize=7)
    ax.set_rlabel_position(30)

    # Add value annotations
    for angle, val, cat in zip(angles, closure, valid_cats):
        if val > 0:
            ax.annotate(f'{val:.3f}',
                        xy=(angle, val),
                        textcoords='offset points', xytext=(8, 5),
                        fontsize=7, color=COLORS[1], fontweight='bold')

    ax.set_title('图25 社区闭合度指数 / Fig.25 Community Closure Index',
                 fontsize=13, fontweight='bold', pad=25)
    ax.legend(loc='lower right', bbox_to_anchor=(1.15, -0.05), fontsize=10,
              framealpha=0.9)

    # IMPORTANT: Use subplots_adjust() instead of tight_layout() for polar plots
    fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    fig.savefig(os.path.join(FIG_DIR, 'fig25_closure.png'))
    plt.close(fig)
    print('[OK] fig25_closure.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 26: 秋港花园通勤可达性
# ═══════════════════════════════════════════════════════════════════════════════
def fig26_commute():
    data = load_json('commute_routes.json')

    # Extract route data
    routes = data['routes']

    # Build data for plotting
    destinations = []
    modes_list = []
    times_list = []
    distances_list = []

    # All possible modes for consistent grouping
    all_modes = ['步行 (walk)', '公交 (transit)', '驾车 (drive)']
    mode_colors = [COLORS[0], COLORS[3], COLORS[1]]

    for route in routes:
        dest = route['destination']
        destinations.append(dest)

    # Create horizontal grouped bar chart
    n_dest = len(destinations)
    n_modes = len(all_modes)
    y = np.arange(n_dest)
    height = 0.22

    fig, ax = plt.subplots(figsize=(12, 5))

    # For each mode, create bars across destinations
    for mode_idx, (mode_key, mode_label) in enumerate(
            [('walk', '步行 (walk)'), ('transit', '公交 (transit)'), ('drive', '驾车 (drive)')]):
        times = []
        distances = []
        for route in routes:
            if mode_key in route['modes']:
                times.append(route['modes'][mode_key]['time_min'])
                distances.append(route['modes'][mode_key]['distance_km'])
            else:
                times.append(0)
                distances.append(0)

        bars = ax.barh(y + mode_idx * height, times, height,
                       label=mode_label, color=mode_colors[mode_idx],
                       edgecolor='white', linewidth=0.5)

        # Add time + distance labels on bars
        for bar, t, d in zip(bars, times, distances):
            if t > 0:
                ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                        f'{t}min ({d}km)',
                        ha='left', va='center', fontsize=9, fontweight='bold')

    ax.set_xlabel('通勤时间 (分钟)', fontsize=12)
    ax.set_title('图26 秋港花园通勤可达性 / Fig.26 Commute Accessibility from Qiugang Garden',
                 fontsize=13, fontweight='bold', pad=15)
    ax.set_yticks(y + height)
    ax.set_yticklabels(destinations, fontsize=11, fontweight='bold')
    ax.legend(loc='lower right', fontsize=10, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, 50)
    ax.invert_yaxis()

    # Add grid on x-axis
    ax.xaxis.grid(True, alpha=0.2)
    ax.set_axisbelow(True)

    plt.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, 'fig26_commute.png'))
    plt.close(fig)
    print('[OK] fig26_commute.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f'Data directory: {DATA_DIR}')
    print(f'Output directory: {FIG_DIR}')
    print()

    fig22_radius_decay()
    fig23_tripolar()
    fig24_spatial()
    fig25_closure()
    fig26_commute()

    print()
    print('All figures generated successfully.')

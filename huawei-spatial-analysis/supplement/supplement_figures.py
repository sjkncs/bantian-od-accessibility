#!/usr/bin/env python3
"""Generate supplementary figures (Fig 27-30) from gaode_supplement data."""
import json, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Font & style
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
COLORS = ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377']
RED = '#EE6677'
BLUE = '#4477AA'
GREEN = '#228833'

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gaode_supplement')
FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs', 'coursework', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

def load(name):
    with open(os.path.join(DATA_DIR, f'{name}.json'), 'r', encoding='utf-8-sig') as f:
        return json.load(f)

# ============================================================
# Fig 27: School walking distance comparison
# ============================================================
def fig27():
    data = load('school_walking_routes')
    routes = data['routes']
    names = [r['community'] for r in routes]
    dists = [r['distance_m'] for r in routes]
    times = [r['duration_min'] for r in routes]

    # Sort by distance descending
    idx = np.argsort(dists)[::-1]
    names = [names[i] for i in idx]
    dists = [dists[i] for i in idx]
    times = [times[i] for i in idx]

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = [RED if n == '秋港花园' else BLUE for n in names]
    bars = ax.barh(range(len(names)), dists, color=colors, height=0.6, edgecolor='white')
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel('步行距离 (m)', fontsize=12)
    ax.set_title('图27 各社区至最近学校步行距离 / Fig.27 Walking Distance to Nearest School', fontsize=13, fontweight='bold', pad=15)

    for i, (d, t) in enumerate(zip(dists, times)):
        ax.text(d + 30, i, f'{d}m / {t}min', va='center', fontsize=10, fontweight='bold' if names[i]=='秋港花园' else 'normal')

    # Annotation
    ax.annotate('秋港花园是其他社区的5.5~7.7倍', xy=(2752, 0), xytext=(1800, 2),
                fontsize=11, color=RED, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=RED, lw=1.5))

    ax.set_xlim(0, 3400)
    ax.axvline(x=np.mean([d for i,d in enumerate(dists) if names[i]!='秋港花园']), color=GREEN, linestyle='--', alpha=0.5, label='其他社区均值')
    ax.legend(loc='lower right', fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, 'fig27_school_distance.png')
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved {path} ({os.path.getsize(path)//1024}KB)')

# ============================================================
# Fig 28: Transit + Commercial dual comparison
# ============================================================
def fig28():
    transit = load('transit_coverage')
    realestate = load('realestate_density')

    # Build aligned data
    t_names = [c['community'] for c in transit['communities']]
    t_stops = [c['stops_within_500m'] for c in transit['communities']]

    r_names = [c['community'] for c in realestate['communities']]
    r_comm = [c['commercial_200m'] for c in realestate['communities']]

    # Use transit names order
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Panel A: Transit
    colors_a = [RED if n == '秋港花园' else BLUE for n in t_names]
    ax1.barh(range(len(t_names)), t_stops, color=colors_a, height=0.6, edgecolor='white')
    ax1.set_yticks(range(len(t_names)))
    ax1.set_yticklabels(t_names, fontsize=10)
    ax1.set_xlabel('公交站点数量', fontsize=11)
    ax1.set_title('(A) 500m内公交站点数', fontsize=12, fontweight='bold')
    for i, s in enumerate(t_stops):
        ax1.text(s + 0.1, i, str(s), va='center', fontsize=10, fontweight='bold' if t_names[i]=='秋港花园' else 'normal')
    ax1.set_xlim(0, 9)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Panel B: Commercial
    colors_b = [RED if n == '秋港花园' else GREEN for n in r_names]
    ax2.barh(range(len(r_names)), r_comm, color=colors_b, height=0.6, edgecolor='white')
    ax2.set_yticks(range(len(r_names)))
    ax2.set_yticklabels(r_names, fontsize=10)
    ax2.set_xlabel('商业设施数量', fontsize=11)
    ax2.set_title('(B) 200m内商业设施数', fontsize=12, fontweight='bold')
    for i, c in enumerate(r_comm):
        label = str(c) if c > 0 else '0 (零!)'
        ax2.text(max(c, 0.3), i, label, va='center', fontsize=10,
                 color=RED if c==0 else 'black', fontweight='bold' if r_names[i]=='秋港花园' else 'normal')
    ax2.set_xlim(0, 18)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    fig.suptitle('图28 社区公共服务覆盖对比 / Fig.28 Public Service Coverage Comparison', fontsize=13, fontweight='bold', y=1.02)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, 'fig28_transit_commercial.png')
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved {path} ({os.path.getsize(path)//1024}KB)')

# ============================================================
# Fig 29: Enterprise housing model comparison
# ============================================================
def fig29():
    comp = load('competitor_housing')
    analysis = comp['analysis']

    # Build comparison data
    enterprises = []
    internal_counts = []
    nearby_counts = []
    labels = []

    # Huawei Qiugang
    enterprises.append('华为·秋港花园')
    internal_counts.append(3)
    nearby_counts.append(0)
    labels.append('宿舍型')

    # Extract from competitor data - pick representative entries
    for a in analysis:
        name = a['enterprise']
        ic = a['internal_facilities_count']
        nc = a['nearby_residential_count']

        if '康冠科技' in name and '深圳' in name:
            enterprises.append('康冠科技')
            internal_counts.append(ic)
            nearby_counts.append(min(nc, 25))
            labels.append('传统大院型')
        elif name == '神舟电脑股份有限公司':
            enterprises.append('神舟电脑')
            internal_counts.append(min(ic, 25))
            nearby_counts.append(min(nc, 25))
            labels.append('市场化型')
        elif '富士康科技集团(龙华' in name:
            enterprises.append('富士康(龙华)')
            internal_counts.append(min(ic, 25))
            nearby_counts.append(min(nc, 25))
            labels.append('全包围型')

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(enterprises))
    w = 0.35

    bar1 = ax.bar(x - w/2, internal_counts, w, label='200m内设施数', color=BLUE, edgecolor='white')
    bar2 = ax.bar(x + w/2, nearby_counts, w, label='1km内住宅数', color=GREEN, edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(enterprises, fontsize=11)
    ax.set_ylabel('数量', fontsize=12)
    ax.set_title('图29 坂田企业配套住宅模式对比 / Fig.29 Enterprise Housing Model Comparison', fontsize=13, fontweight='bold', pad=15)
    ax.legend(fontsize=10, loc='upper right')

    # Value labels
    for bar in bar1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, str(int(h)), ha='center', fontsize=10, fontweight='bold')
    for bar in bar2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, str(int(h)), ha='center', fontsize=10)

    # Model labels below
    for i, (e, l) in enumerate(zip(enterprises, labels)):
        color = RED if l == '宿舍型' else (GREEN if l == '全包围型' else COLORS[3])
        ax.text(i, -2.5, l, ha='center', fontsize=11, fontweight='bold', color=color,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, lw=1.5))

    ax.set_ylim(-4, 30)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, 'fig29_enterprise_housing.png')
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved {path} ({os.path.getsize(path)//1024}KB)')

# ============================================================
# Fig 30: Dormitory Index radar chart
# ============================================================
def fig30():
    transit = load('transit_coverage')
    realestate = load('realestate_density')
    schools = load('school_walking_routes')

    # Get Qiugang values
    qg_school_dist = 2752  # meters
    qg_stops = 2
    qg_commercial = 0

    # Get other communities averages
    other_school = [r['distance_m'] for r in schools['routes'] if r['community'] != '秋港花园']
    avg_school_dist = np.mean(other_school)  # ~411m

    other_stops = [c['stops_within_500m'] for c in transit['communities'] if c['community'] != '秋港花园']
    avg_stops = np.mean(other_stops)  # ~6.25

    other_comm = [c['commercial_200m'] for c in realestate['communities'] if c['community'] != '秋港花园']
    avg_comm = np.mean(other_comm)  # ~12.4

    # Normalize: Qiugang score relative to others (1.0 = average of others)
    # For school: invert (shorter = better), so score = avg / qg
    school_score = avg_school_dist / qg_school_dist  # ~0.15
    transit_score = qg_stops / avg_stops  # ~0.32
    commercial_score = qg_commercial / avg_comm if avg_comm > 0 else 0  # 0.0
    internal_score = 3 / 25  # 0.12 (3 facilities vs typical 25)

    dimensions = ['学校可达性', '公交覆盖', '商业活力', '内部设施']
    scores = [school_score, transit_score, commercial_score, internal_score]
    N = len(dimensions)

    # Angles
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    scores_plot = scores + scores[:1]
    angles += angles[:1]
    ref = [1.0] * (N + 1)

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    plt.subplots_adjust(left=0.15, right=0.85, top=0.85, bottom=0.15)

    # Reference circle
    ax.plot(angles, ref, 'g--', linewidth=1.5, alpha=0.7, label='其他社区均值 (1.0)')
    ax.fill(angles, ref, alpha=0.05, color='green')

    # Qiugang polygon
    ax.plot(angles, scores_plot, 'o-', color=RED, linewidth=2.5, markersize=10, label='秋港花园')
    ax.fill(angles, scores_plot, alpha=0.15, color=RED)

    # Value labels
    for i in range(N):
        angle = angles[i]
        val = scores[i]
        ax.annotate(f'{val:.2f}', xy=(angle, val), fontsize=12, fontweight='bold', color=RED,
                    ha='center', va='bottom', xytext=(0, 10), textcoords='offset points')

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 1.2)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=9, color='gray')

    ax.legend(loc='lower right', bbox_to_anchor=(1.15, -0.05), fontsize=10)
    ax.set_title('图30 秋港花园宿舍化指数 / Fig.30 Dormitory Index', fontsize=13, fontweight='bold', pad=25)

    path = os.path.join(FIG_DIR, 'fig30_dormitory_index.png')
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved {path} ({os.path.getsize(path)//1024}KB)')

# ============================================================
if __name__ == '__main__':
    print('Generating supplementary figures...')
    fig27()
    fig28()
    fig29()
    fig30()
    print('Done!')

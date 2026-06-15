#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive Publication-Quality Figures for Bantian OD Analysis (v2)
Generates 12 figures (fig10-fig21) from corrected OD data.
"""

import os
import sys
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mticker
from scipy import stats

# ==================================================================
# CONFIGURATION
# ==================================================================
BASE = r'C:\Users\Administrator\.qoderwork\workspace\mq86irc1jqgzw5w6\outputs\coursework'
OD_DB = os.path.join(BASE, 'database', 'bantian_od_v2.db')
TN_DB = os.path.join(BASE, 'database', 'bantian_transport_network.db')
FIG_DIR = os.path.join(BASE, 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

# Style
PALETTE = ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377']
CATS = ['地铁站', '公交站', '教育设施', '医疗设施', '商业服务', '公园绿地']
CATS_SHORT = ['地铁站', '公交站', '教育', '医疗', '商业', '公园']
CATS_EN = ['Metro', 'Bus Stop', 'Education', 'Medical', 'Commercial', 'Park']

plt.rcParams.update({
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'Arial'],
    'font.size': 9,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.unicode_minus': False,
    'axes.grid': False,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
})

GRID_KW = dict(color='#E8E8E8', linewidth=0.3, alpha=0.5)

# ==================================================================
# DATA LOADING
# ==================================================================
conn_od = sqlite3.connect(OD_DB)
conn_tn = sqlite3.connect(TN_DB)

od_df = pd.read_sql("SELECT * FROM od_matrix_v2", conn_od)
stats_df = pd.read_sql("SELECT * FROM od_statistics_v2", conn_od)
routes_df = pd.read_sql("SELECT * FROM real_routes", conn_od)
communities_df = pd.read_sql("SELECT * FROM communities", conn_tn)

conn_od.close()
conn_tn.close()

od_df['dist_km'] = od_df['nearest_distance_m'] / 1000.0

# Reference: old (OSM-only) data
OLD_DIST = {'地铁站': 4353, '公交站': 3081, '教育设施': 3751,
            '医疗设施': 443, '商业服务': 112, '公园绿地': 535}
OLD_COV1 = {'地铁站': 0, '公交站': 0, '教育设施': 11,
            '医疗设施': 85, '商业服务': 96, '公园绿地': 86}

# GB/T 50180-2018 requirements (% within 1km)
GBT_STD = {'地铁站': 60, '公交站': 80, '教育设施': 70,
           '医疗设施': 80, '商业服务': 80, '公园绿地': 80}

# Normalize route categories into 6 main categories
CAT_MAP = {
    '地铁站': '地铁站', '公交站': '公交站',
    '小学': '教育设施', '中学': '教育设施', '大学': '教育设施',
    '幼儿园': '教育设施', '教育': '教育设施', '培训机构': '教育设施',
    '综合医院': '医疗设施', '社区医院': '医疗设施', '诊所': '医疗设施',
    '药店': '医疗设施', '医院': '医疗设施', '医疗保健': '医疗设施',
    '商场': '商业服务', '超市': '商业服务', '便利店': '商业服务',
    '菜市场': '商业服务', '餐饮': '商业服务', 'ATM': '商业服务',
    '银行': '商业服务', '停车场': '商业服务', '加油站': '商业服务',
    '充电站': '商业服务', '邮局': '商业服务', '洗衣店': '商业服务',
    '公园': '公园绿地', '广场': '公园绿地',
}
routes_df['cat6'] = routes_df['category'].map(CAT_MAP).fillna('其他')


# ==================================================================
# HELPER FUNCTIONS
# ==================================================================
def compute_ecdf(x):
    """Compute empirical CDF."""
    xs = np.sort(x)
    ys = np.arange(1, len(xs) + 1) / len(xs)
    return xs, ys


def compute_lorenz(x):
    """Compute Lorenz curve and Gini coefficient."""
    xs = np.sort(x)
    n = len(xs)
    cum_share = np.concatenate([[0], np.cumsum(xs) / np.sum(xs)])
    pop_share = np.arange(n + 1) / n
    gini = 1.0 - 2.0 * np.trapezoid(cum_share, pop_share)
    return pop_share, cum_share, gini


def accessibility_score(dist_m, d_ref=100, d_max=5000):
    """Log-scaled accessibility score: 100 at d_ref, 0 at d_max."""
    log_ref = np.log10(max(d_ref, 1))
    log_max = np.log10(d_max)
    log_d = np.log10(np.clip(dist_m, 1, d_max))
    score = np.clip(100 * (log_max - log_d) / (log_max - log_ref), 0, 100)
    return score


def get_qiugang():
    """Get Qiugang Garden data (community_id=0)."""
    return od_df[od_df['community_name'] == '秋港花园'].copy()


def select_20_communities():
    """Select 20 representative communities for the heatmap."""
    comm_med = od_df.groupby('community_name')['nearest_distance_m'].median()
    comm_med = comm_med.sort_values()
    # Pick communities with short names (<=6 chars) for readability
    short = comm_med[comm_med.index.str.len() <= 6]
    if len(short) >= 20:
        idx = np.linspace(0, len(short) - 1, 20, dtype=int)
        names = short.iloc[idx].index.tolist()
    else:
        idx = np.linspace(0, len(comm_med) - 1, 20, dtype=int)
        names = comm_med.iloc[idx].index.tolist()
    # Verify all 6 categories exist for each
    valid = []
    for nm in names:
        sub = od_df[od_df['community_name'] == nm]
        if len(sub) == 6:
            valid.append(nm)
        if len(valid) >= 20:
            break
    # Fill if needed
    if len(valid) < 20:
        for nm in comm_med.index:
            if nm not in valid:
                sub = od_df[od_df['community_name'] == nm]
                if len(sub) == 6:
                    valid.append(nm)
            if len(valid) >= 20:
                break
    return valid[:20]


def grid_helper(ax):
    """Apply standard grid styling."""
    ax.grid(True, **GRID_KW)


def label_panels(axes, labels=('(a)', '(b)', '(c)')):
    """Add (a)(b)(c) panel labels."""
    for ax, lbl in zip(axes, labels):
        ax.text(-0.08, 1.05, lbl, transform=ax.transAxes,
                fontsize=11, fontweight='bold', va='bottom', ha='right')


# ==================================================================
# FIGURE 10: CDF Curves
# ==================================================================
def fig10_cdf():
    fig, ax = plt.subplots(figsize=(8, 5.5))

    for i, (cat, cat_en) in enumerate(zip(CATS, CATS_EN)):
        dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
        xs, ys = compute_ecdf(dists)
        ax.plot(xs, ys * 100, color=PALETTE[i], linewidth=1.8,
                label=f'{cat} {cat_en}')

    # Reference lines
    ax.axvline(1000, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
    ax.axvline(2000, color='gray', linestyle=':', linewidth=0.8, alpha=0.7)
    ax.text(1020, 5, '1 km', fontsize=7.5, color='gray', rotation=90, va='bottom')
    ax.text(2020, 5, '2 km', fontsize=7.5, color='gray', rotation=90, va='bottom')

    ax.set_xlabel('最近设施距离 / Nearest Facility Distance (m)')
    ax.set_ylabel('累计覆盖率 / Cumulative Coverage (%)')
    ax.set_title('图10  各类设施距离累积分布函数\nFig.10  CDF of Nearest Facility Distances by Category')
    ax.set_xlim(0, 5000)
    ax.set_ylim(0, 105)
    ax.legend(loc='lower right', fontsize=8, framealpha=0.9)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig10_v2_cdf.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 11: Summary Bar Chart (mean distance + coverage rates)
# ==================================================================
def fig11_summary():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))

    y_pos = np.arange(len(CATS))
    avg_dists = [stats_df[stats_df['category'] == c]['avg_dist'].values[0] for c in CATS]
    med_dists = [stats_df[stats_df['category'] == c]['median_dist'].values[0] for c in CATS]

    # (a) Mean nearest distance
    bars = ax1.barh(y_pos, avg_dists, color=PALETTE, edgecolor='white', height=0.6)
    # Diamond markers for median
    ax1.scatter(med_dists, y_pos, color='white', edgecolor='black', s=60,
                marker='D', zorder=5, label='中位数 Median')
    for i, (avg, med) in enumerate(zip(avg_dists, med_dists)):
        ax1.text(avg + 50, i, f'{avg:.0f}m', va='center', fontsize=8)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)])
    ax1.set_xlabel('平均最近距离 / Mean Nearest Distance (m)')
    ax1.set_title('(a) 平均最近设施距离\nMean Nearest Facility Distance')
    ax1.legend(loc='lower right', fontsize=8)
    ax1.axvline(1000, color='red', linestyle='--', linewidth=0.6, alpha=0.5)
    ax1.text(1020, 5.2, '1 km', fontsize=7, color='red', alpha=0.6)
    grid_helper(ax1)

    # (b) 1km and 2km coverage rates
    cov1 = [stats_df[stats_df['category'] == c]['within_1km_pct'].values[0] for c in CATS]
    cov2 = [stats_df[stats_df['category'] == c]['within_2km_pct'].values[0] for c in CATS]
    width = 0.35
    x = np.arange(len(CATS))
    bars1 = ax2.bar(x - width / 2, cov1, width, color=PALETTE, edgecolor='white',
                    alpha=0.85, label='1km覆盖率 Within 1km')
    bars2 = ax2.bar(x + width / 2, cov2, width, color=PALETTE, edgecolor='white',
                    alpha=0.45, label='2km覆盖率 Within 2km')
    for bar, val in zip(bars1, cov1):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f'{val:.0f}%', ha='center', va='bottom', fontsize=7)
    for bar, val in zip(bars2, cov2):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f'{val:.0f}%', ha='center', va='bottom', fontsize=7)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax2.set_ylabel('覆盖率 / Coverage Rate (%)')
    ax2.set_ylim(0, 115)
    ax2.set_title('(b) 1km / 2km 覆盖率\n1km / 2km Coverage Rates')
    ax2.legend(loc='lower right', fontsize=8)
    ax2.axhline(80, color='red', linestyle='--', linewidth=0.6, alpha=0.5)
    ax2.text(5.6, 81, '80% 标准', fontsize=7, color='red', alpha=0.6)
    grid_helper(ax2)

    fig.suptitle('图11  坂田街道设施可达性总览\nFig.11  Facility Accessibility Summary for Bantian',
                 fontsize=12, y=1.02)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, 'fig11_v2_summary.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 12: OD Distance Heatmap (20 communities x 6 categories)
# ==================================================================
def fig12_heatmap():
    comm_names = select_20_communities()

    # Build matrix
    matrix = np.zeros((len(comm_names), len(CATS)))
    for j, cat in enumerate(CATS):
        for i, nm in enumerate(comm_names):
            row = od_df[(od_df['community_name'] == nm) & (od_df['category'] == cat)]
            if len(row) > 0:
                matrix[i, j] = row['nearest_distance_m'].values[0]

    # Truncate at 3000m for display
    matrix_disp = np.clip(matrix, 0, 3000)

    fig, ax = plt.subplots(figsize=(9, 9))

    # Custom colormap: green (low) -> yellow -> red (high)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list('gr', ['#228833', '#CCBB44', '#EE6677'])
    im = ax.imshow(matrix_disp, cmap=cmap, aspect='auto', vmin=0, vmax=3000)

    # Labels
    short_names = []
    for nm in comm_names:
        if len(nm) > 8:
            short_names.append(nm[:7] + '..')
        else:
            short_names.append(nm)
    ax.set_yticks(range(len(comm_names)))
    ax.set_yticklabels(short_names, fontsize=7.5)
    ax.set_xticks(range(len(CATS)))
    ax.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)

    # Show numeric values
    for i in range(len(comm_names)):
        for j in range(len(CATS)):
            val = matrix[i, j]
            txt = f'{val:.0f}' if val < 3000 else '3000+'
            text_color = 'white' if matrix_disp[i, j] > 2000 else 'black'
            ax.text(j, i, txt, ha='center', va='center', fontsize=6.5,
                    color=text_color, fontweight='bold')

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label('距离 (m, 截断于3000) / Distance (m, capped at 3000)', fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.set_title('图12  社区-设施OD距离热力图 (前20社区)\n'
                 'Fig.12  OD Distance Heatmap: 20 Communities × 6 Facility Categories',
                 fontsize=11)

    path = os.path.join(FIG_DIR, 'fig12_v2_heatmap.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 13: Lorenz Curves with Gini Coefficients
# ==================================================================
def fig13_lorenz():
    fig, ax = plt.subplots(figsize=(7, 6.5))

    # Equality line
    ax.plot([0, 1], [0, 1], color='gray', linestyle='--', linewidth=1,
            label='完全平等线 Equality Line')

    for i, (cat, cat_en) in enumerate(zip(CATS, CATS_EN)):
        dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
        pop, cum, gini = compute_lorenz(dists)
        ax.plot(pop, cum, color=PALETTE[i], linewidth=1.8,
                label=f'{cat} {cat_en} (Gini={gini:.3f})')

    ax.set_xlabel('社区累计比例 / Cumulative Population Share')
    ax.set_ylabel('距离累计比例 / Cumulative Distance Share')
    ax.set_title('图13  设施可达性洛伦兹曲线与基尼系数\n'
                 'Fig.13  Lorenz Curves with Gini Coefficients')
    ax.legend(loc='upper left', fontsize=7.5, framealpha=0.9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig13_v2_lorenz.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 14: Radar Chart for 秋港花园
# ==================================================================
def fig14_radar():
    qg = get_qiugang()

    # Get distances in category order
    dists = []
    for cat in CATS:
        row = qg[qg['category'] == cat]
        dists.append(row['nearest_distance_m'].values[0] if len(row) > 0 else 0)

    scores = [accessibility_score(d) for d in dists]

    # Radar setup
    angles = np.linspace(0, 2 * np.pi, len(CATS), endpoint=False).tolist()
    scores_closed = scores + [scores[0]]
    dists_closed = dists + [dists[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    ax.plot(angles_closed, scores_closed, color=PALETTE[0], linewidth=2, marker='o',
            markersize=6, markerfacecolor=PALETTE[0])
    ax.fill(angles_closed, scores_closed, color=PALETTE[0], alpha=0.2)

    ax.set_thetagrids(np.degrees(angles),
                      [f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)])
    ax.set_ylim(0, 110)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=7)
    ax.set_rlabel_position(30)

    # Annotate actual distances
    for angle, score, dist, cat in zip(angles, scores, dists, CATS_SHORT):
        ax.annotate(f'{dist:.0f}m',
                    xy=(angle, score),
                    xytext=(angle, score + 12),
                    ha='center', va='center', fontsize=7.5,
                    color=PALETTE[0], fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.8))

    ax.set_title('图14  秋港花园设施可达性雷达图\n'
                 'Fig.14  Accessibility Radar for Qiugang Garden\n'
                 '(对数缩放可达性评分 / Log-scaled Accessibility Score)',
                 fontsize=11, pad=25)

    # Use subplots_adjust instead of tight_layout (polar bug in matplotlib 3.10)
    fig.subplots_adjust(left=0.15, right=0.85, top=0.88, bottom=0.1)

    path = os.path.join(FIG_DIR, 'fig14_v2_radar.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 15: KDE Distance Distributions
# ==================================================================
def fig15_kde():
    fig, ax = plt.subplots(figsize=(8, 5.5))

    x_range = np.linspace(0, 5000, 500)

    for i, (cat, cat_en) in enumerate(zip(CATS, CATS_EN)):
        dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
        if len(dists) > 1:
            kde = stats.gaussian_kde(dists, bw_method=0.3)
            density = kde(x_range)
            ax.plot(x_range, density, color=PALETTE[i], linewidth=1.8,
                    label=f'{cat} {cat_en}')
            ax.fill_between(x_range, density, color=PALETTE[i], alpha=0.1)

    ax.axvline(1000, color='gray', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.text(1020, ax.get_ylim()[1] * 0.9, '1 km', fontsize=7.5, color='gray')
    ax.axvline(2000, color='gray', linestyle=':', linewidth=0.8, alpha=0.6)
    ax.text(2020, ax.get_ylim()[1] * 0.9, '2 km', fontsize=7.5, color='gray')

    ax.set_xlabel('最近设施距离 / Nearest Facility Distance (m)')
    ax.set_ylabel('概率密度 / Probability Density')
    ax.set_title('图15  各类设施距离核密度估计\nFig.15  KDE of Nearest Facility Distances')
    ax.set_xlim(0, 5000)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig15_v2_kde.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 16: Box Plots
# ==================================================================
def fig16_boxplot():
    fig, ax = plt.subplots(figsize=(9, 6))

    data_boxes = []
    for cat in CATS:
        dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
        data_boxes.append(dists)

    bp = ax.boxplot(data_boxes, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=1.5),
                    whiskerprops=dict(linewidth=0.8),
                    capprops=dict(linewidth=0.8),
                    flierprops=dict(marker='o', markersize=3, alpha=0.5))

    for i, patch in enumerate(bp['boxes']):
        patch.set_facecolor(PALETTE[i])
        patch.set_alpha(0.7)
        patch.set_edgecolor('black')

    # Mark 秋港花园 as gold star
    qg = get_qiugang()
    for i, cat in enumerate(CATS):
        row = qg[qg['category'] == cat]
        if len(row) > 0:
            d = row['nearest_distance_m'].values[0]
            ax.scatter(i + 1, d, color='gold', marker='*', s=150, zorder=5,
                       edgecolors='black', linewidths=0.5)

    # 1km reference line
    ax.axhline(1000, color='red', linestyle='--', linewidth=0.8, alpha=0.7)
    ax.text(6.3, 1020, '1 km', fontsize=7.5, color='red', alpha=0.7)
    ax.axhline(2000, color='red', linestyle=':', linewidth=0.8, alpha=0.5)
    ax.text(6.3, 2020, '2 km', fontsize=7.5, color='red', alpha=0.5)

    ax.set_xticks(range(1, len(CATS) + 1))
    ax.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax.set_ylabel('最近设施距离 / Nearest Facility Distance (m)')
    ax.set_title('图16  各类设施距离箱线图\nFig.16  Box Plots of Nearest Facility Distances\n'
                 '(★ = 秋港花园 Qiugang Garden)', fontsize=11)
    ax.set_ylim(0, 5000)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig16_v2_boxplot.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 17: GB/T 50180-2018 Compliance
# ==================================================================
def fig17_standard():
    fig, ax = plt.subplots(figsize=(9, 6))

    x = np.arange(len(CATS))
    width = 0.35

    cov1 = [stats_df[stats_df['category'] == c]['within_1km_pct'].values[0] for c in CATS]
    stds = [GBT_STD[c] for c in CATS]

    bars_actual = ax.bar(x - width / 2, cov1, width, color=PALETTE, edgecolor='white',
                         alpha=0.85, label='实际覆盖率 Actual Coverage')
    bars_std = ax.bar(x + width / 2, stds, width, color='gray', edgecolor='white',
                      alpha=0.4, label='GB/T 50180-2018 标准')

    # Compliance markers
    for i, (actual, std) in enumerate(zip(cov1, stds)):
        passed = actual >= std
        marker = '\u2713' if passed else '\u2717'  # checkmark or X
        color = '#228833' if passed else '#EE6677'
        y_pos = max(actual, std) + 5
        ax.text(i, y_pos, marker, ha='center', va='bottom', fontsize=16,
                color=color, fontweight='bold')
        # Also show actual value
        ax.text(i - width / 2, actual + 1, f'{actual:.0f}%', ha='center',
                va='bottom', fontsize=7, color=PALETTE[i])
        ax.text(i + width / 2, std + 1, f'{std}%', ha='center',
                va='bottom', fontsize=7, color='gray')

    ax.set_xticks(x)
    ax.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax.set_ylabel('1km覆盖率 / 1km Coverage Rate (%)')
    ax.set_ylim(0, 120)
    ax.set_title('图17  GB/T 50180-2018 达标评估\n'
                 'Fig.17  Compliance Assessment against GB/T 50180-2018\n'
                 '(\u2713 = 达标 Compliant,  \u2717 = 不达标 Non-compliant)', fontsize=11)
    ax.legend(loc='lower left', fontsize=8)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig17_v2_standard.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 18: Real Routes Comparison (Walking / Transit / Driving)
# ==================================================================
def fig18_real_routes():
    fig, axes = plt.subplots(1, 3, figsize=(16, 6))

    # Organize by normalized category and mode
    modes = ['walking', 'transit', 'driving']
    mode_labels = {'walking': '步行 Walk', 'transit': '公交 Transit', 'driving': '驾车 Drive'}
    mode_colors = {'walking': PALETTE[2], 'transit': PALETTE[0], 'driving': PALETTE[1]}

    # Get 6 main categories from routes
    route_cats = [c for c in CATS if c in routes_df['cat6'].values]

    # Build summary by category and mode
    summary = {}
    for cat in route_cats:
        summary[cat] = {}
        for mode in modes:
            sub = routes_df[(routes_df['cat6'] == cat) & (routes_df['route_type'] == mode)]
            if len(sub) > 0:
                summary[cat][mode] = {
                    'avg_dist': sub['distance_m'].mean(),
                    'avg_time': sub['duration_min'].mean(),
                    'count': len(sub)
                }

    # (a) Distance comparison
    ax1 = axes[0]
    x = np.arange(len(route_cats))
    width = 0.25
    for k, mode in enumerate(modes):
        vals = []
        for cat in route_cats:
            if mode in summary.get(cat, {}):
                vals.append(summary[cat][mode]['avg_dist'])
            else:
                vals.append(0)
        bars = ax1.bar(x + k * width, vals, width, color=mode_colors[mode],
                       edgecolor='white', alpha=0.85, label=mode_labels[mode])
    ax1.set_xticks(x + width)
    ax1.set_xticklabels([CATS_SHORT[CATS.index(c)] for c in route_cats], fontsize=7.5, rotation=15)
    ax1.set_ylabel('平均距离 / Avg Distance (m)')
    ax1.set_title('(a) 实际出行距离比较\nReal Route Distance Comparison')
    ax1.legend(fontsize=7.5)
    grid_helper(ax1)

    # (b) Time comparison
    ax2 = axes[1]
    for k, mode in enumerate(modes):
        vals = []
        for cat in route_cats:
            if mode in summary.get(cat, {}):
                vals.append(summary[cat][mode]['avg_time'])
            else:
                vals.append(0)
        ax2.bar(x + k * width, vals, width, color=mode_colors[mode],
                edgecolor='white', alpha=0.85, label=mode_labels[mode])
    ax2.set_xticks(x + width)
    ax2.set_xticklabels([CATS_SHORT[CATS.index(c)] for c in route_cats], fontsize=7.5, rotation=15)
    ax2.set_ylabel('平均时间 / Avg Time (min)')
    ax2.set_title('(b) 实际出行时间比较\nReal Route Time Comparison')
    ax2.legend(fontsize=7.5)
    grid_helper(ax2)

    # (c) Average speed and mode recommendation
    ax3 = axes[2]
    # Calculate average speed for each mode (across all routes)
    avg_speeds = {}
    for mode in modes:
        sub = routes_df[routes_df['route_type'] == mode]
        if len(sub) > 0:
            avg_speeds[mode] = (sub['distance_m'] / sub['duration_min']).mean() * 60 / 1000  # km/h
        else:
            avg_speeds[mode] = 0

    speed_vals = [avg_speeds[m] for m in modes]
    bars = ax3.bar([mode_labels[m] for m in modes], speed_vals,
                   color=[mode_colors[m] for m in modes], edgecolor='white', alpha=0.85)
    for bar, val in zip(bars, speed_vals):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f'{val:.1f} km/h', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Add recommendation text
    rec_text = (
        "出行建议 Recommendation:\n"
        "• <1km: 步行 Walking\n"
        "• 1-3km: 公交 Transit\n"
        "• >3km: 驾车 Driving"
    )
    ax3.text(0.05, 0.95, rec_text, transform=ax3.transAxes,
             fontsize=8, va='top', ha='left',
             bbox=dict(boxstyle='round,pad=0.5', fc='#F8F8F8', ec='#CCCCCC', alpha=0.9))

    ax3.set_ylabel('平均速度 / Avg Speed (km/h)')
    ax3.set_title('(c) 出行速度与方式建议\nTravel Speed & Mode Recommendation')
    grid_helper(ax3)

    fig.suptitle('图18  多模式实际出行路线比较 (秋港花园出发)\n'
                 'Fig.18  Multi-Modal Real Route Comparison (from Qiugang Garden)',
                 fontsize=12, y=1.02)
    fig.tight_layout()

    path = os.path.join(FIG_DIR, 'fig18_v2_real_routes.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 19: Old vs New Data Comparison
# ==================================================================
def fig19_old_vs_new():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))

    x = np.arange(len(CATS))
    width = 0.35

    old_dists = [OLD_DIST[c] for c in CATS]
    new_dists = [stats_df[stats_df['category'] == c]['avg_dist'].values[0] for c in CATS]
    old_covs = [OLD_COV1[c] for c in CATS]
    new_covs = [stats_df[stats_df['category'] == c]['within_1km_pct'].values[0] for c in CATS]

    # (a) Mean distances
    bars_old = ax1.bar(x - width / 2, old_dists, width, color='#CCCCCC', edgecolor='white',
                       alpha=0.8, label='旧数据 OSM-only (Old)')
    bars_new = ax1.bar(x + width / 2, new_dists, width, color=PALETTE, edgecolor='white',
                       alpha=0.85, label='新数据 Gaode+OSM (New)')
    for bar, val in zip(bars_old, old_dists):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 50,
                 f'{val}', ha='center', va='bottom', fontsize=7, color='gray')
    for bar, val in zip(bars_new, new_dists):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 50,
                 f'{val:.0f}', ha='center', va='bottom', fontsize=7)

    # Show improvement percentages
    for i, (old, new) in enumerate(zip(old_dists, new_dists)):
        if old > 0:
            improve = (old - new) / old * 100
            ax1.text(i, max(old, new) + 250,
                     f'\u2193{improve:.0f}%', ha='center', fontsize=7,
                     color='#228833', fontweight='bold')

    ax1.set_xticks(x)
    ax1.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax1.set_ylabel('平均最近距离 / Mean Nearest Distance (m)')
    ax1.set_title('(a) 平均最近距离对比\nMean Nearest Distance: Old vs New')
    ax1.legend(loc='upper right', fontsize=8)
    grid_helper(ax1)

    # (b) 1km coverage rates
    bars_old2 = ax2.bar(x - width / 2, old_covs, width, color='#CCCCCC', edgecolor='white',
                        alpha=0.8, label='旧数据 OSM-only (Old)')
    bars_new2 = ax2.bar(x + width / 2, new_covs, width, color=PALETTE, edgecolor='white',
                        alpha=0.85, label='新数据 Gaode+OSM (New)')
    for bar, val in zip(bars_old2, old_covs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f'{val}%', ha='center', va='bottom', fontsize=7, color='gray')
    for bar, val in zip(bars_new2, new_covs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f'{val:.0f}%', ha='center', va='bottom', fontsize=7)

    ax2.set_xticks(x)
    ax2.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax2.set_ylabel('1km覆盖率 / 1km Coverage Rate (%)')
    ax2.set_ylim(0, 120)
    ax2.set_title('(b) 1km覆盖率对比\n1km Coverage Rate: Old vs New')
    ax2.legend(loc='lower right', fontsize=8)
    ax2.axhline(80, color='red', linestyle='--', linewidth=0.6, alpha=0.5)
    ax2.text(5.5, 81, '80% 标准', fontsize=7, color='red', alpha=0.5)
    grid_helper(ax2)

    fig.suptitle('图19  数据质量提升效果 (OSM-only vs Gaode+OSM)\n'
                 'Fig.19  Data Quality Improvement: Old (OSM-only) vs New (Gaode+OSM)',
                 fontsize=12, y=1.02)
    fig.tight_layout()

    path = os.path.join(FIG_DIR, 'fig19_v2_old_vs_new.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 20: Violin Plots (Equity Analysis)
# ==================================================================
def fig20_equity():
    fig, ax = plt.subplots(figsize=(10, 6))

    data_violins = []
    for cat in CATS:
        dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
        data_violins.append(dists)

    positions = range(1, len(CATS) + 1)
    parts = ax.violinplot(data_violins, positions=positions, showmeans=True,
                          showmedians=True, showextrema=False)

    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(PALETTE[i])
        pc.set_alpha(0.5)
        pc.set_edgecolor('black')
        pc.set_linewidth(0.5)

    if 'cmeans' in parts:
        parts['cmeans'].set_color('red')
        parts['cmeans'].set_linewidth(1.5)
        parts['cmeans'].set_linestyle('--')
    if 'cmedians' in parts:
        parts['cmedians'].set_color('blue')
        parts['cmedians'].set_linewidth(1.5)
        parts['cmedians'].set_linestyle('-')

    # Add mean and median value annotations
    for i, cat in enumerate(CATS):
        dists = data_violins[i]
        mean_val = np.mean(dists)
        median_val = np.median(dists)
        ax.scatter(i + 1, mean_val, color='red', marker='D', s=30, zorder=5)
        ax.scatter(i + 1, median_val, color='blue', marker='s', s=30, zorder=5)
        ax.text(i + 1.15, mean_val, f'\u03bc={mean_val:.0f}', fontsize=6.5,
                color='red', va='center')
        ax.text(i + 1.15, median_val, f'M={median_val:.0f}', fontsize=6.5,
                color='blue', va='center')

    # Reference lines
    ax.axhline(1000, color='gray', linestyle='--', linewidth=0.6, alpha=0.5)
    ax.text(6.5, 1020, '1 km', fontsize=7, color='gray', alpha=0.5)

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='red', linestyle='--', linewidth=1.5, label='均值 Mean'),
        Line2D([0], [0], color='blue', linestyle='-', linewidth=1.5, label='中位数 Median'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

    ax.set_xticks(positions)
    ax.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax.set_ylabel('最近设施距离 / Nearest Facility Distance (m)')
    ax.set_title('图20  设施可达性空间公平性分析 (小提琴图)\n'
                 'Fig.20  Spatial Equity Analysis: Violin Plots of Distance Distributions',
                 fontsize=11)
    ax.set_ylim(0, 5000)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig20_v2_equity.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# FIGURE 21: 15-Minute City Assessment (Stacked Bar)
# ==================================================================
def fig21_15min():
    fig, ax = plt.subplots(figsize=(9, 6))

    # Define accessibility levels
    levels = ['优秀 Excellent\n(≤500m)', '良好 Good\n(500-1000m)',
              '一般 Fair\n(1000-2000m)', '较差 Poor\n(>2000m)']
    level_colors = ['#228833', '#66CCEE', '#CCBB44', '#EE6677']

    x = np.arange(len(CATS))
    bottom = np.zeros(len(CATS))

    # Calculate percentage of communities at each level
    for lvl_idx, (lo, hi) in enumerate([(0, 500), (500, 1000), (1000, 2000), (2000, 99999)]):
        pcts = []
        for cat in CATS:
            dists = od_df[od_df['category'] == cat]['nearest_distance_m'].values
            n = len(dists)
            count = np.sum((dists >= lo) & (dists < hi))
            pcts.append(count / n * 100)

        bars = ax.bar(x, pcts, bottom=bottom, color=level_colors[lvl_idx],
                      edgecolor='white', linewidth=0.5, alpha=0.85,
                      label=levels[lvl_idx])

        # Add percentage labels
        for i, (pct, bot) in enumerate(zip(pcts, bottom)):
            if pct > 3:  # Only label if segment is big enough
                ax.text(i, bot + pct / 2, f'{pct:.0f}%',
                        ha='center', va='center', fontsize=7, fontweight='bold',
                        color='white' if lvl_idx in [0, 3] else 'black')

        bottom += np.array(pcts)

    ax.set_xticks(x)
    ax.set_xticklabels([f'{c}\n{e}' for c, e in zip(CATS_SHORT, CATS_EN)], fontsize=8)
    ax.set_ylabel('社区占比 / Percentage of Communities (%)')
    ax.set_ylim(0, 105)
    ax.set_title('图21  15分钟生活圈可达性等级评估\n'
                 'Fig.21  15-Minute City Accessibility Level Assessment', fontsize=11)
    ax.legend(loc='upper right', fontsize=7.5, framealpha=0.9)
    grid_helper(ax)

    path = os.path.join(FIG_DIR, 'fig21_v2_15min.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    return path


# ==================================================================
# MAIN EXECUTION
# ==================================================================
if __name__ == '__main__':
    print('='*60)
    print('Generating 12 Publication-Quality Figures (v2)')
    print('='*60)
    print()

    paths = []
    funcs = [
        ('Fig.10 CDF Curves', fig10_cdf),
        ('Fig.11 Summary Bars', fig11_summary),
        ('Fig.12 OD Heatmap', fig12_heatmap),
        ('Fig.13 Lorenz Curves', fig13_lorenz),
        ('Fig.14 Radar Chart', fig14_radar),
        ('Fig.15 KDE Plots', fig15_kde),
        ('Fig.16 Box Plots', fig16_boxplot),
        ('Fig.17 GB/T Compliance', fig17_standard),
        ('Fig.18 Real Routes', fig18_real_routes),
        ('Fig.19 Old vs New', fig19_old_vs_new),
        ('Fig.20 Violin/Equity', fig20_equity),
        ('Fig.21 15-Min City', fig21_15min),
    ]

    for name, func in funcs:
        print(f'Generating {name}...')
        try:
            p = func()
            paths.append(p)
        except Exception as e:
            print(f'  ERROR in {name}: {e}')
            import traceback
            traceback.print_exc()
            paths.append(None)

    print()
    print('='*60)
    print('All figures generated successfully!')
    print('='*60)
    print()
    print('Output file paths:')
    for p in paths:
        if p:
            print(f'  {p}')
        else:
            print('  [FAILED]')

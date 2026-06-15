# 坂田片区15分钟生活圈可达性分析

**Bantian 15-Minute Living Circle Accessibility Analysis**

GIS与空间分析技术课程大作业 — 基于多源地理数据的城市公共服务设施可达性评估

GIS & Spatial Analysis Coursework — Multi-source geospatial data-based accessibility assessment of urban public service facilities

## 研究区域 Study Area

深圳市龙岗区坂田街道，以华为员工配套社区秋港花园为中心，半径3km范围

Bantian Sub-district, Longgang District, Shenzhen — centered on Qiugang Garden (Huawei employee housing), 3km radius

## 核心发现 Key Findings

**"五达标一缺口"格局 Five Compliant, One Deficit:**

| 设施类别 | 均值(m) | 1km覆盖率 | 国标 | 达标 |
|---------|---------|----------|------|------|
| 商业服务 | 141 | 98.9% | ≥80% | ✓ |
| 公园绿地 | 347 | 94.3% | ≥80% | ✓ |
| 医疗设施 | 270 | 96.6% | ≥80% | ✓ |
| 公交站 | 217 | 100% | ≥80% | ✓ |
| 地铁站 | 941 | 82.9% | ≥60% | ✓ |
| **教育设施** | **1,738** | **44.0%** | **≥70%** | **✗** |

## 数据来源 Data Sources

- **高德地图API (Gaode/Amap API):** 1,171周边POI + 355关键词POI + 75公交站点 + 71条多模式路径规划
- **OpenStreetMap (OSM):** 道路网络拓扑（5,575节点, 5,888条边）
- **坐标系:** CGCS2000 3度带38投影（中央经线114°, 东偏移38500000m）

## 目录结构 Directory Structure

```
bantian-od-analysis/
├── database/                  # SQLite数据库 + CSV导出
│   ├── bantian_od_v2.db       # v2主数据库（OD矩阵+统计+路径）
│   ├── bantian_transport_network.db  # 原始路网数据库
│   ├── od_statistics_v2.csv   # 6类设施OD统计汇总
│   └── real_routes_comparison.csv    # 多模式路径对比
├── figures/                   # 12张出版级分析图表 (fig10-fig21)
│   ├── fig10_v2_cdf.png       # CDF累积分布曲线
│   ├── fig13_v2_lorenz.png    # 洛伦兹曲线与基尼系数
│   ├── fig17_v2_standard.png  # GB/T 50180达标评估
│   ├── fig18_v2_real_routes.png  # 多模式路径对比
│   └── fig19_v2_old_vs_new.png   # OSM vs 高德数据质量对比
├── shapefiles_cgcs2000/       # CGCS2000投影Shapefile
├── discussion_chapter.md      # 讨论章节（中英双语）
├── gaode_comprehensive.py     # 高德API数据采集脚本
├── rebuild_od_v2.py           # OD矩阵重建脚本
├── publication_figures_v2.py # 出版级图表生成脚本
├── multi_service_od.py        # 多设施OD分析脚本
└── generate_mxd.py            # ArcGIS MXD生成脚本
```

## 技术栈 Tech Stack

- Python 3 (networkx, scipy, numpy, matplotlib, pandas)
- SQLite (OD矩阵存储)
- ArcGIS/QGIS (空间数据管理)
- 高德Web Service API (POI采集+路径规划)
- OSM Overpass API (路网数据)

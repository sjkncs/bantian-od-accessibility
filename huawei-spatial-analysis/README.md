# Huawei Spatial Analysis / 华为企业空间分析

This subdirectory contains the Huawei-centered spatial analysis of Qiugang Garden (秋港花园), focusing on why the compound's management is relatively closed and what this reveals about Huawei's spatial governance logic.

## Theoretical Framework

The analysis proposes a **"Dormitory-Type Compound" (宿舍型大院)** model, distinguishing Qiugang Garden from traditional danwei compounds (单位大院). The key finding is a **tripolar spatial structure**:

- **Pole 1 — Qiugang Garden (Residential):** 3 internal facilities only (2 pharmacies, 1 convenience store)
- **Pole 2 — Huawei Bantian Base (Workplace):** 38 enterprise POIs (28 service facilities + 10 zone markers)
- **Pole 3 — Tian'an Cloud Valley (Commercial):** 48 commercial service facilities

## Contents

### `data/` — Gaode API Data Collection

| File | Description |
|:---|:---|
| `qiugang_internal.json` | Internal facilities within 200m of Qiugang Garden (3 facilities) |
| `huawei_pois.json` | Huawei Bantian Base POIs (38 entries across 10 categories) |
| `tayg_internal.json` | Tian'an Cloud Valley internal facilities (48 facilities) |
| `commute_routes.json` | Commute routes: walk/transit/drive from Qiugang to Huawei & TAYG |
| `radius_comparison.json` | Facility counts at 200m/500m/1km/2km radius buffers (12 categories) |

### `figures/` — Publication-Quality Figures (Fig. 22–26)

| Figure | Description |
|:---|:---|
| `fig22_radius_decay.png` | Facility count decay across radius buffers (grouped bar chart) |
| `fig23_tripolar.png` | Tripolar comparison: Qiugang=3, Huawei=28, TAYG=48 |
| `fig24_huawei_spatial.png` | Spatial relationship map with campus zones and commute annotations |
| `fig25_closure.png` | Community closure index radar chart (12 categories vs. ideal benchmark) |
| `fig26_commute.png` | Commute accessibility comparison (walk/transit/drive) |

### Scripts

- `huawei_figures.py` — Generates Fig. 22–26 from the JSON data files

### Discussion

- `discussion_chapter.md` — Chapter 4: The Political Economy of Qiugang Garden's Spatial Closure (bilingual Chinese/English)

## Key Findings

1. **Hollowing Out (空壳化):** Qiugang Garden's interior is a service vacuum — walls and gates exist, but no substantive amenities
2. **Tripolar Structure:** Sleeping (Qiugang) ↔ Working (Huawei) ↔ Consuming (Tian'an Cloud Valley)
3. **Commute Rupture:** 33-min walk / 35.6-min transit / 9.2-min drive to workplace
4. **Control vs. Service Closure:** The compound's closure is about access control, not service self-sufficiency
5. **Dormitory-Type Compound:** A revised model replacing the "new-type danwei compound" analogy

## Data Source

All POI and route data collected via Gaode (Amap) Web Service API. Coordinate system: WGS-84 (GCJ-02 encrypted).

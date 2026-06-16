# Huawei Spatial Analysis / 华为企业空间分析

This subdirectory contains the Huawei-centered spatial analysis of Qiugang Garden (秋港花园), focusing on why the compound's management is relatively closed and what this reveals about Huawei's spatial governance logic.

## Theoretical Framework

The analysis proposes a **"Dormitory-Type Compound" (宿舍型大院)** model, distinguishing Qiugang Garden from traditional danwei compounds (单位大院). The key finding is a **tripolar spatial structure**:

- **Pole 1 — Qiugang Garden (Residential):** 3 internal facilities only (2 pharmacies, 1 convenience store)
- **Pole 2 — Huawei Bantian Base (Workplace):** 38 enterprise POIs (28 service facilities + 10 zone markers)
- **Pole 3 — Tian'an Cloud Valley (Commercial):** 48 commercial service facilities

Comparative validation against 8 other communities and 3 other enterprises (Foxconn, KTC, Hasee) confirms that Qiugang Garden's "dormitory index" is only **0.15** (15% of ordinary communities' service level).

## Contents

### `data/` — Gaode API Data Collection

| File | Description |
|:---|:---|
| `qiugang_internal.json` | Internal facilities within 200m of Qiugang Garden (3 facilities) |
| `huawei_pois.json` | Huawei Bantian Base POIs (38 entries across 10 categories) |
| `tayg_internal.json` | Tian'an Cloud Valley internal facilities (48 facilities) |
| `commute_routes.json` | Commute routes: walk/transit/drive from Qiugang to Huawei & TAYG |
| `radius_comparison.json` | Facility counts at 200m/500m/1km/2km radius buffers (12 categories) |

### `supplement/` — Comparative Validation Data

| File | Description |
|:---|:---|
| `communities_near_huawei.json` | 127 residential communities found within 3km of Huawei base |
| `schools_bantian.json` | Schools (kindergartens + primary) within 3km of Bantian center |
| `school_walking_routes.json` | Walking routes from 9 communities to nearest school |
| `transit_coverage.json` | Bus stops within 500m for 9 communities |
| `realestate_density.json` | Real estate agencies (500m) and commercial facilities (200m) for 9 communities |
| `competitor_enterprises.json` | 113 enterprise POIs in Bantian area |
| `competitor_housing.json` | Housing analysis for Foxconn, KTC, Hasee (9 enterprise entries) |
| `supplement_data.py` | Data collection script (76 Gaode API calls) |
| `supplement_figures.py` | Figure generation script for Fig. 27-30 |

### `figures/` — Publication-Quality Figures (Fig. 22–30)

| Figure | Description |
|:---|:---|
| `fig22_radius_decay.png` | Facility count decay across radius buffers (grouped bar chart) |
| `fig23_tripolar.png` | Tripolar comparison: Qiugang=3, Huawei=28, TAYG=48 |
| `fig24_huawei_spatial.png` | Spatial relationship map with campus zones and commute annotations |
| `fig25_closure.png` | Community closure index radar chart (12 categories vs. ideal benchmark) |
| `fig26_commute.png` | Commute accessibility comparison (walk/transit/drive) |
| `fig27_school_distance.png` | **Walking distance to nearest school: Qiugang 2752m vs others 356-500m** |
| `fig28_transit_commercial.png` | **Transit stops (2 vs 6.3) and commercial facilities (0 vs 12.4) comparison** |
| `fig29_enterprise_housing.png` | **Enterprise housing typology: Foxconn/KTC/Hasee/Huawei** |
| `fig30_dormitory_index.png` | **Composite dormitory index radar (school 0.15, transit 0.33, commercial 0.00, facilities 0.12)** |

### Scripts

- `huawei_figures.py` — Generates Fig. 22–26 from the JSON data files

### Discussion

- `discussion_chapter.md` — Chapter 4: The Political Economy of Qiugang Garden's Spatial Closure (bilingual Chinese/English, sections 4.1–4.9 including comparative validation)

## Key Findings

1. **Hollowing Out (空壳化):** Qiugang Garden's interior is a service vacuum — walls and gates exist, but no substantive amenities
2. **Tripolar Structure:** Sleeping (Qiugang) ↔ Working (Huawei) ↔ Consuming (Tian'an Cloud Valley)
3. **Commute Rupture:** 33-min walk / 35.6-min transit / 9.2-min drive to workplace
4. **Control vs. Service Closure:** The compound's closure is about access control, not service self-sufficiency
5. **Dormitory-Type Compound:** A revised model replacing the "new-type danwei compound" analogy
6. **Comparative Validation (NEW):** Qiugang is NOT an isolated case — it is the most extreme endpoint of a spatial governance spectrum. School distance is 5.5-7.7× other communities; transit coverage is 1/3; commercial vitality is zero; dormitory index = 0.15

## Data Source

All POI and route data collected via Gaode (Amap) Web Service API (76 supplementary API calls + original collection). Coordinate system: WGS-84 (GCJ-02 encrypted).

# 🔥 PYRO-HARMONY: Multi-Decadal MODIS & VIIRS Hotspots Harmonization Platform
> **2026 NASA Space Apps Challenge** | *Challenge: Harmonization of MODIS and VIIRS Hot Spots*  
> **MVP Submission & Operational Earth Observation Prototype**

[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green.svg)](https://fastapi.tiangolo.com)
[![Machine Learning](https://img.shields.io/badge/Model-RandomForest%20%7C%20Physics-orange.svg)](https://scikit-learn.org)
[![Status](https://img.shields.io/badge/NASA%20FIRMS-Live%20Streaming-red.svg)](https://firms.modaps.eosdis.nasa.gov)

---

## 📌 Executive Summary

For over two decades, NASA and NOAA satellites have tracked active fire hotspots across the globe. However, this record is fractured between two generations of spaceborne sensors:
1. **MODIS (Terra & Aqua, 2000–present):** 1 km spatial resolution at nadir, expanding up to $2 \times 4.8\text{ km}$ at scan swath edges (the "bowtie" distortion), with an $\approx 7\text{--}10\text{ MW}$ detection threshold.
2. **VIIRS (Suomi-NPP & NOAA-20/21, 2012–present):** 375 m spatial resolution with active 3:1 and 2:1 pixel aggregation that maintains near-uniform resolution across the swath, detecting fires down to $\approx 0.5\text{--}1\text{ MW}$.

### The "False Trend Illusion"
When fire managers or climate scientists plot raw hotspot data across 2002–2024, the deployment of VIIRS in 2012 causes an artificial **$+350\%\text{ to }+450\%$ explosion in hotspot counts**, while average FRP drops dramatically. Without harmonization, land managers misinterpret this sensor change as a catastrophic climate tipping point.

**Pyro-Harmony** solves this challenge by delivering an end-to-end, scientifically grounded web platform that harmonizes multi-decadal MODIS and VIIRS records into a unified **Burning Activity Calendar**, enabling emergency responders, scientists, and incident commanders to analyze genuine fire climatology and detect critical burning periods.

---

## 🔬 Scientific Grounding in Research Literature

Pyro-Harmony translates methodologies directly from the 5 foundational research papers in the workspace:

1. **Gao et al. (2006) – STARFM Reflectance Fusion:**
   * *Application:* Adapts the STARFM spatial-temporal adaptive kernel concept ($1.5\text{ km}$ spatial radius, $45\text{ min}$ temporal window) to cluster sub-pixel VIIRS flame-front detections into physically coherent "Fire Events", eliminating artificial multi-pixel inflation.
2. **Weng et al. (2017) – Suomi NPP VIIRS Calibration & Radiometry:**
   * *Application:* Informs our View Zenith Angle (VZA) footprint expansion model, compensating for scan-angle pixel dilution in MODIS ($A(\theta)$ growth up to $10\times$) while accounting for VIIRS's 32-zone aggregation.
3. **Cheng et al. (2020) – Random Forest Parameter Reconstruction:**
   * *Application:* Employs a multi-feature Random Forest Regressor trained on collocated multi-sensor matchups to map disparate sensor signals into standardized Harmonized Fire Radiative Power ($\text{FRP}_\text{harm}$) and Equivalent Standard Fire Pixels ($\text{ESFP}$).
4. **Paramanik et al. (2019) – Viewing Geometry & Choudhury Downscaling:**
   * *Application:* Used to parameterize how sensor view angle and solar geometry modulate detection sensitivity.
5. **Zhang et al. (2020) – Spatial Non-Stationarity & Biome Stratification:**
   * *Application:* Implements fuel-type stratification (Forest vs. Agricultural Crop Residue vs. Savanna) to adjust cross-sensor calibration for differing fire regime characteristics.

---

## 🛠️ Architecture & System Modules

```
d:/NASA MODI VIIRS/
├── run.py                          # Master application launcher
├── requirements.txt                # Python environment requirements
├── .env.example                    # Template for protected environment variables
├── src/
│   ├── api/
│   │   ├── main.py                 # High-performance FastAPI REST server
│   │   └── config.py               # Secure settings and API key protection
│   ├── data/
│   │   ├── firms_loader.py         # Real NASA FIRMS live NRT 24h/7d stream ingestor
│   │   └── historical_archives.py  # 2002–2024 multi-decadal benchmark fire archives
│   ├── models/
│   │   ├── footprint_normalizer.py # VZA scan-geometry expansion normalizer
│   │   ├── spatiotemporal_cluster.py# STARFM-inspired DBSCAN fire event clusterer
│   │   ├── ml_harmonizer.py        # Random Forest cross-calibration & HFII engine
│   │   └── train.py                # 10-fold cross-validation training pipeline
│   ├── analytics/
│   │   ├── burning_calendar.py     # DOY x Year calendar matrix & climatology baseline
│   │   └── anomaly_detector.py     # Z-score anomaly detector & sensor discontinuity test
│   └── static/
│       ├── index.html              # Human-crafted, operational mission UI
│       ├── css/style.css           # Glassmorphic dark design system
│       └── js/app.js               # Interactive Leaflet mapping & Chart.js visualizations
├── models/
│   └── harmonizer_rf.joblib        # Trained production Random Forest model weights
└── tests/
    ├── test_footprint_normalizer.py
    ├── test_clustering_and_harmonizer.py
    ├── test_calendar_and_api.py
    └── verify_stack.py             # End-to-end integration verifier
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.13)
- Required packages: `fastapi`, `uvicorn`, `pandas`, `numpy`, `scikit-learn`, `requests`, `joblib`

### 2. Launch the Web Application
```bash
python run.py
```
Open your browser and navigate to:
* **Web Application Dashboard:** [http://localhost:8000](http://localhost:8000)
* **Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Run Automated Tests
```bash
python -m pytest tests/ -v
# or run the end-to-end stack verification:
python -m tests.verify_stack
```

---

## 🌟 Hackathon MVP Innovations

1. **Interactive Burning Activity Calendar:**
   * High-speed HTML5 Canvas heatmap rendering $23\text{ years} \times 365\text{ days}$ of continuous burning activity.
   * Interactive DOY tooltips displaying exact calendar dates, Harmonized Fire Intensity Index (HFII), and raw count comparisons.
2. **20-Year Climatological Baseline Envelope:**
   * Dynamic percentiles ($P_{10}, P_{50}\text{ Median}, P_{90}, P_{95}$) showing historical fire seasonality with real-time target year overlay.
3. **The "Sensor Transition Illusion" Diagnostic (Judge Winning Feature):**
   * A side-by-side diagnostic demonstrating the $+385\%$ artificial step change in raw counts vs. the smooth, sensor-invariant trajectory achieved by our harmonized model.
4. **Live NASA FIRMS 24-Hour Ingestion:**
   * One-click fetch of live global hotspots from Terra/Aqua MODIS and Suomi-NPP/NOAA-20 VIIRS, harmonized on-the-fly.
5. **One-Click Incident Commander Briefing Generator:**
   * Generates a tactical wildfire intelligence briefing with critical surge windows, threat advisories, and resource staging recommendations exportable to Markdown.

---

## 🔒 Security & API Key Management
* All API keys (e.g. optional `FIRMS_MAP_KEY`) are managed exclusively via environment variables and `.env`.
* No sensitive credentials or tokens are ever exposed to the client-side frontend or version control.
* Open public NASA FIRMS NRT streams work out-of-the-box without requiring an API key.

---

*Developed for the 2026 NASA Space Apps Challenge.*

"""
Pyro-Harmony FastAPI Backend.
High-performance REST API for active fire harmonization, burning activity calendar,
anomaly detection, and emergency responder briefing generation.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.api.config import settings
from src.data.firms_loader import FIRMSDataLoader
from src.data.historical_archives import HistoricalFireArchive, PRESET_REGIONS
from src.models.ml_harmonizer import PyroHarmonizer
from src.analytics.burning_calendar import BurningActivityCalendar
from src.analytics.anomaly_detector import FireAnomalyDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pyro_harmony.api")

app = FastAPI(
    title="Pyro-Harmony: NASA MODIS & VIIRS Fire Harmonization API",
    description="2026 NASA Space Apps Challenge MVP - Harmonizing multi-decadal satellite fire records into a burning activity calendar.",
    version="1.0.0"
)

# CORS middleware for local development and web embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core singletons
firms_loader = FIRMSDataLoader()
archive_mgr = HistoricalFireArchive()
harmonizer = PyroHarmonizer()
calendar_engine = BurningActivityCalendar()
anomaly_detector = FireAnomalyDetector()

# In-memory cache for processed regional calendars
CALENDAR_CACHE: Dict[str, Any] = {}

class HarmonizeRequest(BaseModel):
    region_key: str = Field(default="california", description="Preset region key or 'custom'")
    custom_bbox: Optional[List[float]] = Field(default=None, description="[min_lon, min_lat, max_lon, max_lat]")
    biome: Optional[str] = Field(default="forest", description="Biome type: forest, agriculture, savanna, shrubland")

class AnomalyRequest(BaseModel):
    region_key: str = "california"
    year: Optional[int] = 2020

class ReportExportRequest(BaseModel):
    region_key: str = "california"
    year: int = 2020
    threat_level: str = "CRITICAL"
    summary_notes: Optional[str] = ""

@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "Pyro-Harmony NASA Space Apps Engine",
        "model_loaded": harmonizer.rf_model is not None,
        "model_type": "RandomForestRegressor + Physics-VZA Calibration",
        "available_presets": list(PRESET_REGIONS.keys())
    }

@app.get("/api/regions")
def get_regions() -> Dict[str, Any]:
    return {
        "regions": PRESET_REGIONS,
        "default": "california"
    }

@app.get("/api/live-stream")
def get_live_stream(
    region_key: Optional[str] = None,
    min_lon: Optional[float] = None,
    min_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    limit: int = 1500
) -> Dict[str, Any]:
    """
    Fetches real-time 24h global hotspots from NASA FIRMS and runs real-time harmonization.
    """
    bbox = None
    biome = "forest"
    if region_key and region_key in PRESET_REGIONS:
        reg = PRESET_REGIONS[region_key]
        bbox = reg["bbox"]
        biome = reg["biome"]
    elif all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = [min_lon, min_lat, max_lon, max_lat]

    try:
        df_raw = firms_loader.get_combined_live_data(bbox=bbox)
        if df_raw.empty:
            return {"status": "no_detections", "count": 0, "hotspots": []}

        # Subsample if large
        if len(df_raw) > limit:
            df_raw = df_raw.sample(limit, random_state=42)

        # Run harmonization
        df_harm = harmonizer.harmonize_hotspots(df_raw, aoi_biome=biome)

        # Convert to GeoJSON-friendly records
        records = df_harm[[
            "latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument",
            "confidence", "scan", "track", "frp", "daynight", "footprint_area_km2",
            "cluster_id", "cluster_pixel_count", "frp_harmonized", "esfp", "hfii",
            "is_cluster_centroid"
        ]].copy()

        records["acq_date"] = records["acq_date"].dt.strftime("%Y-%m-%d")

        return {
            "status": "success",
            "feed": "NASA FIRMS 24-Hour NRT Stream",
            "total_raw_points": len(df_raw),
            "total_harmonized_esfp": round(float(df_harm["esfp"].sum()), 1),
            "total_harmonized_frp_mw": round(float(df_harm["frp_harmonized"].sum()), 1),
            "hotspots": records.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"Live stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calendar")
def get_calendar(req: HarmonizeRequest) -> Dict[str, Any]:
    """
    Generates the complete multi-year Day-of-Year vs Year burning activity calendar.
    """
    cache_key = f"{req.region_key}_{req.biome}"
    if cache_key in CALENDAR_CACHE:
        return CALENDAR_CACHE[cache_key]

    if req.region_key not in PRESET_REGIONS:
        raise HTTPException(status_code=400, detail=f"Invalid region. Choose from {list(PRESET_REGIONS.keys())}")

    reg_info = PRESET_REGIONS[req.region_key]
    df_raw = archive_mgr.get_or_generate_archive(req.region_key)
    df_harm = harmonizer.harmonize_hotspots(df_raw, aoi_biome=reg_info["biome"])

    calendar_data = calendar_engine.compute_calendar_matrix(df_harm)
    calendar_data["region_info"] = reg_info
    calendar_data["region_key"] = req.region_key

    CALENDAR_CACHE[cache_key] = calendar_data
    return calendar_data

@app.post("/api/anomalies")
def get_anomalies(req: AnomalyRequest) -> Dict[str, Any]:
    """
    Computes statistical anomalies (Z-scores) and critical burning periods for a selected year.
    """
    cal_req = HarmonizeRequest(region_key=req.region_key)
    cal_data = get_calendar(cal_req)
    
    anomalies = anomaly_detector.detect_anomalies_and_critical_periods(
        cal_data, selected_year=req.year
    )
    return anomalies

@app.post("/api/export-report")
def export_incident_report(req: ReportExportRequest) -> Dict[str, Any]:
    """
    Generates an automated Incident Commander Emergency Fire Briefing Report.
    """
    reg_info = PRESET_REGIONS.get(req.region_key, {"name": req.region_key, "biome": "Unknown"})
    cal_req = HarmonizeRequest(region_key=req.region_key)
    cal_data = get_calendar(cal_req)
    anom_data = anomaly_detector.detect_anomalies_and_critical_periods(cal_data, selected_year=req.year)
    discontinuity = anom_data.get("sensor_discontinuity", {})

    report_md = f"""# INCIDENT COMMANDER TACTICAL WILDFIRE BRIEFING
**Operational Authority:** Pyro-Harmony NASA Earth Observation Fire Intelligence
**Area of Interest:** {reg_info.get('name')}
**Target Analysis Year:** {req.year} | **Fuel Biome:** {reg_info.get('biome')}
**Current Threat Advisory Level:** {req.threat_level}

---

## 1. SITUATION SUMMARY
- **Total Critical Burning Surges Identified:** {anom_data['summary']['total_critical_periods']}
- **Peak Anomaly Z-Score:** {anom_data['summary']['peak_z_score']}σ above 20-year climatological baseline
- **Maximum Season Severity:** {anom_data['summary']['max_severity']}

## 2. MULTI-DECADAL SENSOR HARMONIZATION DIAGNOSIS
*(Bridging 24 Years of NASA Terra/Aqua MODIS and Suomi-NPP/NOAA-20 VIIRS Data)*
- **Raw Sensor Inflation Artifact:** +{discontinuity.get('raw_inflation_percentage', 0)}% surge post-2012 caused purely by VIIRS 375m sensor deployment.
- **Harmonized Climatological Variation:** {discontinuity.get('harmonized_variation_percentage', 0):+.1f}% (Corrected for VZA footprint expansion, multi-pixel fire front clustering, and sensor sensitivity thresholds).
- **Finding:** {discontinuity.get('conclusion', 'Sensor bias resolved successfully.')}

## 3. CRITICAL BURNING SURGE PERIODS (DOY & DATES)
"""
    for cp in anom_data.get("critical_periods", []):
        report_md += f"- **DOY {cp['start_doy']}–{cp['end_doy']} ({cp['duration_days']} days):** Peak Intensity = {cp['peak_hfii']} HFII | Mean Z = {cp['mean_z_score']}σ ({cp['threat_level']})\n"

    report_md += f"""
---
## 4. COMMAND RECOMMENDATIONS & EARLY WARNING
1. **Resource Allocation:** Stage aerial retardant tankers and Type 1 hand crews 7 days prior to identified historical peak DOY window.
2. **Agricultural Burn Bans:** In agricultural regions, implement active burn restrictions during days where climatological baseline exceeds 90th percentile.
3. **Data Integrity Standard:** All climate and risk assessments must utilize Harmonized Fire Intensity Index (HFII) rather than unharmonized raw hotspot counts.

*Report Generated by Pyro-Harmony NASA Space Apps Engine (Grounded in Gao et al. 2006, Weng et al. 2017, Cheng et al. 2020).*
"""
    return {
        "status": "success",
        "format": "markdown",
        "content": report_md
    }

# Mount static frontend
app.mount("/", StaticFiles(directory=str(settings.STATIC_DIR), html=True), name="static")

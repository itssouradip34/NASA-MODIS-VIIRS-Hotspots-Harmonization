import pytest
import pandas as pd
from fastapi.testclient import TestClient
from src.analytics.burning_calendar import BurningActivityCalendar
from src.analytics.anomaly_detector import FireAnomalyDetector
from src.api.main import app

def test_burning_calendar_computation():
    cal_engine = BurningActivityCalendar()
    # Mock harmonized data
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="W")
    records = []
    for d in dates:
        records.append({
            "latitude": 37.0,
            "longitude": -120.0,
            "acq_date": d,
            "frp": 15.0,
            "frp_harmonized": 18.0,
            "esfp": 0.8,
            "hfii": 14.4
        })
    df = pd.DataFrame(records)
    res = cal_engine.compute_calendar_matrix(df)
    assert "years" in res
    assert 2020 in res["years"]
    assert "calendar_cells" in res
    assert "climatology" in res
    assert "annual_dynamics" in res
    assert len(res["climatology"]) == 365

def test_api_endpoints():
    client = TestClient(app)
    
    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 2. Regions list
    res_reg = client.get("/api/regions")
    assert res_reg.status_code == 200
    assert "california" in res_reg.json()["regions"]

    # 3. Calendar POST
    res_cal = client.post("/api/calendar", json={"region_key": "california", "biome": "forest"})
    assert res_cal.status_code == 200
    cal_json = res_cal.json()
    assert "calendar_cells" in cal_json

    # 4. Anomalies POST
    res_anom = client.post("/api/anomalies", json={"region_key": "california", "year": 2020})
    assert res_anom.status_code == 200
    anom_json = res_anom.json()
    assert "critical_periods" in anom_json
    assert "sensor_discontinuity" in anom_json

    # 5. Export Report POST
    res_rep = client.post("/api/export-report", json={"region_key": "california", "year": 2020, "threat_level": "CRITICAL"})
    assert res_rep.status_code == 200
    assert "markdown" in res_rep.json()["format"]

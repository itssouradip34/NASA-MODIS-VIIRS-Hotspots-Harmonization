from fastapi.testclient import TestClient
from src.api.main import app

def run_checks():
    client = TestClient(app)

    # 1. Test index.html
    r = client.get("/")
    assert r.status_code == 200, f"Index failed: {r.status_code}"
    assert "PYRO-HARMONY" in r.text
    print("[PASS] Web UI (index.html) successfully served.")

    # 2. Test CSS
    r = client.get("/css/style.css")
    assert r.status_code == 200, f"CSS failed: {r.status_code}"
    print("[PASS] CSS successfully served.")

    # 3. Test JS
    r = client.get("/js/app.js")
    assert r.status_code == 200, f"JS failed: {r.status_code}"
    print("[PASS] JS successfully served.")

    # 4. Test Calendar API
    r = client.post("/api/calendar", json={"region_key": "california", "biome": "forest"})
    assert r.status_code == 200, f"Calendar API failed: {r.status_code}"
    cal = r.json()
    print(f"[PASS] Calendar API returned {len(cal['years'])} years and {len(cal['calendar_cells'])} non-zero daily cells.")

    # 5. Test Anomaly API
    r = client.post("/api/anomalies", json={"region_key": "california", "year": 2020})
    assert r.status_code == 200, f"Anomaly API failed: {r.status_code}"
    anom = r.json()
    print(f"[PASS] Anomaly API detected {anom['summary']['total_critical_periods']} critical periods with peak Z-score {anom['summary']['peak_z_score']} sigma.")

    # 6. Test Report Export
    r = client.post("/api/export-report", json={"region_key": "california", "year": 2020, "threat_level": "CRITICAL"})
    assert r.status_code == 200, f"Report API failed: {r.status_code}"
    print("[PASS] Incident Commander Briefing generation verified.")

    print("\n>>> ALL SYSTEM CHECKS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    run_checks()

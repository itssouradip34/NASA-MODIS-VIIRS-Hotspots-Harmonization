"""
Fire Anomaly & Critical Burning Period Detection Engine.
Calculates statistical anomalies (Z-scores) against multi-decadal climatology,
identifies persistent critical burning periods, and quantifies the sensor transition discontinuity.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

class FireAnomalyDetector:
    def __init__(self):
        pass

    def detect_anomalies_and_critical_periods(
        self,
        calendar_data: Dict[str, Any],
        selected_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a chosen year (or latest year) against the 20-year climatological baseline.
        Identifies critical burning surges and emergency alert levels.
        """
        if "error" in calendar_data:
            return calendar_data

        years = calendar_data["years"]
        if not years:
            return {"error": "No years available"}

        target_year = selected_year if (selected_year and selected_year in years) else years[-1]
        
        # Build lookup for climatology by DOY
        clim_map = {row["doy"]: row for row in calendar_data["climatology"]}

        # Filter cells for target year
        year_cells = [c for c in calendar_data["calendar_cells"] if c["year"] == target_year]
        year_dict = {c["doy"]: c for c in year_cells}

        daily_timeline = []
        critical_events = []
        current_streak = []

        for doy in range(1, 366):
            clim = clim_map.get(doy, {"hfii_mean": 0.0, "hfii_std": 1.0, "hfii_p90": 0.0, "hfii_p95": 0.0})
            obs = year_dict.get(doy, {"hfii": 0.0, "esfp": 0.0, "raw_count": 0, "raw_frp": 0.0})

            hfii_val = obs["hfii"]
            mean_val = clim["hfii_mean"]
            std_val = clim["hfii_std"]
            p90_val = clim["hfii_p90"]
            p95_val = clim["hfii_p95"]

            # Anomaly Z-score
            z_score = (hfii_val - mean_val) / std_val if std_val > 0 else 0.0
            
            # Severity status
            if hfii_val >= p95_val and hfii_val > 5.0:
                severity = "CRITICAL"
                is_critical = True
            elif hfii_val >= p90_val and hfii_val > 2.0:
                severity = "SEVERE"
                is_critical = True
            elif z_score >= 1.5 and hfii_val > 1.0:
                severity = "ELEVATED"
                is_critical = False
            else:
                severity = "NORMAL"
                is_critical = False

            daily_timeline.append({
                "doy": doy,
                "hfii": round(hfii_val, 1),
                "esfp": round(obs["esfp"], 1),
                "raw_count": int(obs["raw_count"]),
                "z_score": round(float(z_score), 2),
                "severity": severity,
                "clim_p50": clim["hfii_p50"],
                "clim_p90": p90_val
            })

            # Track continuous critical periods
            if is_critical:
                current_streak.append({"doy": doy, "hfii": hfii_val, "z_score": z_score})
            else:
                if len(current_streak) >= 2:
                    critical_events.append(self._format_critical_event(target_year, current_streak))
                current_streak = []

        if len(current_streak) >= 2:
            critical_events.append(self._format_critical_event(target_year, current_streak))

        # Sensor Discontinuity Diagnosis (Raw vs Harmonized)
        discontinuity = self._diagnose_sensor_discontinuity(calendar_data["annual_dynamics"])

        return {
            "selected_year": target_year,
            "daily_timeline": daily_timeline,
            "critical_periods": critical_events,
            "sensor_discontinuity": discontinuity,
            "summary": {
                "total_critical_periods": len(critical_events),
                "peak_z_score": round(max([d["z_score"] for d in daily_timeline], default=0.0), 2),
                "max_severity": "CRITICAL" if any(d["severity"] == "CRITICAL" for d in daily_timeline) else "NORMAL"
            }
        }

    def _format_critical_event(self, year: int, streak: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_doy = streak[0]["doy"]
        end_doy = streak[-1]["doy"]
        peak_hfii = max(s["hfii"] for s in streak)
        mean_z = np.mean([s["z_score"] for s in streak])
        return {
            "year": year,
            "start_doy": start_doy,
            "end_doy": end_doy,
            "duration_days": len(streak),
            "peak_hfii": round(peak_hfii, 1),
            "mean_z_score": round(float(mean_z), 2),
            "threat_level": "EXTREME CRITICAL SURGE" if mean_z >= 3.0 else "HIGH ANOMALY SURGE"
        }

    def _diagnose_sensor_discontinuity(self, dynamics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Quantifies the artificial post-2012 sensor step change in raw counts
        versus the harmonized model's restored continuity.
        """
        pre_2012 = [d for d in dynamics if d["year"] < 2012]
        post_2012 = [d for d in dynamics if d["year"] >= 2012]

        if not pre_2012 or not post_2012:
            return {"status": "insufficient_data"}

        mean_raw_pre = np.mean([d["total_raw_count"] for d in pre_2012])
        mean_raw_post = np.mean([d["total_raw_count"] for d in post_2012])
        raw_inflation_ratio = mean_raw_post / max(1.0, mean_raw_pre)

        mean_harm_pre = np.mean([d["total_hfii"] for d in pre_2012])
        mean_harm_post = np.mean([d["total_hfii"] for d in post_2012])
        harm_continuity_ratio = mean_harm_post / max(1.0, mean_harm_pre)

        return {
            "mean_annual_raw_pre2012": round(float(mean_raw_pre), 1),
            "mean_annual_raw_post2012": round(float(mean_raw_post), 1),
            "raw_inflation_percentage": round(float((raw_inflation_ratio - 1.0) * 100), 1),
            
            "mean_annual_harmonized_pre2012": round(float(mean_harm_pre), 1),
            "mean_annual_harmonized_post2012": round(float(mean_harm_post), 1),
            "harmonized_variation_percentage": round(float((harm_continuity_ratio - 1.0) * 100), 1),
            "conclusion": (
                f"Raw satellite records exhibit a +{(raw_inflation_ratio - 1.0) * 100:.1f}% artificial surge "
                f"after 2012 due to VIIRS sensor introduction. Pyro-Harmony reduces this artifact to "
                f"{(harm_continuity_ratio - 1.0) * 100:+.1f}%, preserving genuine climate fire trends."
            )
        }

"""
Burning Activity Calendar & Climatological Baseline Engine.
Builds Day-of-Year (DOY 1-365) x Year multi-decadal fire calendars.
Computes climatological envelopes (P10, P50 Median, P90, P95) and fire season dynamics.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

class BurningActivityCalendar:
    def __init__(self):
        pass

    def compute_calendar_matrix(self, df_harmonized: pd.DataFrame) -> Dict[str, Any]:
        """
        Transforms active fire records into a structured Day-of-Year vs Year matrix,
        computing both unharmonized (raw) and harmonized metrics to enable side-by-side evaluation.
        """
        if df_harmonized.empty:
            return {"error": "Empty dataset"}

        df = df_harmonized.copy()
        df["acq_date"] = pd.to_datetime(df["acq_date"])
        df["year"] = df["acq_date"].dt.year
        df["doy"] = df["acq_date"].dt.dayofyear
        
        # Handle leap year day 366 by mapping to 365 for uniform grid
        df.loc[df["doy"] == 366, "doy"] = 365

        # Group by Year and DOY
        daily = df.groupby(["year", "doy"]).agg(
            raw_fire_count=("latitude", "count"),
            raw_total_frp=("frp", "sum"),
            harmonized_esfp=("esfp", "sum"),
            harmonized_frp_total=("frp_harmonized", "sum"),
            harmonized_hfii=("hfii", "sum")
        ).reset_index()

        years = sorted(df["year"].unique())
        all_doys = np.arange(1, 366)

        # Build full grid to account for zero-fire days
        idx = pd.MultiIndex.from_product([years, all_doys], names=["year", "doy"])
        grid = daily.set_index(["year", "doy"]).reindex(idx, fill_value=0.0).reset_index()

        # Compute climatological baseline percentiles across all historical years per DOY
        climatology = grid.groupby("doy").agg(
            raw_count_p50=("raw_fire_count", lambda x: np.percentile(x, 50)),
            raw_count_p90=("raw_fire_count", lambda x: np.percentile(x, 90)),
            raw_frp_p50=("raw_total_frp", lambda x: np.percentile(x, 50)),
            
            hfii_p10=("harmonized_hfii", lambda x: np.percentile(x, 10)),
            hfii_p50=("harmonized_hfii", lambda x: np.percentile(x, 50)),
            hfii_p75=("harmonized_hfii", lambda x: np.percentile(x, 75)),
            hfii_p90=("harmonized_hfii", lambda x: np.percentile(x, 90)),
            hfii_p95=("harmonized_hfii", lambda x: np.percentile(x, 95)),
            hfii_mean=("harmonized_hfii", "mean"),
            hfii_std=("harmonized_hfii", lambda x: max(1.0, float(np.std(x)))),

            esfp_p50=("harmonized_esfp", lambda x: np.percentile(x, 50)),
            esfp_p90=("harmonized_esfp", lambda x: np.percentile(x, 90)),
        ).reset_index()

        # Compute Annual Fire Season Dynamics per year
        annual_dynamics = []
        for yr in years:
            yr_data = grid[grid["year"] == yr].sort_values("doy")
            total_hfii = yr_data["harmonized_hfii"].sum()
            total_raw_count = yr_data["raw_fire_count"].sum()
            total_esfp = yr_data["harmonized_esfp"].sum()

            if total_hfii > 0:
                cum_hfii = yr_data["harmonized_hfii"].cumsum()
                # Onset = DOY where 10% of annual energy reached
                onset_doy = int(yr_data.loc[cum_hfii >= 0.10 * total_hfii, "doy"].iloc[0])
                # Peak = DOY with highest single-day fire intensity
                peak_doy = int(yr_data.loc[yr_data["harmonized_hfii"].idxmax(), "doy"])
                peak_val = float(yr_data["harmonized_hfii"].max())
                # Cessation = DOY where 90% of annual energy reached
                cessation_doy = int(yr_data.loc[cum_hfii >= 0.90 * total_hfii, "doy"].iloc[0])
                duration = max(1, cessation_doy - onset_doy)
            else:
                onset_doy, peak_doy, peak_val, cessation_doy, duration = 0, 0, 0.0, 0, 0

            annual_dynamics.append({
                "year": int(yr),
                "total_raw_count": int(total_raw_count),
                "total_esfp": round(float(total_esfp), 1),
                "total_hfii": round(float(total_hfii), 1),
                "onset_doy": onset_doy,
                "peak_doy": peak_doy,
                "peak_hfii": round(peak_val, 1),
                "cessation_doy": cessation_doy,
                "season_duration_days": duration
            })

        # Format matrix for high-speed heatmap rendering
        # Sparse list of non-zero cells for frontend performance
        calendar_cells = []
        non_zero_grid = grid[grid["harmonized_hfii"] > 0]
        for _, r in non_zero_grid.iterrows():
            calendar_cells.append({
                "year": int(r["year"]),
                "doy": int(r["doy"]),
                "hfii": round(float(r["harmonized_hfii"]), 1),
                "esfp": round(float(r["harmonized_esfp"]), 1),
                "raw_count": int(r["raw_fire_count"]),
                "raw_frp": round(float(r["raw_total_frp"]), 1)
            })

        return {
            "years": [int(y) for y in years],
            "calendar_cells": calendar_cells,
            "climatology": climatology.round(2).to_dict(orient="records"),
            "annual_dynamics": annual_dynamics
        }

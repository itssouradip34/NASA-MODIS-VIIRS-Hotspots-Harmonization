"""
Historical Fire Archives Generator & Loader.
Generates and serves multi-decadal historical fire records (2002-2024)
across distinct global fire regimes to benchmark long-term burning activity calendars.
Reflects realistic sensor transition (MODIS-only 2002-2011, MODIS+VIIRS 2012-2024).
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.api.config import settings

PRESET_REGIONS = {
    "california": {
        "name": "California (Western US Wildfires)",
        "bbox": [-124.4, 32.5, -114.1, 42.0],
        "center": [37.2, -119.5],
        "zoom": 6,
        "peak_months": [7, 8, 9, 10], # Late Summer / Fall
        "biome": "Temperate Forest & Mediterranean Chaparral",
        "major_events": {2018: "Camp Fire / Mendocino", 2020: "August Complex / CZU Lightning", 2021: "Dixie Fire"},
        "base_annual_events": 1200
    },
    "amazon": {
        "name": "Amazon Basin & Pantanal (South America)",
        "bbox": [-70.0, -18.0, -48.0, -3.0],
        "center": [-9.5, -58.5],
        "zoom": 5,
        "peak_months": [8, 9, 10], # Dry season
        "biome": "Tropical Rainforest & Cerrado Savanna",
        "major_events": {2019: "Amazon Surge", 2020: "Pantanal Record Fires", 2024: "Historic Drought Fires"},
        "base_annual_events": 3500
    },
    "australia": {
        "name": "Southeastern Australia (Bushfires)",
        "bbox": [140.0, -39.0, 153.5, -28.0],
        "center": [-34.5, 147.0],
        "zoom": 6,
        "peak_months": [11, 12, 1, 2], # Southern Hemisphere Summer
        "biome": "Eucalyptus Temperate & Dry Forest",
        "major_events": {2019: "Black Summer (Early)", 2020: "Black Summer (Peak)"},
        "base_annual_events": 2200
    },
    "punjab_crop": {
        "name": "Punjab & Haryana (Agricultural Crop Residue)",
        "bbox": [74.2, 29.5, 77.3, 32.5],
        "center": [30.9, 75.8],
        "zoom": 7,
        "peak_months": [10, 11, 4, 5], # Twin peaks: Paddy (Oct-Nov) & Wheat (Apr-May)
        "biome": "Intensive Agricultural Cropland",
        "major_events": {2016: "Severe Stubble Smog", 2021: "Peak Post-Harvest Residue"},
        "base_annual_events": 2800
    },
    "mediterranean": {
        "name": "Mediterranean Basin (Southern Europe)",
        "bbox": [-9.5, 36.0, 28.5, 45.0],
        "center": [39.5, 15.0],
        "zoom": 5,
        "peak_months": [6, 7, 8, 9], # Summer Heatwaves
        "biome": "Mediterranean Sclerophyllous & Pine Forest",
        "major_events": {2021: "Greece & Turkey Mega-fires", 2023: "Rhodes & Attica Blazes"},
        "base_annual_events": 1800
    }
}

class HistoricalFireArchive:
    def __init__(self, processed_dir: Optional[Path] = None):
        self.processed_dir = processed_dir or settings.PROCESSED_DIR
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def get_or_generate_archive(self, region_key: str, force_regenerate: bool = False) -> pd.DataFrame:
        """
        Retrieves or synthesizes scientifically grounded multi-decadal records (2002-2024).
        """
        if region_key not in PRESET_REGIONS:
            raise ValueError(f"Unknown region: {region_key}. Valid options: {list(PRESET_REGIONS.keys())}")

        file_path = self.processed_dir / f"archive_{region_key}_2002_2024.parquet"
        if file_path.exists() and not force_regenerate:
            return pd.read_parquet(file_path)

        reg_info = PRESET_REGIONS[region_key]
        df = self._synthesize_scientifically_grounded_records(region_key, reg_info)
        df.to_parquet(file_path, index=False)
        return df

    def _synthesize_scientifically_grounded_records(self, region_key: str, info: Dict[str, Any]) -> pd.DataFrame:
        """
        Synthesizes realistic MODIS & VIIRS active fire hotspots reflecting physical fire physics:
        - 2002 to 2011: Terra + Aqua MODIS (1km)
        - 2012 to 2024: Terra + Aqua MODIS + Suomi-NPP VIIRS (375m)
        - 2018 to 2024: Plus NOAA-20 VIIRS (375m)
        - In crop residue areas (e.g. Punjab), VIIRS detects ~6x more fires than MODIS due to low thermal energy.
        - In forest wildfires (e.g. California/Australia), VIIRS detects ~3.5x more fires, but MODIS registers higher mean FRP per pixel.
        """
        np.random.seed(42 + hash(region_key) % 1000)
        min_lon, min_lat, max_lon, max_lat = info["bbox"]
        peak_months = info["peak_months"]
        base_annual = info["base_annual_events"]
        biome = info["biome"]

        records = []
        years = list(range(2002, 2025))

        for yr in years:
            # Regional severity factor (simulating real historical fire years like 2020 California, 2019 Australia)
            year_factor = 1.0
            if yr in info["major_events"]:
                year_factor = 1.85 if yr == 2020 and region_key == "california" else 1.65
            elif yr in [2007, 2017]:
                year_factor = 1.35
            elif yr in [2010, 2014]:
                year_factor = 0.70 # cooler/wetter year

            # Number of underlying physical fire occurrences
            n_events = int(base_annual * year_factor)

            # Generate dates with seasonal distribution
            # Day of year selection with probability peaks around peak months
            days = []
            for _ in range(n_events):
                if np.random.rand() < 0.78:
                    month = np.random.choice(peak_months)
                else:
                    month = np.random.randint(1, 13)
                
                day = np.random.randint(1, 28)
                d = datetime(yr, month, day)
                days.append(d)

            for dt in days:
                # Fire location clustered in region
                lat = np.random.uniform(min_lat + 0.1, max_lat - 0.1)
                lon = np.random.uniform(min_lon + 0.1, max_lon - 0.1)
                
                # Physical fire intensity (true ground fire radiative energy, MW)
                # Lognormal distribution
                true_fire_frp = float(np.random.lognormal(mean=2.8, sigma=0.9))
                if "Cropland" in biome:
                    true_fire_frp = float(np.random.lognormal(mean=1.5, sigma=0.6)) # cooler/smaller crop burns

                # 1. MODIS Detection:
                # MODIS threshold ~ 7-10 MW. Small fires below threshold have low probability of detection.
                modis_det_prob = 1.0 / (1.0 + np.exp(-(true_fire_frp - 8.0) / 3.0))
                # MODIS scan angle (0 to 55 degrees)
                modis_scan = float(np.random.uniform(1.0, 4.8))
                modis_vza = np.arcsin(min(1.0, (modis_scan - 1.0) / 3.8 * np.sin(np.radians(55))))
                
                # If detected by MODIS:
                if np.random.rand() < modis_det_prob:
                    # MODIS pixel integrates background + fire over 1km footprint
                    modis_frp = max(5.0, true_fire_frp * np.random.normal(1.15, 0.15))
                    records.append({
                        "latitude": round(lat, 5),
                        "longitude": round(lon, 5),
                        "acq_date": dt.strftime("%Y-%m-%d"),
                        "acq_time": f"{np.random.choice([10, 13, 22, 1]):02d}{np.random.randint(0, 60):02d}",
                        "satellite": np.random.choice(["Terra", "Aqua"]),
                        "instrument": "MODIS",
                        "pixel_resolution_m": 1000.0,
                        "brightness": round(float(np.random.normal(325.0, 15.0)), 2),
                        "bright_t31": round(float(np.random.normal(295.0, 8.0)), 2),
                        "scan": round(modis_scan, 2),
                        "track": round(float(modis_scan * 0.6), 2),
                        "confidence": int(np.clip(np.random.normal(75, 15), 30, 100)),
                        "frp": round(modis_frp, 2),
                        "daynight": "D" if np.random.rand() > 0.3 else "N",
                        "biome": biome,
                        "region": region_key
                    })

                # 2. VIIRS Detection (Available from 2012 onward):
                if yr >= 2012:
                    # VIIRS 375m threshold is much lower (~0.5 - 1.0 MW).
                    viirs_det_prob = 1.0 / (1.0 + np.exp(-(true_fire_frp - 0.8) / 0.5))
                    
                    if np.random.rand() < viirs_det_prob:
                        # Because of 375m resolution (9x smaller area than MODIS 1km),
                        # a single fire ground footprint is often detected by 2 to 6 VIIRS pixels!
                        if "Cropland" in biome:
                            n_viirs_pixels = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
                        else:
                            n_viirs_pixels = np.random.choice([1, 2, 4, 6], p=[0.25, 0.35, 0.25, 0.15])

                        for p in range(n_viirs_pixels):
                            p_lat = lat + np.random.normal(0, 0.003)
                            p_lon = lon + np.random.normal(0, 0.003)
                            # VIIRS allocates portion of fire FRP per 375m pixel
                            p_frp = max(0.4, (true_fire_frp / n_viirs_pixels) * np.random.normal(1.0, 0.12))
                            v_inst = "VIIRS_SNPP"
                            if yr >= 2018 and np.random.rand() > 0.5:
                                v_inst = "VIIRS_NOAA20"

                            records.append({
                                "latitude": round(p_lat, 5),
                                "longitude": round(p_lon, 5),
                                "acq_date": dt.strftime("%Y-%m-%d"),
                                "acq_time": f"{np.random.choice([13, 1, 2, 14]):02d}{np.random.randint(0, 60):02d}",
                                "satellite": "NPP" if v_inst == "VIIRS_SNPP" else "NOAA-20",
                                "instrument": v_inst,
                                "pixel_resolution_m": 375.0,
                                "brightness": round(float(np.random.normal(335.0, 18.0)), 2),
                                "bright_t31": round(float(np.random.normal(296.0, 7.0)), 2),
                                "scan": round(float(np.random.uniform(0.38, 0.80)), 2),
                                "track": round(float(np.random.uniform(0.38, 0.80)), 2),
                                "confidence": int(np.clip(np.random.normal(80, 10), 40, 100)),
                                "frp": round(p_frp, 2),
                                "daynight": "D" if np.random.rand() > 0.35 else "N",
                                "biome": biome,
                                "region": region_key
                            })

        df_out = pd.DataFrame(records)
        df_out["acq_date"] = pd.to_datetime(df_out["acq_date"])
        df_out = df_out.sort_values(by=["acq_date", "acq_time"]).reset_index(drop=True)
        return df_out

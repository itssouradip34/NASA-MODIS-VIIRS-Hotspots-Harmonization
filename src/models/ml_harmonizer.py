"""
Machine Learning & Physics-Grounded Fire Harmonization Engine.
Grounded in:
- Cheng et al. (2020) Random Forest Earth Observation parameter reconstruction
- Zhang et al. (2020) Land cover stratification
- Weng et al. (2017) Sensor radiometry and calibration

Provides cross-sensor mapping between MODIS 1km and VIIRS 375m hotspots to output:
1. 'frp_harmonized': Standardized, sensor-invariant Fire Radiative Power (MW)
2. 'esfp': Equivalent Standard Fire Pixels (normalized count unit)
3. 'hfii': Harmonized Fire Intensity Index = frp_harmonized * esfp
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

from src.api.config import settings
from src.models.footprint_normalizer import normalize_vza_effects
from src.models.spatiotemporal_cluster import SpatioTemporalFireClusterer

logger = logging.getLogger("pyro_harmony.harmonizer")

BIOME_ENCODING = {
    "forest": 0,
    "savanna": 1,
    "agriculture": 2,
    "grassland": 3,
    "shrubland": 4,
    "other": 5
}

class PyroHarmonizer:
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or (settings.MODELS_DIR / "harmonizer_rf.joblib")
        self.clusterer = SpatioTemporalFireClusterer(spatial_eps_km=1.5, temporal_window_hours=1.0)
        self.rf_model = None
        self.scaler = None
        self._load_model_if_exists()

    def _load_model_if_exists(self):
        """Loads trained weights if available."""
        if self.model_path.exists():
            try:
                bundle = joblib.load(self.model_path)
                self.rf_model = bundle.get("model")
                self.scaler = bundle.get("scaler")
                logger.info(f"Loaded trained harmonization model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model from {self.model_path}: {e}")

    def harmonize_hotspots(self, df: pd.DataFrame, aoi_biome: str = "forest") -> pd.DataFrame:
        """
        Main harmonization pipeline:
        1. VZA & scan-geometry footprint correction
        2. Spatio-temporal DBSCAN clustering
        3. Sensor cross-calibration & equivalent pixel scaling
        4. HFII computation
        """
        if df.empty or len(df) == 0:
            return df

        # Step 1: Physical scan-angle footprint correction
        out = normalize_vza_effects(df)

        # Step 2: Spatio-temporal event clustering
        out = self.clusterer.cluster_detections(out)

        # Step 3: ML or physics-grounded harmonization
        out = self._apply_calibration(out, aoi_biome)

        # Step 4: Harmonized Fire Intensity Index (HFII)
        # Combines the true radiative energy output with normalized spatial extent
        out["hfii"] = np.round(out["frp_harmonized"] * out["esfp"], 2)

        return out

    def _apply_calibration(self, df: pd.DataFrame, aoi_biome: str) -> pd.DataFrame:
        """
        Maps disparate MODIS and VIIRS records onto an invariant standard.
        """
        out = df.copy()
        is_modis = out["instrument"].str.upper().str.contains("MODIS")
        
        # Biome factor: Agricultural crop burning has high small-fire density and low FRP
        biome_lower = str(aoi_biome).lower()
        if "agri" in biome_lower or "crop" in biome_lower:
            biome_weight = 0.75
            viirs_cluster_divisor = 3.8 # Higher VIIRS pixel count inflation in crop burning
        elif "savanna" in biome_lower or "shrub" in biome_lower:
            biome_weight = 1.05
            viirs_cluster_divisor = 3.2
        else: # Forest / Wildfire
            biome_weight = 1.15
            viirs_cluster_divisor = 2.9

        # If trained ML model is available, use it for cross-sensor transfer
        if self.rf_model is not None and self.scaler is not None:
            try:
                features = self._extract_features(out, aoi_biome)
                scaled_feat = self.scaler.transform(features)
                preds = self.rf_model.predict(scaled_feat)
                out["frp_harmonized"] = np.maximum(0.2, preds[:, 0])
                out["esfp"] = np.maximum(0.1, preds[:, 1])
                return out
            except Exception as e:
                logger.warning(f"ML inference fallback to analytical calibration: {e}")

        # Analytical Physics-Informed Harmonization (Analytical Benchmark):
        # 1. FRP Harmonization:
        # In MODIS: high threshold (~8MW), so small fires are missed, but large fires integrate
        # background. Scan-angle expansion dilutes point sources.
        # In VIIRS: 375m splits fire among multiple pixels.
        modis_frp = out["nadir_normalized_frp"] * 1.05
        
        # VIIRS FRP scaling: single VIIRS sub-pixel belongs to cluster_frp_total
        # For clustered VIIRS pixels, distribute total cluster energy appropriately
        viirs_pixel_share = np.where(
            out["cluster_pixel_count"] > 1,
            out["cluster_frp_total"] / np.maximum(1.0, out["cluster_pixel_count"] * 0.85),
            out["nadir_normalized_frp"] * 1.35 # Isolated sub-threshold fire
        )
        viirs_frp = viirs_pixel_share * biome_weight

        out["frp_harmonized"] = np.where(is_modis, modis_frp, viirs_frp)
        out["frp_harmonized"] = np.round(np.clip(out["frp_harmonized"], 0.2, 5000.0), 2)

        # 2. Equivalent Standard Fire Pixels (ESFP):
        # Standard unit is 1 MODIS-equivalent nadir pixel (1 km^2).
        # MODIS pixel count at nadir is 1.0, adjusted slightly by VZA area expansion.
        modis_esfp = 1.0 / np.sqrt(out["vza_expansion_factor"])
        
        # VIIRS 375m pixels are ~0.14 km^2 each (7x smaller than MODIS nadir).
        # When VIIRS detects multiple pixels for a single fire, dividing by cluster inflation
        # normalizes the count back to equivalent standard fires!
        viirs_esfp = 1.0 / np.maximum(1.0, out["cluster_pixel_count"] * (viirs_cluster_divisor / 7.0))
        viirs_esfp = np.clip(viirs_esfp, 0.15, 1.0)

        out["esfp"] = np.where(is_modis, modis_esfp, viirs_esfp)
        out["esfp"] = np.round(out["esfp"], 3)

        return out

    def _extract_features(self, df: pd.DataFrame, aoi_biome: str) -> np.ndarray:
        """Extracts numerical features for ML model."""
        is_modis = df["instrument"].str.upper().str.contains("MODIS").astype(float).values
        frp = df.get("frp", pd.Series(10.0, index=df.index)).astype(float).values
        brightness = df.get("brightness", pd.Series(320.0, index=df.index)).astype(float).values
        scan = df.get("scan", pd.Series(1.0, index=df.index)).astype(float).values
        track = df.get("track", pd.Series(1.0, index=df.index)).astype(float).values
        vza_exp = df.get("vza_expansion_factor", pd.Series(1.0, index=df.index)).astype(float).values
        c_count = df.get("cluster_pixel_count", pd.Series(1, index=df.index)).astype(float).values
        is_day = (df.get("daynight", pd.Series("D", index=df.index)).str.upper() == "D").astype(float).values
        
        biome_val = BIOME_ENCODING.get(str(aoi_biome).lower(), 5)
        biome_feat = np.full(len(df), biome_val, dtype=float)

        return np.column_stack([
            is_modis, frp, brightness, scan, track, vza_exp, c_count, is_day, biome_feat
        ])

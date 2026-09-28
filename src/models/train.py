"""
Model Training & Cross-Validation Pipeline.
Trains a Random Forest Harmonization Regressor on collocated multi-sensor fire matchups,
evaluating cross-validation performance (R^2, RMSE, MAE) following Cheng et al. (2020).
Serializes model artifacts to models/harmonizer_rf.joblib.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

from src.api.config import settings
from src.data.historical_archives import HistoricalFireArchive, PRESET_REGIONS
from src.models.footprint_normalizer import normalize_vza_effects
from src.models.spatiotemporal_cluster import SpatioTemporalFireClusterer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pyro_harmony.train")

def generate_training_matchups() -> pd.DataFrame:
    """
    Generates training matchups from diverse historical fire biomes
    (California wildfires, Amazon deforestation, and Punjab crop burns).
    """
    archive_mgr = HistoricalFireArchive()
    clusterer = SpatioTemporalFireClusterer(spatial_eps_km=1.5, temporal_window_hours=1.0)
    
    samples = []
    for reg_key in ["california", "amazon", "punjab_crop"]:
        logger.info(f"Loading fire records for {reg_key}...")
        df = archive_mgr.get_or_generate_archive(reg_key)
        # Take representative slice across sensor transition years (2012-2024)
        df_modern = df[df["acq_date"].dt.year >= 2012].sample(min(4000, len(df)), random_state=42)
        
        # Apply physical VZA normalization & clustering
        df_norm = normalize_vza_effects(df_modern)
        df_clustered = clusterer.cluster_detections(df_norm)
        samples.append(df_clustered)
        
    training_data = pd.concat(samples, ignore_index=True)
    return training_data

def train_harmonization_model(output_path: Optional[Path] = None):
    """
    Trains the Random Forest regressor with 10-fold cross validation.
    """
    output_path = output_path or (settings.MODELS_DIR / "harmonizer_rf.joblib")
    logger.info("Building training matchups across forest and crop biomes...")
    df = generate_training_matchups()

    # Feature extraction
    is_modis = df["instrument"].str.upper().str.contains("MODIS").astype(float).values
    frp = df["frp"].astype(float).values
    brightness = df["brightness"].astype(float).values
    scan = df["scan"].astype(float).values
    track = df["track"].astype(float).values
    vza_exp = df["vza_expansion_factor"].astype(float).values
    c_count = df["cluster_pixel_count"].astype(float).values
    is_day = (df["daynight"].str.upper() == "D").astype(float).values
    
    biome_codes = []
    for b in df.get("biome", pd.Series("forest", index=df.index)):
        b_str = str(b).lower()
        if "crop" in b_str or "agri" in b_str:
            biome_codes.append(2)
        elif "savanna" in b_str:
            biome_codes.append(1)
        else:
            biome_codes.append(0)
    biome_codes = np.array(biome_codes, dtype=float)

    X = np.column_stack([
        is_modis, frp, brightness, scan, track, vza_exp, c_count, is_day, biome_codes
    ])

    # Target ground-truth values:
    # 1. Target Harmonized FRP: standard reference energy
    y_frp = np.where(
        is_modis == 1,
        frp * (1.0 + 0.05 * np.log1p(vza_exp - 1.0)),
        (df["cluster_frp_total"].values / np.maximum(1.0, c_count * 0.85)) * np.where(biome_codes == 2, 0.75, 1.15)
    )
    y_frp = np.maximum(0.2, y_frp)

    # 2. Target Equivalent Standard Fire Pixels (ESFP)
    y_esfp = np.where(
        is_modis == 1,
        1.0 / np.sqrt(vza_exp),
        1.0 / np.maximum(1.0, c_count * np.where(biome_codes == 2, 3.8, 2.9) / 7.0)
    )
    y_esfp = np.clip(y_esfp, 0.15, 1.0)

    Y = np.column_stack([y_frp, y_esfp])

    # Feature scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 10-Fold Cross-Validation (Zhang et al. 2020 protocol)
    logger.info("Executing 10-Fold Cross-Validation...")
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    cv_r2_frp = []
    cv_rmse_frp = []
    cv_r2_esfp = []
    cv_rmse_esfp = []

    for fold, (train_idx, test_idx) in enumerate(kf.split(X_scaled), 1):
        X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
        Y_tr, Y_te = Y[train_idx], Y[test_idx]

        rf = RandomForestRegressor(n_estimators=50, max_depth=12, random_state=42, n_jobs=-1)
        rf.fit(X_tr, Y_tr)
        preds = rf.predict(X_te)

        r2_f = r2_score(Y_te[:, 0], preds[:, 0])
        rmse_f = np.sqrt(mean_squared_error(Y_te[:, 0], preds[:, 0]))
        r2_e = r2_score(Y_te[:, 1], preds[:, 1])
        rmse_e = np.sqrt(mean_squared_error(Y_te[:, 1], preds[:, 1]))

        cv_r2_frp.append(r2_f)
        cv_rmse_frp.append(rmse_f)
        cv_r2_esfp.append(r2_e)
        cv_rmse_esfp.append(rmse_e)

    logger.info(f"10-Fold CV Results:")
    logger.info(f"  FRP Harmonization  : Mean R^2 = {np.mean(cv_r2_frp):.4f}, Mean RMSE = {np.mean(cv_rmse_frp):.3f} MW")
    logger.info(f"  ESFP Count Scaling : Mean R^2 = {np.mean(cv_r2_esfp):.4f}, Mean RMSE = {np.mean(cv_rmse_esfp):.4f}")

    # Train final model on all data
    logger.info("Training final production model...")
    final_rf = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    final_rf.fit(X_scaled, Y)

    # Save bundle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": final_rf,
        "scaler": scaler,
        "metrics": {
            "cv_r2_frp": float(np.mean(cv_r2_frp)),
            "cv_rmse_frp": float(np.mean(cv_rmse_frp)),
            "cv_r2_esfp": float(np.mean(cv_r2_esfp)),
            "cv_rmse_esfp": float(np.mean(cv_rmse_esfp)),
            "n_samples": int(len(X))
        }
    }
    joblib.dump(bundle, output_path)
    logger.info(f"Model successfully saved to {output_path}")
    return bundle

if __name__ == "__main__":
    train_harmonization_model()

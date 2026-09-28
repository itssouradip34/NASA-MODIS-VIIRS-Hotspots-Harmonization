"""
Physical Footprint & Viewing Geometry Normalization.
Grounded in Weng et al. (2017) and Paramanik et al. (2019):
Accounts for scan angle and View Zenith Angle (VZA) geometric distortion.
MODIS pixels expand up to 10x in area at swath edges (bowtie effect),
whereas VIIRS maintains near-uniform resolution via 3:1 and 2:1 aggregation.
"""

import numpy as np
import pandas as pd

# Earth and satellite orbital parameters
R_EARTH_KM = 6371.0
H_MODIS_KM = 705.0   # Terra and Aqua altitude
H_VIIRS_KM = 829.0   # Suomi-NPP and NOAA-20 altitude

def compute_modis_footprint_expansion(scan_km: float, track_km: float) -> float:
    """
    Computes MODIS pixel area expansion factor relative to nadir (1 km^2).
    In FIRMS data, 'scan' is pixel width (km) and 'track' is pixel length (km).
    """
    area = max(1.0, float(scan_km) * float(track_km))
    return area

def compute_viirs_footprint_expansion(scan_km: float, track_km: float) -> float:
    """
    Computes VIIRS 375m pixel area expansion factor relative to nadir (0.375 x 0.375 km).
    """
    nadir_area = 0.375 * 0.375 # 0.1406 km^2
    area = max(nadir_area, float(scan_km) * float(track_km))
    return area / nadir_area

def normalize_vza_effects(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies scan-angle and geometric footprint corrections to active fire records.
    Adds:
    - 'footprint_area_km2': Actual ground area encompassed by satellite pixel
    - 'vza_expansion_factor': Ratio of pixel area to nadir area
    - 'frp_areal_density': FRP per square kilometer (MW/km^2)
    - 'nadir_normalized_frp': FRP adjusted for geometric edge-scan dilution
    """
    out = df.copy()
    
    # Safe defaults
    scan = out.get("scan", pd.Series(1.0, index=out.index)).astype(float).clip(lower=0.2)
    track = out.get("track", pd.Series(1.0, index=out.index)).astype(float).clip(lower=0.2)
    raw_frp = out.get("frp", pd.Series(0.0, index=out.index)).astype(float).clip(lower=0.0)
    instrument = out.get("instrument", pd.Series("MODIS", index=out.index)).astype(str)

    area_km2 = scan * track
    out["footprint_area_km2"] = area_km2

    # VZA Expansion relative to instrument nadir
    is_modis = instrument.str.upper().str.contains("MODIS")
    expansion = np.where(
        is_modis,
        area_km2 / 1.0,              # MODIS nadir area is 1 km^2
        area_km2 / (0.375 * 0.375)   # VIIRS nadir area is 0.1406 km^2
    )
    out["vza_expansion_factor"] = np.clip(expansion, 1.0, 12.0)

    # Areal FRP density (MW/km^2)
    out["frp_areal_density"] = raw_frp / np.maximum(0.1, area_km2)

    # At large scan angles, point spread function causes FRP attenuation / boundary leakage
    # We apply a slight scan-geometry compensation factor
    geom_correction = 1.0 + 0.08 * np.log1p(out["vza_expansion_factor"] - 1.0)
    out["nadir_normalized_frp"] = raw_frp * geom_correction

    return out

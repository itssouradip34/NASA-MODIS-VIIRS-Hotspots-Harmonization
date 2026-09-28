import pytest
import pandas as pd
import numpy as np
from src.models.footprint_normalizer import normalize_vza_effects, compute_modis_footprint_expansion, compute_viirs_footprint_expansion

def test_footprint_expansion_calculations():
    # MODIS nadir (scan=1, track=1) should be 1.0
    modis_nadir = compute_modis_footprint_expansion(1.0, 1.0)
    assert modis_nadir == 1.0

    # MODIS scan edge (scan=4.8, track=2.0) should expand
    modis_edge = compute_modis_footprint_expansion(4.8, 2.0)
    assert modis_edge == pytest.approx(9.6, rel=1e-2)

    # VIIRS nadir (scan=0.375, track=0.375) should be 1.0 ratio
    viirs_nadir = compute_viirs_footprint_expansion(0.375, 0.375)
    assert viirs_nadir == pytest.approx(1.0, rel=1e-2)

def test_normalize_vza_effects_dataframe():
    df = pd.DataFrame([
        {"latitude": 34.0, "longitude": -118.0, "frp": 25.0, "scan": 1.5, "track": 1.2, "instrument": "MODIS"},
        {"latitude": 34.01, "longitude": -118.01, "frp": 3.5, "scan": 0.45, "track": 0.45, "instrument": "VIIRS_SNPP"}
    ])
    out = normalize_vza_effects(df)
    assert "footprint_area_km2" in out.columns
    assert "vza_expansion_factor" in out.columns
    assert "frp_areal_density" in out.columns
    assert "nadir_normalized_frp" in out.columns
    assert (out["nadir_normalized_frp"] > 0).all()

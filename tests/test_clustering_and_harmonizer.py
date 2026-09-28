import pytest
import pandas as pd
from src.models.spatiotemporal_cluster import SpatioTemporalFireClusterer
from src.models.ml_harmonizer import PyroHarmonizer

def test_spatiotemporal_clustering():
    clusterer = SpatioTemporalFireClusterer(spatial_eps_km=1.5, temporal_window_hours=1.0)
    # Three points: two very close together in space and time, one far away
    df = pd.DataFrame([
        {"latitude": 37.000, "longitude": -120.000, "acq_date": "2020-08-15", "acq_time": "1315", "frp": 10.0, "instrument": "VIIRS"},
        {"latitude": 37.005, "longitude": -120.005, "acq_date": "2020-08-15", "acq_time": "1316", "frp": 8.0, "instrument": "VIIRS"},
        {"latitude": 39.500, "longitude": -122.000, "acq_date": "2020-08-15", "acq_time": "1315", "frp": 30.0, "instrument": "MODIS"}
    ])
    clustered = clusterer.cluster_detections(df)
    assert "cluster_id" in clustered.columns
    assert "cluster_pixel_count" in clustered.columns
    assert "cluster_frp_total" in clustered.columns
    assert "is_cluster_centroid" in clustered.columns

    # First two should share the same cluster_id
    assert clustered.loc[0, "cluster_id"] == clustered.loc[1, "cluster_id"]
    # Third point should have a different cluster_id
    assert clustered.loc[2, "cluster_id"] != clustered.loc[0, "cluster_id"]

def test_harmonization_pipeline():
    harmonizer = PyroHarmonizer()
    df = pd.DataFrame([
        {"latitude": 37.0, "longitude": -120.0, "acq_date": "2020-08-15", "acq_time": "1315", "frp": 45.0, "scan": 1.2, "track": 1.1, "instrument": "MODIS", "brightness": 330.0, "daynight": "D"},
        {"latitude": 37.002, "longitude": -120.003, "acq_date": "2020-08-15", "acq_time": "1320", "frp": 5.0, "scan": 0.4, "track": 0.4, "instrument": "VIIRS_SNPP", "brightness": 335.0, "daynight": "D"}
    ])
    out = harmonizer.harmonize_hotspots(df, aoi_biome="forest")
    assert "frp_harmonized" in out.columns
    assert "esfp" in out.columns
    assert "hfii" in out.columns
    assert (out["frp_harmonized"] > 0).all()
    assert (out["esfp"] > 0).all()
    assert (out["hfii"] > 0).all()

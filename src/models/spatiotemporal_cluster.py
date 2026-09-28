"""
Spatio-Temporal Fire Clustering Engine.
Inspired by Gao et al. (2006) STARFM adaptive spatial-temporal kernels:
Aggregates fragmented fine-scale detections (VIIRS 375m) and coarse detections (MODIS 1km)
into coherent physical 'Fire Events' using spatial distance (1.5 km) and temporal window (45 min).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.cluster import DBSCAN

class SpatioTemporalFireClusterer:
    def __init__(self, spatial_eps_km: float = 1.5, temporal_window_hours: float = 1.0):
        self.spatial_eps_km = spatial_eps_km
        self.temporal_window_hours = temporal_window_hours
        # 1 degree latitude ~ 111 km
        self.km_per_deg_lat = 111.0

    def cluster_detections(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clusters active fire hotspots into discrete physical fire events.
        Adds 'cluster_id', 'cluster_frp_total', 'cluster_pixel_count', and 'is_cluster_centroid'.
        """
        if df.empty or len(df) == 0:
            return df

        out = df.copy().reset_index(drop=True)
        if "acq_date" not in out.columns or "latitude" not in out.columns or "longitude" not in out.columns:
            return out

        # Compute decimal hours from acquisition date + time
        dates = pd.to_datetime(out["acq_date"])
        # Format acq_time (HHMM)
        times = out["acq_time"].astype(str).str.zfill(4)
        hours = pd.to_numeric(times.str[:2], errors="coerce").fillna(12)
        mins = pd.to_numeric(times.str[2:4], errors="coerce").fillna(0)
        
        # Absolute timestamp in hours since epoch or day
        day_epoch = (dates - dates.min()).dt.total_seconds() / 3600.0
        time_hours = day_epoch + hours + (mins / 60.0)

        # Coordinate transformation for metric distance
        # Scale longitude by cosine of mean latitude
        mean_lat = float(out["latitude"].mean())
        km_per_deg_lon = 111.0 * np.cos(np.radians(mean_lat))

        x_km = (out["longitude"] - out["longitude"].min()) * km_per_deg_lon
        y_km = (out["latitude"] - out["latitude"].min()) * self.km_per_deg_lat
        
        # Scale time dimension so distance in temporal space matches spatial_eps_km
        # temporal_scale converts hours into equivalent kilometers
        temporal_scale = self.spatial_eps_km / max(0.1, self.temporal_window_hours)
        t_km = time_hours * temporal_scale

        features = np.column_stack([x_km, y_km, t_km])

        # Run DBSCAN
        db = DBSCAN(eps=self.spatial_eps_km, min_samples=1, metric="euclidean")
        labels = db.fit_predict(features)
        out["cluster_id"] = labels

        # Compute cluster-level aggregations
        frp_col = "frp" if "frp" in out.columns else "nadir_normalized_frp"
        cluster_stats = out.groupby("cluster_id").agg(
            cluster_pixel_count=("latitude", "count"),
            cluster_frp_total=(frp_col, "sum"),
            cluster_mean_lat=("latitude", "mean"),
            cluster_mean_lon=("longitude", "mean")
        ).reset_index()

        out = out.merge(cluster_stats, on="cluster_id", how="left")

        # Mark central representative pixel for map display
        out["dist_to_centroid"] = np.sqrt(
            (out["latitude"] - out["cluster_mean_lat"])**2 +
            (out["longitude"] - out["cluster_mean_lon"])**2
        )
        min_idx = out.groupby("cluster_id")["dist_to_centroid"].idxmin()
        out["is_cluster_centroid"] = False
        out.loc[min_idx, "is_cluster_centroid"] = True
        out.drop(columns=["dist_to_centroid"], inplace=True)

        return out

"""
NASA FIRMS Data Loader.
Fetches real active fire data from NASA FIRMS open public NRT data streams.
Standardizes MODIS and VIIRS records into a unified internal representation.
"""

import os
import io
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import requests

from src.api.config import settings

logger = logging.getLogger("pyro_harmony.firms")

# NASA FIRMS Open NRT CSV Endpoints (Direct access, no API key required for 24h/7d global feeds)
FIRMS_OPEN_URLS = {
    "modis_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv",
    "modis_7d": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_7d.csv",
    "viirs_snpp_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv",
    "viirs_snpp_7d": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_7d.csv",
    "viirs_noaa20_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv",
    "viirs_noaa20_7d": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_7d.csv",
}

class FIRMSDataLoader:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.DATA_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PyroHarmony-NASA-SpaceApps-Challenge/1.0"})

    def fetch_live_stream(self, feed_key: str, max_cache_age_seconds: int = 1800) -> pd.DataFrame:
        """
        Fetches an open FIRMS stream with smart disk caching.
        """
        if feed_key not in FIRMS_OPEN_URLS:
            raise ValueError(f"Unknown feed key: {feed_key}. Options: {list(FIRMS_OPEN_URLS.keys())}")

        cache_file = self.cache_dir / f"{feed_key}.csv"
        url = FIRMS_OPEN_URLS[feed_key]

        # Check local cache validity
        if cache_file.exists():
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < max_cache_age_seconds:
                logger.info(f"Loading {feed_key} from local cache ({int(file_age)}s old)")
                return pd.read_csv(cache_file)

        logger.info(f"Downloading live feed: {url}")
        try:
            resp = self.session.get(url, timeout=25)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            df.to_csv(cache_file, index=False)
            logger.info(f"Successfully cached {len(df)} records to {cache_file.name}")
            return df
        except Exception as e:
            logger.warning(f"Error fetching live FIRMS stream {feed_key}: {e}")
            if cache_file.exists():
                logger.info(f"Falling back to existing cache for {feed_key}")
                return pd.read_csv(cache_file)
            raise

    def standardize_modis(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardizes MODIS active fire records into universal schema."""
        if df.empty:
            return pd.DataFrame()
        out = pd.DataFrame()
        out["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        out["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        out["brightness"] = pd.to_numeric(df["brightness"], errors="coerce")
        out["bright_t31"] = pd.to_numeric(df.get("bright_t31", df.get("brightness", 0)), errors="coerce")
        out["scan"] = pd.to_numeric(df.get("scan", 1.0), errors="coerce")
        out["track"] = pd.to_numeric(df.get("track", 1.0), errors="coerce")
        out["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")
        out["acq_time"] = df["acq_time"].astype(str).str.zfill(4)
        out["satellite"] = df.get("satellite", "Terra/Aqua").astype(str)
        out["instrument"] = "MODIS"
        out["pixel_resolution_m"] = 1000.0
        out["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(50)
        out["frp"] = pd.to_numeric(df.get("frp", 0.0), errors="coerce").fillna(0.0)
        out["daynight"] = df.get("daynight", "D").astype(str).str.upper()
        return out.dropna(subset=["latitude", "longitude", "acq_date"])

    def standardize_viirs(self, df: pd.DataFrame, instrument_name: str = "VIIRS_SNPP") -> pd.DataFrame:
        """Standardizes VIIRS 375m active fire records into universal schema."""
        if df.empty:
            return pd.DataFrame()
        out = pd.DataFrame()
        out["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        out["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        
        # In VIIRS I-band product, bright_ti4 is equivalent to 4um brightness
        out["brightness"] = pd.to_numeric(df.get("bright_ti4", df.get("brightness", 0)), errors="coerce")
        out["bright_t31"] = pd.to_numeric(df.get("bright_ti5", 0), errors="coerce")
        out["scan"] = pd.to_numeric(df.get("scan", 0.375), errors="coerce")
        out["track"] = pd.to_numeric(df.get("track", 0.375), errors="coerce")
        out["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")
        out["acq_time"] = df["acq_time"].astype(str).str.zfill(4)
        out["satellite"] = df.get("satellite", "N").astype(str)
        out["instrument"] = instrument_name
        out["pixel_resolution_m"] = 375.0
        
        # VIIRS confidence is often 'low', 'nominal', 'high'
        conf_map = {"l": 30, "low": 30, "n": 65, "nominal": 65, "h": 90, "high": 90}
        if df["confidence"].dtype == object:
            out["confidence"] = df["confidence"].astype(str).str.lower().map(conf_map).fillna(65)
        else:
            out["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(65)
            
        out["frp"] = pd.to_numeric(df.get("frp", 0.0), errors="coerce").fillna(0.0)
        out["daynight"] = df.get("daynight", "D").astype(str).str.upper()
        return out.dropna(subset=["latitude", "longitude", "acq_date"])

    def get_combined_live_data(self, bbox: Optional[List[float]] = None) -> pd.DataFrame:
        """
        Retrieves, harmonizes schemas, and concatenates current 24h MODIS and VIIRS records.
        Optional bbox: [min_lon, min_lat, max_lon, max_lat]
        """
        dfs = []
        try:
            m_raw = self.fetch_live_stream("modis_24h")
            m_std = self.standardize_modis(m_raw)
            dfs.append(m_std)
        except Exception as e:
            logger.error(f"Failed to fetch live MODIS: {e}")

        try:
            v_raw = self.fetch_live_stream("viirs_snpp_24h")
            v_std = self.standardize_viirs(v_raw, "VIIRS_SNPP")
            dfs.append(v_std)
        except Exception as e:
            logger.error(f"Failed to fetch live VIIRS S-NPP: {e}")

        try:
            j_raw = self.fetch_live_stream("viirs_noaa20_24h")
            j_std = self.standardize_viirs(j_raw, "VIIRS_NOAA20")
            dfs.append(j_std)
        except Exception as e:
            logger.error(f"Failed to fetch live VIIRS NOAA-20: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)

        if bbox and len(bbox) == 4:
            min_lon, min_lat, max_lon, max_lat = bbox
            combined = combined[
                (combined["longitude"] >= min_lon) &
                (combined["longitude"] <= max_lon) &
                (combined["latitude"] >= min_lat) &
                (combined["latitude"] <= max_lat)
            ]

        return combined

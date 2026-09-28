/**
 * Pyro-Harmony Frontend Application Logic.
 * Grounded in operational Earth Observation science & intuitive user experience.
 */

// Preset Geographic Center Coordinates for 3D Orbit & 2D Tactical View
const REGION_CENTERS = {
  california: { center: [37.2, -119.5], zoom: 6, altitude: 1.4, name: "California (Western US Wildfires)" },
  amazon: { center: [-9.5, -58.5], zoom: 5, altitude: 1.6, name: "Amazon Basin & Pantanal (South America)" },
  australia: { center: [-34.5, 147.0], zoom: 6, altitude: 1.5, name: "Southeastern Australia (Bushfires)" },
  punjab_crop: { center: [30.9, 75.8], zoom: 7, altitude: 1.1, name: "Punjab & Haryana (Crop Residue)" },
  mediterranean: { center: [39.5, 15.0], zoom: 5, altitude: 1.6, name: "Mediterranean Basin (Southern Europe)" }
};

// Application State
const state = {
  currentRegion: "california",
  currentYear: 2020,
  calendarData: null,
  anomalyData: null,
  liveData: null,
  currentHotspots: [],
  map: null,
  markersLayer: null,
  globe: null,
  globeMode: "3d", // "3d" or "2d"
  autoRotate: true,
  isSwitchingMode: false,
  charts: {
    climatology: null,
    discontinuity: null
  }
};

// DOY to Month/Day Converter for human-friendly tooltips
function doyToDateStr(year, doy) {
  const d = new Date(year, 0, 1);
  d.setDate(doy);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// Color scale for burning activity calendar heatmap
function getHeatmapColor(value, maxVal) {
  if (!value || value <= 0) return "#151c2c";
  const norm = Math.min(1.0, value / Math.max(10.0, maxVal));
  if (norm < 0.15) return "#0284c7"; // light cyan/blue
  if (norm < 0.35) return "#0d9488"; // teal
  if (norm < 0.60) return "#f59e0b"; // amber
  if (norm < 0.85) return "#ea580c"; // orange fire
  return "#dc2626"; // intense red
}

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initMap();
  initGlobe();
  setupEventListeners();
  loadRegionData(state.currentRegion);
});

// Setup Tab Switching
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add("active");
        if (targetId === "tabMap") {
          setTimeout(() => {
            if (state.globeMode === "3d" && state.globe) {
              const cont = document.getElementById("globeContainer");
              if (cont && cont.clientWidth > 0) {
                state.globe.width(cont.clientWidth);
                state.globe.height(cont.clientHeight);
              }
            } else if (state.map) {
              state.map.invalidateSize();
            }
          }, 150);
        } else if (targetId === "tabBriefing") {
          loadBriefingReport();
        }
      }
    });
  });

  // Support ?tab= in URL for direct tab loading & screenshots
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get("tab");
  if (initialTab) {
    const btn = document.querySelector(`[data-tab="${initialTab}"]`);
    if (btn) {
      setTimeout(() => btn.click(), 200);
    }
  }
}

// Setup Event Listeners
function setupEventListeners() {
  // Region Selection
  const regSelect = document.getElementById("regionSelect");
  if (regSelect) {
    regSelect.addEventListener("change", (e) => {
      state.currentRegion = e.target.value;
      loadRegionData(state.currentRegion);
    });
  }

  // Target Year Selection
  const yrSelect = document.getElementById("targetYearSelect");
  if (yrSelect) {
    yrSelect.addEventListener("change", (e) => {
      state.currentYear = parseInt(e.target.value);
      updateAnomaliesForYear(state.currentYear);
    });
  }

  // Live NASA FIRMS Stream Button
  const btnLive = document.getElementById("btnLiveFirms");
  if (btnLive) {
    btnLive.addEventListener("click", () => fetchLiveFIRMS());
  }

  // Generate / View Briefing Button in Header
  const btnBriefing = document.getElementById("btnGenerateReport");
  if (btnBriefing) {
    btnBriefing.addEventListener("click", () => {
      const briefingTab = document.querySelector('[data-tab="tabBriefing"]');
      if (briefingTab) briefingTab.click();
      loadBriefingReport();
    });
  }

  // Mode Switcher: 3D Globe vs 2D Tactical Map
  const btnGlobe = document.getElementById("btnModeGlobe");
  if (btnGlobe) {
    btnGlobe.addEventListener("click", () => {
      const reg = REGION_CENTERS[state.currentRegion] || REGION_CENTERS.california;
      switchTo3DGlobe(reg.center[0], reg.center[1], reg.altitude);
    });
  }

  const btnMap = document.getElementById("btnModeMap");
  if (btnMap) {
    btnMap.addEventListener("click", () => {
      const reg = REGION_CENTERS[state.currentRegion] || REGION_CENTERS.california;
      switchTo2DMap(reg.center[0], reg.center[1], reg.zoom);
    });
  }

  // Quick Action Buttons on 3D Globe
  const btnFly = document.getElementById("btnFlyRegion");
  if (btnFly) {
    btnFly.addEventListener("click", () => {
      const reg = REGION_CENTERS[state.currentRegion] || REGION_CENTERS.california;
      if (state.globeMode === "3d" && state.globe) {
        state.globe.pointOfView({ lat: reg.center[0], lng: reg.center[1], altitude: reg.altitude }, 1200);
      } else if (state.map) {
        state.map.flyTo(reg.center, reg.zoom);
      }
    });
  }

  const btnReset = document.getElementById("btnResetOrbit");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      if (state.globeMode === "3d" && state.globe) {
        state.globe.pointOfView({ lat: 20.0, lng: 0.0, altitude: 2.5 }, 1200);
      } else if (state.map) {
        state.map.flyTo([20.0, 0.0], 2);
      }
    });
  }

  const btnRotate = document.getElementById("btnToggleRotate");
  if (btnRotate) {
    btnRotate.addEventListener("click", () => {
      if (state.globe && state.globe.controls()) {
        state.autoRotate = !state.autoRotate;
        state.globe.controls().autoRotate = state.autoRotate;
        if (state.autoRotate) {
          btnRotate.classList.add("active");
        } else {
          btnRotate.classList.remove("active");
        }
      }
    });
  }

  // Raw Markdown Drawer Toggle (Incident Briefing)
  const drawerHeader = document.getElementById("btnToggleRawDrawer");
  if (drawerHeader) {
    drawerHeader.addEventListener("click", () => {
      const box = document.getElementById("briefingContent");
      const icon = document.getElementById("drawerToggleIcon");
      if (box.style.display === "none") {
        box.style.display = "block";
        if (icon) icon.innerText = "▲";
      } else {
        box.style.display = "none";
        if (icon) icon.innerText = "▼";
      }
    });
  }

  // Copy Briefing Text to Clipboard
  const btnCopy = document.getElementById("btnCopyBriefing");
  if (btnCopy) {
    btnCopy.addEventListener("click", () => {
      const text = document.getElementById("briefingContent").innerText;
      navigator.clipboard.writeText(text).then(() => {
        btnCopy.innerText = "Copied!";
        setTimeout(() => btnCopy.innerText = "Copy Text", 2000);
      });
    });
  }

  // Download Briefing as Markdown File
  const btnDownload = document.getElementById("btnDownloadBriefing");
  if (btnDownload) {
    btnDownload.addEventListener("click", () => {
      const text = document.getElementById("briefingContent").innerText;
      const blob = new Blob([text], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Incident_Commander_Briefing_${state.currentRegion}_${state.currentYear}.md`;
      a.click();
    });
  }
}

// Initialize Leaflet 2D Tactical Map
function initMap() {
  state.map = L.map("map", {
    zoomControl: true,
    attributionControl: false
  }).setView([37.2, -119.5], 6);

  // High contrast dark tile provider without watermark (Esri Dark Gray Canvas)
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 16,
    attribution: "Esri, HERE, DeLorme, MapmyIndia"
  }).addTo(state.map);

  state.markersLayer = L.layerGroup().addTo(state.map);
}

// Initialize WebGL 3D Globe with Globe.gl
function initGlobe() {
  const container = document.getElementById("globeContainer");
  if (!container || typeof Globe === "undefined") {
    console.warn("Globe.gl container or library not ready.");
    return;
  }

  try {
    state.globe = Globe()(container)
      .globeImageUrl("//unpkg.com/three-globe/example/img/earth-night.jpg")
      .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
      .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
      .showAtmosphere(true)
      .atmosphereColor("#3b82f6")
      .atmosphereAltitude(0.2)
      .pointLat("latitude")
      .pointLng("longitude")
      .pointAltitude(d => Math.min(0.22, 0.02 + ((d.frp || 15) / 1000)))
      .pointRadius(d => d.is_cluster_centroid ? 0.45 : (d.instrument && d.instrument.includes("MODIS") ? 0.32 : 0.22))
      .pointColor(d => d.is_cluster_centroid ? "#f59e0b" : (d.instrument && d.instrument.includes("MODIS") ? "#06b6d4" : "#ff5722"))
      .pointLabel(d => `
        <div style="background: rgba(15,23,42,0.92); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 8px 12px; font-family: -apple-system, sans-serif; font-size: 11px; color: #f1f5f9; box-shadow: 0 4px 14px rgba(0,0,0,0.5); min-width: 190px;">
          <div style="font-weight: 700; color: ${d.is_cluster_centroid ? '#f59e0b' : (d.instrument && d.instrument.includes('MODIS') ? '#06b6d4' : '#ff5722')}; font-size: 12px; margin-bottom: 4px;">
            ${d.instrument || 'Satellite Hotspot'} ${d.is_cluster_centroid ? '★ Clustered Centroid' : 'Detection'}
          </div>
          <div><strong>Coordinates:</strong> ${d.latitude.toFixed(4)}, ${d.longitude.toFixed(4)}</div>
          <div><strong>Acquisition:</strong> ${d.acq_date || 'N/A'} ${d.acq_time || ''} UTC</div>
          <div><strong>Raw FRP:</strong> ${d.frp || 0} MW</div>
          <div style="border-top: 1px solid rgba(255,255,255,0.1); margin: 4px 0; padding-top: 4px;">
            <span style="color: #ea580c; font-weight: 600;">Harmonized FRP: ${d.frp_harmonized || d.frp || 0} MW</span>
          </div>
          <div><strong>ESFP:</strong> ${d.esfp || 1.0} eq &bull; <strong>HFII:</strong> ${d.hfii || 0}</div>
        </div>
      `);

    // Setup globe controls & auto-rotation
    const controls = state.globe.controls();
    if (controls) {
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.5;
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;

      // Dynamic Auto-Switch: When user scrolls in close (altitude < 0.35), seamlessly switch to 2D tactical map!
      controls.addEventListener("change", () => {
        if (state.globeMode === "3d" && !state.isSwitchingMode) {
          const pov = state.globe.pointOfView();
          if (pov && pov.altitude < 0.35) {
            switchTo2DMap(pov.lat, pov.lng, 8);
          }
        }
      });
    }

    // Set initial view centered on California
    state.globe.pointOfView({ lat: 37.2, lng: -119.5, altitude: 1.6 }, 1000);

    // Responsive container resize listener
    window.addEventListener("resize", () => {
      if (state.globe && container.clientWidth > 0 && container.clientHeight > 0) {
        state.globe.width(container.clientWidth);
        state.globe.height(container.clientHeight);
      }
    });

  } catch (err) {
    console.warn("WebGL 3D Globe initialization notice:", err);
  }
}

// Switch Mode to 2D Tactical Map
function switchTo2DMap(lat, lng, zoom = 7) {
  state.globeMode = "2d";
  state.isSwitchingMode = true;

  const btnGlobe = document.getElementById("btnModeGlobe");
  const btnMap = document.getElementById("btnModeMap");
  const globeCont = document.getElementById("globeContainer");
  const mapCont = document.getElementById("mapContainer");
  const statusText = document.getElementById("mapStatusText");

  if (btnGlobe) btnGlobe.classList.remove("active");
  if (btnMap) btnMap.classList.add("active");

  if (globeCont) globeCont.style.display = "none";
  if (mapCont) {
    mapCont.style.display = "block";
    if (state.map) {
      state.map.invalidateSize();
      if (lat !== undefined && lng !== undefined) {
        state.map.setView([lat, lng], zoom);
      }
    }
  }

  if (statusText) {
    statusText.innerText = "2D Tactical Map • High-resolution surface basemap & clustered fire perimeters";
  }

  setTimeout(() => {
    state.isSwitchingMode = false;
  }, 400);
}

// Switch Mode to 3D Orbital Globe
function switchTo3DGlobe(lat, lng, altitude = 1.6) {
  state.globeMode = "3d";
  state.isSwitchingMode = true;

  const btnGlobe = document.getElementById("btnModeGlobe");
  const btnMap = document.getElementById("btnModeMap");
  const globeCont = document.getElementById("globeContainer");
  const mapCont = document.getElementById("mapContainer");
  const statusText = document.getElementById("mapStatusText");

  if (btnGlobe) btnGlobe.classList.add("active");
  if (btnMap) btnMap.classList.remove("active");

  if (mapCont) mapCont.style.display = "none";
  if (globeCont) {
    globeCont.style.display = "block";
    if (state.globe) {
      const cont = document.getElementById("globeContainer");
      if (cont && cont.clientWidth > 0) {
        state.globe.width(cont.clientWidth);
        state.globe.height(cont.clientHeight);
      }
      if (lat !== undefined && lng !== undefined) {
        state.globe.pointOfView({ lat, lng, altitude }, 800);
      }
    }
  }

  if (statusText) {
    statusText.innerText = "3D WebGL Globe • Interactive satellite hotspots & harmonized fire centroids";
  }

  setTimeout(() => {
    state.isSwitchingMode = false;
  }, 400);
}

// Load Region Data & Calendar
async function loadRegionData(regionKey) {
  try {
    showLoadingIndicators();
    const res = await fetch("/api/calendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region_key: regionKey, biome: "forest" })
    });
    
    if (!res.ok) throw new Error(`Calendar API failed: ${res.statusText}`);
    const data = await res.json();
    state.calendarData = data;

    // Populate Year dropdown
    const yrSelect = document.getElementById("targetYearSelect");
    yrSelect.innerHTML = "";
    data.years.forEach(yr => {
      const opt = document.createElement("option");
      opt.value = yr;
      opt.textContent = yr;
      if (yr === 2020) opt.selected = true;
      yrSelect.appendChild(opt);
    });
    state.currentYear = parseInt(yrSelect.value);

    // Update geospatial camera to region center
    const regMeta = REGION_CENTERS[regionKey] || (data.region_info && { center: data.region_info.center, zoom: data.region_info.zoom, altitude: 1.5 });
    if (regMeta) {
      const [cLat, cLng] = regMeta.center;
      if (state.globe && state.globeMode === "3d") {
        state.globe.pointOfView({ lat: cLat, lng: cLng, altitude: regMeta.altitude || 1.5 }, 1000);
      }
      if (state.map) {
        state.map.setView([cLat, cLng], regMeta.zoom || 6);
      }
    }

    // Render Calendar Canvas & Diagnostic
    renderCalendarHeatmap(data);
    renderDiscontinuityDiagnostic(data);

    // Load Anomalies for initial year
    await updateAnomaliesForYear(state.currentYear);

    // Load sample regional hotspots onto both 3D Globe and 2D Map
    loadRegionalMapHotspots(regionKey);

  } catch (err) {
    console.error("Error loading region data:", err);
  }
}

// Render Calendar Heatmap on Canvas
function renderCalendarHeatmap(data) {
  const canvas = document.getElementById("calendarCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const years = data.years;
  const numYears = years.length;
  const numDays = 365;

  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const leftMargin = 55;
  const topMargin = 25;
  const cellWidth = (width - leftMargin - 15) / numDays;
  const cellHeight = (height - topMargin - 20) / numYears;

  // Max HFII for normalization
  const maxHfii = Math.max(...data.calendar_cells.map(c => c.hfii), 100);

  // Quick lookup table: [year][doy]
  const cellMap = {};
  data.calendar_cells.forEach(c => {
    if (!cellMap[c.year]) cellMap[c.year] = {};
    cellMap[c.year][c.doy] = c;
  });

  // Draw Month markers on top
  ctx.fillStyle = "#9ca3af";
  ctx.font = "10px -apple-system, sans-serif";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthDoys = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
  months.forEach((m, i) => {
    const x = leftMargin + (monthDoys[i] - 1) * cellWidth;
    ctx.fillText(m, x + 2, 16);
  });

  // Draw Grid Rows
  years.forEach((yr, rowIdx) => {
    const y = topMargin + rowIdx * cellHeight;

    // Year Label
    ctx.fillStyle = (yr === state.currentYear) ? "#f59e0b" : "#6b7280";
    ctx.font = (yr === state.currentYear) ? "bold 11px monospace" : "10px monospace";
    ctx.fillText(yr.toString(), 10, y + cellHeight - 3);

    // Days in year
    for (let doy = 1; doy <= numDays; doy++) {
      const x = leftMargin + (doy - 1) * cellWidth;
      const cell = cellMap[yr] ? cellMap[yr][doy] : null;
      const hfii = cell ? cell.hfii : 0;

      ctx.fillStyle = getHeatmapColor(hfii, maxHfii);
      ctx.fillRect(x, y, Math.max(1, cellWidth - 0.5), Math.max(1, cellHeight - 1));
    }
  });

  // Canvas Mouse Click interaction
  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) * (canvas.width / rect.width);
    const clickY = (e.clientY - rect.top) * (canvas.height / rect.height);

    if (clickX >= leftMargin && clickY >= topMargin) {
      const rowIdx = Math.floor((clickY - topMargin) / cellHeight);
      if (rowIdx >= 0 && rowIdx < years.length) {
        state.currentYear = years[rowIdx];
        document.getElementById("targetYearSelect").value = state.currentYear;
        updateAnomaliesForYear(state.currentYear);
        renderCalendarHeatmap(data); // Redraw to highlight active year
      }
    }
  };
}

// Update Anomalies & Climatology Chart
async function updateAnomaliesForYear(year) {
  try {
    const res = await fetch("/api/anomalies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region_key: state.currentRegion, year: year })
    });
    
    if (!res.ok) throw new Error("Anomalies API failed");
    const anom = await res.json();
    state.anomalyData = anom;

    // Update KPI Barometer Cards
    const timeline = anom.daily_timeline || [];
    const totalHfii = timeline.reduce((acc, d) => acc + (d.hfii || 0), 0);
    const totalEsfp = timeline.reduce((acc, d) => acc + (d.esfp || 0), 0);
    const peakZ = anom.summary.peak_z_score || 0;
    const maxSev = anom.summary.max_severity || "NORMAL";

    document.getElementById("kpiHfii").innerText = Math.round(totalHfii).toLocaleString();
    document.getElementById("kpiEsfp").innerText = Math.round(totalEsfp).toLocaleString();
    document.getElementById("kpiAnomaly").innerText = `${peakZ > 0 ? "+" : ""}${peakZ}σ`;
    
    const kpiThreat = document.getElementById("kpiThreat");
    kpiThreat.innerText = maxSev;
    kpiThreat.style.color = (maxSev === "CRITICAL") ? "var(--accent-rose)" : (maxSev === "SEVERE" ? "var(--accent-amber)" : "var(--accent-emerald)");
    document.getElementById("kpiThreatSub").innerText = `${anom.summary.total_critical_periods} critical surge events identified`;

    // Render Climatology Envelope Chart
    renderClimatologyChart(state.calendarData.climatology, timeline, year);

    // Populate Critical Periods Table
    populateCriticalPeriodsTable(anom.critical_periods, year);

  } catch (err) {
    console.error("Error updating anomalies:", err);
  }
}

// Render Climatology Envelope Chart (Chart.js)
function renderClimatologyChart(climatology, timeline, targetYear) {
  const canvas = document.getElementById("climatologyChart");
  if (!canvas) return;

  const labels = climatology.map(c => `DOY ${c.doy}`);
  const p10 = climatology.map(c => c.hfii_p10);
  const p50 = climatology.map(c => c.hfii_p50);
  const p90 = climatology.map(c => c.hfii_p90);
  const p95 = climatology.map(c => c.hfii_p95);
  const observed = timeline.map(t => t.hfii);

  if (state.charts.climatology) {
    state.charts.climatology.destroy();
  }

  state.charts.climatology = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: `${targetYear} Observed HFII`,
          data: observed,
          borderColor: "#ff5722",
          borderWidth: 2.2,
          pointRadius: 0,
          tension: 0.2,
          order: 1
        },
        {
          label: "90th Percentile (Severe Threshold)",
          data: p90,
          borderColor: "rgba(239, 68, 68, 0.7)",
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          order: 2
        },
        {
          label: "50th Percentile (Median Climatology)",
          data: p50,
          borderColor: "#f59e0b",
          borderWidth: 1.8,
          pointRadius: 0,
          fill: false,
          order: 3
        },
        {
          label: "10th–90th Climatology Envelope",
          data: p90,
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          borderColor: "transparent",
          pointRadius: 0,
          fill: "+1",
          order: 4
        },
        {
          label: "Envelope Lower Bound",
          data: p10,
          borderColor: "transparent",
          pointRadius: 0,
          fill: false,
          order: 5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#9ca3af", font: { size: 11 } }
        },
        tooltip: {
          backgroundColor: "#111827",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          callbacks: {
            title: (items) => {
              const doy = items[0].dataIndex + 1;
              return `DOY ${doy} (${doyToDateStr(targetYear, doy)})`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#6b7280", maxTicksLimit: 12 },
          grid: { color: "rgba(255, 255, 255, 0.03)" }
        },
        y: {
          title: { display: true, text: "Harmonized Fire Intensity (HFII)", color: "#9ca3af" },
          ticks: { color: "#6b7280" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        }
      }
    }
  });
}

// Populate Critical Burning Periods Table
function populateCriticalPeriodsTable(periods, year) {
  const tbody = document.getElementById("criticalPeriodsTableBody");
  if (!tbody) return;

  if (!periods || periods.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No critical burning surge anomalies detected in ${year}.</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  periods.forEach(p => {
    const tr = document.createElement("tr");
    const startDate = doyToDateStr(year, p.start_doy);
    const endDate = doyToDateStr(year, p.end_doy);
    const isExtreme = p.mean_z_score >= 3.0;

    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 600;">${p.year}</td>
      <td style="font-family: var(--font-mono);">DOY ${p.start_doy}–${p.end_doy}</td>
      <td>${startDate} – ${endDate}</td>
      <td>${p.duration_days} days</td>
      <td style="font-family: var(--font-mono); color: var(--accent-amber); font-weight: 600;">${p.peak_hfii}</td>
      <td style="font-family: var(--font-mono); color: var(--accent-rose); font-weight: 600;">+${p.mean_z_score}σ</td>
      <td>
        <span class="badge-tag ${isExtreme ? 'badge-critical' : 'badge-severe'}">
          ${p.threat_level}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Render Discontinuity Diagnostic View (Raw vs Harmonized)
function renderDiscontinuityDiagnostic(data) {
  const dynamics = data.annual_dynamics || [];
  if (dynamics.length === 0) return;

  const pre2012 = dynamics.filter(d => d.year < 2012);
  const post2012 = dynamics.filter(d => d.year >= 2012);

  const meanRawPre = pre2012.reduce((a, b) => a + b.total_raw_count, 0) / Math.max(1, pre2012.length);
  const meanRawPost = post2012.reduce((a, b) => a + b.total_raw_count, 0) / Math.max(1, post2012.length);
  const rawInflation = ((meanRawPost - meanRawPre) / Math.max(1, meanRawPre)) * 100;

  const meanHarmPre = pre2012.reduce((a, b) => a + b.total_hfii, 0) / Math.max(1, pre2012.length);
  const meanHarmPost = post2012.reduce((a, b) => a + b.total_hfii, 0) / Math.max(1, post2012.length);
  const harmVar = ((meanHarmPost - meanHarmPre) / Math.max(1, meanHarmPre)) * 100;

  document.getElementById("rawInflationVal").innerText = `+${rawInflation.toFixed(1)}%`;
  document.getElementById("harmVariationVal").innerText = `${harmVar >= 0 ? "+" : ""}${harmVar.toFixed(1)}%`;

  // Render Multi-Decadal Discontinuity Chart
  const canvas = document.getElementById("discontinuityChart");
  if (!canvas) return;

  if (state.charts.discontinuity) {
    state.charts.discontinuity.destroy();
  }

  const labels = dynamics.map(d => d.year.toString());
  const rawCounts = dynamics.map(d => d.total_raw_count);
  const harmonizedHfii = dynamics.map(d => d.total_hfii);

  state.charts.discontinuity = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          type: "bar",
          label: "Raw Unharmonized Hotspot Count (Artificial 2012 Jump)",
          data: rawCounts,
          backgroundColor: labels.map(y => parseInt(y) >= 2012 ? "rgba(244, 63, 94, 0.45)" : "rgba(156, 163, 175, 0.3)"),
          borderColor: labels.map(y => parseInt(y) >= 2012 ? "#f43f5e" : "#9ca3af"),
          borderWidth: 1.2,
          yAxisID: "yRaw"
        },
        {
          type: "line",
          label: "Pyro-Harmony Harmonized Fire Intensity (True Climate Continuity)",
          data: harmonizedHfii,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          borderWidth: 2.5,
          pointRadius: 3,
          tension: 0.2,
          yAxisID: "yHarm"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#9ca3af", font: { size: 11 } } },
        tooltip: { backgroundColor: "#111827", borderColor: "rgba(255,255,255,0.1)", borderWidth: 1 }
      },
      scales: {
        x: { ticks: { color: "#6b7280" }, grid: { color: "rgba(255,255,255,0.03)" } },
        yRaw: {
          type: "linear",
          position: "left",
          title: { display: true, text: "Raw Hotspot Count", color: "#f43f5e" },
          ticks: { color: "#f43f5e" },
          grid: { color: "rgba(255, 255, 255, 0.04)" }
        },
        yHarm: {
          type: "linear",
          position: "right",
          title: { display: true, text: "Harmonized Fire Intensity (HFII)", color: "#10b981" },
          ticks: { color: "#10b981" },
          grid: { drawOnChartArea: false }
        }
      }
    }
  });
}

// Load Regional Hotspots onto 3D Globe & 2D Map
async function loadRegionalMapHotspots(regionKey) {
  try {
    const res = await fetch(`/api/live-stream?region_key=${regionKey}&limit=600`);
    const data = await res.json();
    if (data.status === "success" && data.hotspots && data.hotspots.length > 0) {
      renderHotspots(data.hotspots, "Regional FIRMS Hotspots & Clustered Events");
    } else {
      document.getElementById("mapStatusText").innerText = "No current hotspots in selected region.";
    }
  } catch (e) {
    console.warn("Could not load regional map hotspots:", e);
  }
}

// Unified Hotspot Renderer for 3D Globe and 2D Leaflet Map
function renderHotspots(hotspots, statusMsg) {
  state.currentHotspots = hotspots;
  
  // 1. Update 3D Globe
  if (state.globe) {
    state.globe.pointsData(hotspots);
  }

  // 2. Update 2D Leaflet Map
  if (state.map && state.markersLayer) {
    state.markersLayer.clearLayers();
    hotspots.forEach(pt => {
      const isCentroid = pt.is_cluster_centroid;
      const isModis = pt.instrument && pt.instrument.includes("MODIS");
      
      let color = isModis ? "#06b6d4" : "#ff5722";
      let radius = isModis ? 6 : 4;
      let fillOpacity = 0.65;

      if (isCentroid) {
        color = "#f59e0b";
        radius = 8;
        fillOpacity = 0.9;
      }

      const circle = L.circleMarker([pt.latitude, pt.longitude], {
        radius: radius,
        color: color,
        fillColor: color,
        fillOpacity: fillOpacity,
        weight: isCentroid ? 2 : 1
      });

      const popupHtml = `
        <div style="font-family: -apple-system, sans-serif; font-size: 12px; color: #111;">
          <strong style="color: ${color}; font-size: 13px;">${pt.instrument} Detection</strong><br/>
          <strong>Coordinates:</strong> ${pt.latitude.toFixed(4)}, ${pt.longitude.toFixed(4)}<br/>
          <strong>Acquisition:</strong> ${pt.acq_date} ${pt.acq_time} UTC<br/>
          <strong>Raw FRP:</strong> ${pt.frp} MW<br/>
          <hr style="margin: 4px 0; border: none; border-top: 1px solid #ddd;"/>
          <strong style="color: #ea580c;">Harmonized FRP:</strong> ${pt.frp_harmonized} MW<br/>
          <strong>Equivalent Pixels (ESFP):</strong> ${pt.esfp}<br/>
          <strong>Harmonized Index (HFII):</strong> ${pt.hfii}<br/>
          <strong>Cluster Size:</strong> ${pt.cluster_pixel_count} pixels
        </div>
      `;

      circle.bindPopup(popupHtml);
      state.markersLayer.addLayer(circle);
    });
  }

  const statusLabel = document.getElementById("mapStatusText");
  if (statusLabel) {
    statusLabel.innerText = `${statusMsg} (${hotspots.length} detections plotted)`;
  }
}

// Fetch Live 24h Global FIRMS Stream
async function fetchLiveFIRMS() {
  const btn = document.getElementById("btnLiveFirms");
  btn.innerHTML = "<span>⏳</span> Pulling Stream...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/live-stream?limit=1200");
    const data = await res.json();
    if (data.status === "success" && data.hotspots) {
      // Switch to Map tab
      const mapTab = document.querySelector('[data-tab="tabMap"]');
      if (mapTab) mapTab.click();

      renderHotspots(data.hotspots, "Live Global 24h NASA FIRMS Hotspots (Satellite Stream)");
      
      // Update viewpoint to show global density
      if (state.globeMode === "3d" && state.globe) {
        state.globe.pointOfView({ lat: 15.0, lng: 10.0, altitude: 2.2 }, 1200);
      } else if (state.map) {
        state.map.setView([20.0, 0.0], 2);
      }
    }
  } catch (err) {
    console.error("Failed to fetch live FIRMS stream:", err);
  } finally {
    btn.innerHTML = "<span>📡</span> Live FIRMS (24h)";
    btn.disabled = false;
  }
}

// Load Automated Incident Commander Briefing
async function loadBriefingReport() {
  const box = document.getElementById("briefingContent");
  box.innerText = "Generating operational briefing from multi-decadal model...";

  try {
    const res = await fetch("/api/export-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        region_key: state.currentRegion,
        year: state.currentYear,
        threat_level: state.anomalyData ? state.anomalyData.summary.max_severity : "MONITORING"
      })
    });
    const data = await res.json();

    // 1. Raw markdown in background drawer
    box.innerText = data.content;

    // 2. Render Executive Structured Briefing
    if (data.structured) {
      renderExecutiveBriefing(data.structured);
    }
  } catch (err) {
    box.innerText = "Error generating briefing: " + err.message;
  }
}

// Render Executive Briefing UI
function renderExecutiveBriefing(struct) {
  // Title & Subtitle
  const areaTitle = document.getElementById("briefingAreaTitle");
  if (areaTitle) {
    areaTitle.innerText = `${struct.area_of_interest} • Tactical Briefing`;
  }

  const metaSubtitle = document.getElementById("briefingMetaSubtitle");
  if (metaSubtitle) {
    metaSubtitle.innerText = `Target Year: ${struct.target_year} • Biome: ${struct.fuel_biome} • Authority: ${struct.operational_authority}`;
  }

  // Threat Ribbon
  const badge = document.getElementById("briefingThreatBadge");
  const threatText = document.getElementById("briefingThreatText");
  const sev = struct.threat_level || (struct.summary && struct.summary.max_severity) || "MONITORING";

  if (badge) {
    badge.className = "threat-ribbon " + (sev === "CRITICAL" ? "threat-critical" : (sev === "SEVERE" ? "threat-severe" : "threat-normal"));
  }
  if (threatText) {
    threatText.innerText = (sev === "CRITICAL" ? "CRITICAL SURGE ADVISORY" : (sev === "SEVERE" ? "SEVERE FIRE WEATHER ADVISORY" : "ROUTINE MONITORING LEVEL"));
  }

  // Meta Cards
  const surgeCount = document.getElementById("briefingSurgeCount");
  if (surgeCount) {
    surgeCount.innerText = `${struct.summary.critical_periods_count || 0} Periods`;
  }

  const peakZ = document.getElementById("briefingPeakZ");
  if (peakZ) {
    const z = struct.summary.peak_z_score || 0;
    peakZ.innerText = `${z > 0 ? "+" : ""}${z}σ`;
  }

  const artifactCured = document.getElementById("briefingArtifactCured");
  if (artifactCured) {
    const infl = struct.sensor_harmonization.raw_inflation || 0;
    artifactCured.innerText = `+${infl}% Normalized`;
  }

  // Critical Surge Cards
  const surgeGrid = document.getElementById("briefingSurgeCards");
  if (surgeGrid) {
    surgeGrid.innerHTML = "";
    const periods = struct.critical_periods || [];
    if (periods.length === 0) {
      surgeGrid.innerHTML = `<div style="grid-column: 1/-1; color: var(--text-muted); font-size: 0.85rem; padding: 1rem; text-align: center;">No critical burning surge periods detected for ${struct.target_year}. Baseline conditions maintained.</div>`;
    } else {
      periods.forEach((cp, idx) => {
        const startDate = doyToDateStr(struct.target_year, cp.start_doy);
        const endDate = doyToDateStr(struct.target_year, cp.end_doy);
        const isCrit = cp.mean_z_score >= 3.0;

        const card = document.createElement("div");
        card.className = "surge-card";
        card.innerHTML = `
          <div class="surge-card-header">
            <span class="surge-dates">Window #${idx + 1}: ${startDate} – ${endDate}</span>
            <span class="badge-tag ${isCrit ? 'badge-critical' : 'badge-severe'}">${cp.threat_level}</span>
          </div>
          <div style="font-size: 0.78rem; color: var(--text-secondary); margin: 2px 0;">
            DOY ${cp.start_doy} to ${cp.end_doy} &bull; Duration: <strong>${cp.duration_days} days</strong>
          </div>
          <div class="surge-stats">
            <span>Peak: <strong style="color: var(--accent-amber);">${cp.peak_hfii} HFII</strong></span>
            <span>Anomaly: <strong style="color: var(--accent-rose);">+${cp.mean_z_score}σ</strong></span>
          </div>
        `;
        surgeGrid.appendChild(card);
      });
    }
  }
}

function showLoadingIndicators() {
  document.getElementById("kpiHfii").innerText = "Loading...";
  document.getElementById("kpiEsfp").innerText = "Loading...";
  document.getElementById("kpiAnomaly").innerText = "--";
  document.getElementById("kpiThreat").innerText = "COMPUTING";
}

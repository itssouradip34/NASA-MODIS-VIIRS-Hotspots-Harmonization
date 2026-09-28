/**
 * Pyro-Harmony Frontend Application Logic.
 * Grounded in operational Earth Observation science & intuitive user experience.
 */

// Application State
const state = {
  currentRegion: "california",
  currentYear: 2020,
  calendarData: null,
  anomalyData: null,
  liveData: null,
  map: null,
  markersLayer: null,
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
        if (targetId === "tabMap" && state.map) {
          setTimeout(() => state.map.invalidateSize(), 150);
        }
      }
    });
  });
}

// Setup Event Listeners
function setupEventListeners() {
  const regSelect = document.getElementById("regionSelect");
  if (regSelect) {
    regSelect.addEventListener("change", (e) => {
      state.currentRegion = e.target.value;
      loadRegionData(state.currentRegion);
    });
  }

  const yrSelect = document.getElementById("targetYearSelect");
  if (yrSelect) {
    yrSelect.addEventListener("change", (e) => {
      state.currentYear = parseInt(e.target.value);
      updateAnomaliesForYear(state.currentYear);
    });
  }

  const btnLive = document.getElementById("btnLiveFirms");
  if (btnLive) {
    btnLive.addEventListener("click", () => fetchLiveFIRMS());
  }

  const btnBriefing = document.getElementById("btnGenerateReport");
  if (btnBriefing) {
    btnBriefing.addEventListener("click", () => {
      const briefingTab = document.querySelector('[data-tab="tabBriefing"]');
      if (briefingTab) briefingTab.click();
      loadBriefingReport();
    });
  }

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

// Initialize Leaflet Map
function initMap() {
  state.map = L.map("map", {
    zoomControl: true,
    attributionControl: false
  }).setView([37.2, -119.5], 6);

  // High contrast dark tile provider
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 18,
    subdomains: "abcd"
  }).addTo(state.map);

  state.markersLayer = L.layerGroup().addTo(state.map);
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

    // Update map view to region center
    if (data.region_info && data.region_info.center) {
      state.map.setView(data.region_info.center, data.region_info.zoom || 6);
    }

    // Render Calendar Canvas & Diagnostic
    renderCalendarHeatmap(data);
    renderDiscontinuityDiagnostic(data);

    // Load Anomalies for initial year
    await updateAnomaliesForYear(state.currentYear);

    // Load sample hotspots onto map for visualization
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

  // Canvas Mouse Click/Hover interaction
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
    kpiThreat.style.color = (maxSev === "CRITICAL") ? "var(--accent-rose)" : "var(--accent-emerald)";
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

// Load Regional Hotspots onto Map
async function loadRegionalMapHotspots(regionKey) {
  if (!state.map || !state.markersLayer) return;
  state.markersLayer.clearLayers();

  // Load a subset of real/archive hotspots to visualize clustering
  try {
    const res = await fetch(`/api/live-stream?region_key=${regionKey}&limit=600`);
    const data = await res.json();
    if (data.status === "success" && data.hotspots && data.hotspots.length > 0) {
      renderHotspotsOnMap(data.hotspots, "Active FIRMS Hotspots & Clustered Events");
    } else {
      document.getElementById("mapStatusText").innerText = "No current hotspots in selected region.";
    }
  } catch (e) {
    console.warn("Could not load regional map hotspots:", e);
  }
}

// Render Hotspots onto Leaflet Map
function renderHotspotsOnMap(hotspots, statusMsg) {
  state.markersLayer.clearLayers();
  document.getElementById("mapStatusText").innerText = `${statusMsg} (${hotspots.length} detections)`;

  hotspots.forEach(pt => {
    const isCentroid = pt.is_cluster_centroid;
    const isModis = pt.instrument.includes("MODIS");
    
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

// Fetch Live 24h Global FIRMS Stream
async function fetchLiveFIRMS() {
  const btn = document.getElementById("btnLiveFirms");
  btn.innerHTML = "<span>⏳</span> Pulling Stream...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/live-stream?limit=1000");
    const data = await res.json();
    if (data.status === "success" && data.hotspots) {
      // Switch to Map tab
      const mapTab = document.querySelector('[data-tab="tabMap"]');
      if (mapTab) mapTab.click();

      renderHotspotsOnMap(data.hotspots, "Live Global 24h NASA FIRMS Hotspots");
      state.map.setView([20.0, 0.0], 2); // Global overview
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
    box.innerText = data.content;
  } catch (err) {
    box.innerText = "Error generating briefing: " + err.message;
  }
}

function showLoadingIndicators() {
  document.getElementById("kpiHfii").innerText = "Loading...";
  document.getElementById("kpiEsfp").innerText = "Loading...";
  document.getElementById("kpiAnomaly").innerText = "--";
  document.getElementById("kpiThreat").innerText = "COMPUTING";
}

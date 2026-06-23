from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import m7_dashboard_server as m7


st.set_page_config(
    page_title="Event-Driven Congestion Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)


CAUSES = [
    "vehicle_breakdown",
    "vip_movement",
    "water_logging",
    "accident",
    "construction",
    "tree_fall",
    "pot_holes",
]


def css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
          --m7-ink: #0f172a;
          --m7-muted: #64748b;
          --m7-line: #e2e8f0;
          --m7-panel: #ffffff;
          --m7-soft: #f0f9f8;
          --m7-teal: #0d9488;
          --m7-teal-dark: #0f766e;
          --m7-blue: #2563eb;
          --m7-red: #dc2626;
          --m7-orange: #f97316;
          --m7-bg: #f8fafc;
        }

        html, body, [class*="css"] {
          font-family: 'Inter', Segoe UI, Arial, sans-serif;
        }

        .block-container {
          padding-top: 1rem;
          padding-bottom: 2.5rem;
          max-width: 1500px;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {
          background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
          border-right: none;
        }
        section[data-testid="stSidebar"] * {
          color: #e2e8f0 !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
          color: #f1f5f9 !important;
          font-size: 1rem !important;
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }
        section[data-testid="stSidebar"] input[type="password"] {
          background: rgba(255,255,255,0.07) !important;
          border: 1px solid rgba(255,255,255,0.15) !important;
          color: #f1f5f9 !important;
          border-radius: 8px !important;
        }
        section[data-testid="stSidebar"] label {
          color: #94a3b8 !important;
          font-size: 0.78rem !important;
          font-weight: 600 !important;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button {
          background: linear-gradient(135deg, #0d9488, #0369a1) !important;
          border: none !important;
          color: white !important;
          font-weight: 700 !important;
          border-radius: 8px !important;
          padding: 10px 0 !important;
          font-size: 0.88rem !important;
          letter-spacing: 0.03em;
          box-shadow: 0 4px 14px rgba(13,148,136,0.35);
          transition: all 0.2s ease;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
          box-shadow: 0 6px 20px rgba(13,148,136,0.5);
          transform: translateY(-1px);
        }

        /* ── Hero Banner ── */
        .m7-hero {
          background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f4c75 100%);
          border-radius: 12px;
          padding: 22px 28px;
          margin-bottom: 18px;
          position: relative;
          overflow: hidden;
          box-shadow: 0 10px 40px rgba(15,23,42,0.2);
        }
        .m7-hero::before {
          content: '';
          position: absolute;
          top: -40px; right: -40px;
          width: 200px; height: 200px;
          background: radial-gradient(circle, rgba(13,148,136,0.25) 0%, transparent 70%);
          border-radius: 50%;
        }
        .m7-hero::after {
          content: '';
          position: absolute;
          bottom: -30px; left: 30%;
          width: 160px; height: 160px;
          background: radial-gradient(circle, rgba(37,99,235,0.2) 0%, transparent 70%);
          border-radius: 50%;
        }
        .m7-hero h1 {
          font-size: 1.85rem;
          font-weight: 800;
          margin: 0 0 6px;
          color: #f1f5f9 !important;
          letter-spacing: -0.02em;
          position: relative;
          z-index: 1;
        }
        .m7-hero p {
          color: #94a3b8 !important;
          margin: 0;
          font-size: 0.92rem;
          position: relative;
          z-index: 1;
        }
        .m7-hero .badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(13,148,136,0.25);
          border: 1px solid rgba(13,148,136,0.4);
          color: #5eead4 !important;
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          padding: 3px 10px;
          border-radius: 20px;
          margin-bottom: 10px;
        }
        .m7-hero .badge::before {
          content: '';
          width: 6px; height: 6px;
          background: #2dd4bf;
          border-radius: 50%;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }

        /* ── KPI Cards ── */
        .m7-card {
          border: 1px solid var(--m7-line);
          background: var(--m7-panel);
          border-radius: 12px;
          padding: 18px 20px;
          min-height: 108px;
          box-shadow: 0 2px 12px rgba(15,23,42,0.06);
          transition: box-shadow 0.2s, transform 0.2s;
          position: relative;
          overflow: hidden;
        }
        .m7-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 3px;
          background: linear-gradient(90deg, var(--m7-teal), var(--m7-blue));
          border-radius: 12px 12px 0 0;
        }
        .m7-card:hover {
          box-shadow: 0 8px 28px rgba(15,23,42,0.11);
          transform: translateY(-2px);
        }
        .m7-card span {
          color: var(--m7-muted);
          font-size: 0.74rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }
        .m7-card strong {
          display: block;
          color: var(--m7-ink);
          font-size: 2rem;
          font-weight: 800;
          line-height: 1.1;
          margin-top: 8px;
          letter-spacing: -0.03em;
        }
        .m7-card small {
          display: block;
          color: var(--m7-muted);
          margin-top: 5px;
          font-size: 0.78rem;
        }

        /* ── Sections ── */
        .m7-section {
          border: 1px solid var(--m7-line);
          border-radius: 12px;
          background: #ffffff;
          padding: 18px 20px;
          margin-bottom: 14px;
          box-shadow: 0 2px 8px rgba(15,23,42,0.04);
        }
        .m7-section h3 {
          font-size: 0.88rem !important;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.07em;
          color: var(--m7-muted) !important;
          margin: 0 0 14px;
          padding-bottom: 10px;
          border-bottom: 1px solid var(--m7-line);
        }

        /* ── Rank List ── */
        .m7-rank {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 9px 0;
          border-bottom: 1px solid #f1f5f9;
        }
        .m7-rank:last-child { border-bottom: 0; }
        .m7-rank span {
          color: var(--m7-ink);
          font-size: 0.85rem;
          font-weight: 500;
          overflow-wrap: anywhere;
        }
        .m7-rank b {
          background: linear-gradient(135deg, #0d9488, #0369a1);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          font-weight: 700;
          white-space: nowrap;
          font-size: 0.9rem;
        }

        /* ── Metric Cards ── */
        div[data-testid="stMetric"] {
          border: 1px solid var(--m7-line);
          border-radius: 12px;
          padding: 14px 16px;
          background: #ffffff;
          box-shadow: 0 2px 8px rgba(15,23,42,0.04);
          transition: box-shadow 0.2s;
        }
        div[data-testid="stMetric"]:hover {
          box-shadow: 0 6px 20px rgba(15,23,42,0.09);
        }

        /* ── Buttons ── */
        div[data-testid="stButton"] button,
        div[data-testid="stFormSubmitButton"] button {
          border-radius: 8px !important;
          border: none !important;
          background: linear-gradient(135deg, #0d9488, #0f766e) !important;
          color: white !important;
          font-weight: 700 !important;
          font-size: 0.88rem !important;
          letter-spacing: 0.02em;
          box-shadow: 0 4px 14px rgba(13,148,136,0.3) !important;
          transition: all 0.2s ease !important;
        }
        div[data-testid="stButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
          background: linear-gradient(135deg, #0f766e, #0c5c56) !important;
          box-shadow: 0 6px 20px rgba(13,148,136,0.45) !important;
          transform: translateY(-1px);
        }

        /* ── Section Headers ── */
        h3 { color: var(--m7-ink); letter-spacing: -0.01em; }

        /* ── Dividers ── */
        hr { border-color: var(--m7-line); margin: 1.2rem 0; }

        /* ── Info/Success boxes ── */
        div[data-testid="stAlert"] {
          border-radius: 10px !important;
          border-left-width: 4px !important;
        }

        /* ── Forms ── */
        div[data-testid="stForm"] {
          border: 1px solid var(--m7-line);
          border-radius: 12px;
          padding: 16px;
          background: #fafbfc;
          box-shadow: 0 2px 8px rgba(15,23,42,0.04);
        }

        /* ── Model Readout section header ── */
        .model-readout-header {
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.09em;
          color: var(--m7-muted);
          margin-bottom: 4px;
        }
        .model-readout-sub {
          font-size: 0.72rem;
          color: #94a3b8;
          margin-bottom: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def html_escape(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "--"


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "--"


@st.cache_data(show_spinner=False)
def cached_overview() -> dict:
    return m7.to_jsonable(m7.build_overview())


def card(label: str, value: str, detail: str = "") -> None:
    st.markdown(
        f"""
        <div class="m7-card">
          <span>{html_escape(label)}</span>
          <strong>{html_escape(value)}</strong>
          <small>{html_escape(detail)}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rank_list(rows: list[dict], label_key: str, value_key: str, digits: int | None = None) -> None:
    if not rows:
        st.caption("No data available.")
        return
    html = []
    for row in rows:
        value = row.get(value_key)
        if digits is not None:
            value = fmt(value, digits)
        html.append(
            f"""
            <div class="m7-rank">
              <span>{html_escape(row.get(label_key, "Unknown"))}</span>
              <b>{html_escape(value)}</b>
            </div>
            """
        )
    st.markdown("".join(html), unsafe_allow_html=True)


def build_map_html(mappls_key: str, overview: dict, prediction_result: dict | None) -> str:
    payload = {
        "corridorSegments": overview.get("corridor_segments") or [],
        "prediction": prediction_result,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    key_json = json.dumps(mappls_key)
    # cache-bust so iframe always reloads fresh HTML after a prediction
    import time as _time
    ts = int(_time.time() * 1000)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  #m7-map-wrap {{
    position: relative;
    height: 100vh;
    background: #e8eef5;
    font-family: Inter, Segoe UI, Arial, sans-serif;
  }}
  #m7-map {{ position: absolute; inset: 0; }}
  /* Hide OpenStreetMap attribution — MapMyIndia/Mappls only */
  .mappls-ctrl-attrib,
  .mapboxgl-ctrl-attrib,
  [class*="attribution"] a[href*="openstreetmap"],
  [class*="attribution"] span:has(a[href*="openstreetmap"]) {{
    display: none !important;
  }}
  /* Also target text nodes inside attribution bar that say OpenStreetMap */
  .mappls-ctrl-attrib-inner,
  .mapboxgl-ctrl-attrib-inner {{
    font-size: 10px;
  }}
  .legend, #m7-map-status {{
    position: absolute;
    z-index: 1000;
    background: rgba(255,255,255,0.97);
    border: 1px solid rgba(15,23,42,0.10);
    box-shadow: 0 4px 20px rgba(15,23,42,0.15);
    border-radius: 10px;
    font-family: Inter, Segoe UI, Arial, sans-serif;
  }}
  .legend {{
    left: 14px; bottom: 40px;
    display: flex; gap: 16px; align-items: center;
    padding: 10px 14px;
    font-size: 12px; font-weight: 700; color: #0f172a;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  #m7-map-status {{
    top: 14px; left: 14px;
    padding: 8px 12px;
    font-size: 12px; color: #334155; max-width: 420px;
  }}
  .dot {{
    width: 12px; height: 12px; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
  }}
  .dot-incident {{ background: #dc2626; box-shadow: 0 0 8px rgba(220,38,38,0.7); }}
  .line-swatch {{
    width: 28px; height: 4px; border-radius: 3px; flex-shrink: 0;
  }}
  .congestion-swatch {{ background: #dc2626; }}
  .diversion-swatch {{ background: #1d4ed8; }}
</style>
</head>
<body>
<div id="m7-map-wrap">
  <div id="m7-map"></div>
  <div id="m7-map-status">Loading MapMyIndia/Mappls SDK…</div>
  <div class="legend">
    <div class="legend-item"><span class="dot dot-incident"></span>Incident</div>
    <div class="legend-item"><span class="line-swatch congestion-swatch"></span>Congestion Road</div>
    <div class="legend-item"><span class="line-swatch diversion-swatch"></span>Diversion Route</div>
  </div>
</div>
<script>
  /* ts={ts} — cache-bust */
  const mapplsKey = {key_json};
  const dashboardData = {payload_json};

  function setStatus(text, color) {{
    const node = document.getElementById("m7-map-status");
    if (node) {{ node.textContent = text; if (color) node.style.color = color; }}
  }}

  function sdkUrls() {{
    return [
      `https://apis.mappls.com/advancedmaps/api/${{mapplsKey}}/map_sdk?layer=vector&v=3.0&callback=__m7MapReady`,
      `https://apis.mappls.com/advancedmaps/api/${{mapplsKey}}/map_sdk?layer=vector&v=2.0&callback=__m7MapReady`,
      `https://apis.mappls.com/advancedmaps/api/${{mapplsKey}}/map_sdk?v=3.0&callback=__m7MapReady`,
    ];
  }}

  function loadScript(src) {{
    return new Promise((res, rej) => {{
      const s = document.createElement("script");
      s.src = src; s.async = true; s.referrerPolicy = "origin";
      s.onload = res;
      s.onerror = () => rej(new Error("Script failed: " + src.replace(mapplsKey, "****")));
      document.head.appendChild(s);
      setTimeout(() => rej(new Error("Script timeout: " + src.replace(mapplsKey, "****"))), 18000);
    }});
  }}

  async function loadMappls() {{
    if (window.mappls && window.mappls.Map) return window.mappls;
    const errors = [];
    for (const src of sdkUrls()) {{
      try {{
        window.__m7MapReady = () => window.mappls;
        await loadScript(src);
        if (window.mappls) return window.mappls;
        errors.push("Loaded but no window.mappls");
      }} catch (e) {{ errors.push(e.message); }}
    }}
    throw new Error("Mappls SDK failed — check allowed domains. " + errors.join(" | "));
  }}

  async function waitReady(api) {{
    const end = Date.now() + 14000;
    while (Date.now() < end) {{
      if (api && api.Map && api.Marker && api.Polyline) return api;
      await new Promise(r => setTimeout(r, 120));
    }}
    throw new Error("Mappls SDK loaded but map classes unavailable.");
  }}

  /* normalise a point that may be [lat,lng] array or {{lat,lng}} object */
  function toLatLng(p) {{
    if (Array.isArray(p)) return {{ lat: Number(p[0]), lng: Number(p[1]) }};
    return {{ lat: Number(p.lat), lng: Number(p.lng) }};
  }}

  function placeMarker(api, map, lat, lng, popup, color) {{
    const opts = {{
      map,
      position: {{ lat, lng }},
      popupHtml: popup || "",
    }};
    /* tint the default pin if the API supports it */
    if (color) opts.icon = {{ url: `https://maps.google.com/mapfiles/ms/icons/${{color}}-dot.png` }};
    return new api.Marker(opts);
  }}

  function drawPolyline(api, map, rawPath, color, weight, opacity, popup) {{
    const path = rawPath.map(toLatLng);
    if (path.length < 2) return null;
    return new api.Polyline({{
      map,
      path,
      strokeColor: color,
      strokeWeight: weight,
      strokeOpacity: opacity,
      popupHtml: popup || "",
    }});
  }}

  function esc(v) {{
    return String(v ?? "").replace(/[&<>"']/g, c =>
      ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[c]));
  }}

  /* Remove OpenStreetMap attribution text from the DOM */
  function stripOSMAttribution() {{
    const selectors = [
      '[class*="attrib"] a[href*="openstreetmap"]',
      '[class*="attrib"] a[href*="osm.org"]',
    ];
    selectors.forEach(sel => {{
      document.querySelectorAll(sel).forEach(el => {{
        const parent = el.closest('[class*="attrib-inner"], [class*="attribution"]');
        if (parent) {{
          // Remove just the OSM part, not the whole attribution
          const txt = parent.innerHTML;
          parent.innerHTML = txt
            .replace(/[|·]\s*©?\s*<a[^>]*openstreetmap[^>]*>.*?<\/a>/gi, "")
            .replace(/<a[^>]*openstreetmap[^>]*>.*?<\/a>\s*[|·]?/gi, "")
            .replace(/OpenStreetMap contributors?/gi, "")
            .replace(/\|\s*\|/g, "|").replace(/^\s*\|\s*/,"").replace(/\s*\|\s*$/,"");
        }} else {{
          el.style.display = "none";
        }}
      }});
    }});
  }}

  async function draw() {{
    try {{
      setStatus("Loading map SDK…");
      const api = await waitReady(await loadMappls());

      /* ── default view: Bengaluru city centre ── */
      const map = new api.Map("m7-map", {{
        center: {{lat: 12.9716, lng: 77.5946}},
        zoom: 12,
        zoomControl: true,
      }});

      /* Strip OSM text from attribution bar once map tiles load */
      setTimeout(stripOSMAttribution, 2000);
      setTimeout(stripOSMAttribution, 5000);
      setTimeout(stripOSMAttribution, 10000);

      if (!dashboardData.prediction) {{
        setStatus("Bengaluru — enter an incident in the Forecast panel to visualise congestion impact.");
        return;
      }}

      /* ─────────── PREDICTION LAYERS ─────────── */
      const result      = dashboardData.prediction;
      const input       = result.prediction.input;
      const plan        = result.resource_plan;
      const cisData     = result.prediction.congestion_impact_score;
      const closureData = result.prediction.closure_prediction;

      const incLat = Number(input.latitude);
      const incLng = Number(input.longitude);

      /* Guard: if coords are not in India/Bengaluru area, force re-centre */
      const inBengaluru = incLat >= 12.75 && incLat <= 13.20 && incLng >= 77.38 && incLng <= 77.82;
      if (!inBengaluru) {{
        setStatus(`⚠️ Incident coordinates (${{incLat.toFixed(4)}}, ${{incLng.toFixed(4)}}) appear outside Bengaluru. Map centred on Bengaluru.`, "#f97316");
        map.setCenter({{lat: 12.9716, lng: 77.5946}});
        if (map.setZoom) map.setZoom(12);
        return;
      }}

      /* 1. Incident marker */
      const closurePct = (Number((closureData || {{}}).closure_probability || 0) * 100).toFixed(1);
      const cisVal     = Number((cisData || {{}}).cis_ml_based || 0).toFixed(2);

      const incPopup = `<div style="font-family:Inter,sans-serif;min-width:200px;padding:6px;">
         <div style="color:#dc2626;font-size:14px;font-weight:700;margin-bottom:6px;">🚨 Incident: ${{esc(input.event_cause)}}</div>
         <table style="font-size:12px;color:#374151;border-collapse:collapse;width:100%;">
           <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Priority</td><td><b>${{esc(input.priority)}}</b></td></tr>
           <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Closure Risk</td><td><b>${{closurePct}}%</b></td></tr>
           <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">CIS Score</td><td><b>${{cisVal}}</b></td></tr>
           <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Tier</td><td><b>${{esc(plan.final_tier)}}</b></td></tr>
           <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Officers</td><td><b>${{plan.officer_count || 0}}</b></td></tr>
         </table>
       </div>`;

      placeMarker(api, map, incLat, incLng, incPopup, "red");

      /* Centre immediately on incident — DO NOT wait for allPoints bounding box */
      map.setCenter({{lat: incLat, lng: incLng}});
      if (map.setZoom) map.setZoom(14);

      /* allPoints collects ONLY local geometry (diversion polylines near incident).
         Full corridor endpoints are NOT included — they span all of Bengaluru and
         would drag the computed centroid far from the incident. */
      const allPoints = [[incLat, incLng]];

      /* 2. Congestion road — matched corridor in RED, popup shows CIS by hour */
      const corridorName = (result.prediction.resolved_location || {{}}).corridor_final;
      const corridorSeg  = (dashboardData.corridorSegments || []).find(s => s.corridor === corridorName);

      /* Grab hourly CIS from diversion_routes for the affected corridor */
      const affectedDivInfo = (result.diversion_routes || []).find(r => r.corridor === corridorName);
      const hourlyCIS = (affectedDivInfo || {{}}).hourly_cis || {{}};
      const avgCIS    = (affectedDivInfo || {{}}).avg_cis;

      /* Build hourly CIS table rows */
      let hourlyRows = "";
      const hourKeys = Object.keys(hourlyCIS).map(Number).sort((a,b) => a-b);
      if (hourKeys.length) {{
        hourlyRows += `<tr style="background:#f1f5f9;"><td colspan="4" style="padding:4px 6px;font-size:11px;font-weight:700;color:#475569;">Avg Congestion Score by Hour</td></tr>`;
        for (let i = 0; i < hourKeys.length; i += 4) {{
          const slice = hourKeys.slice(i, i+4);
          hourlyRows += `<tr>` + slice.map(h => {{
            const v = hourlyCIS[h];
            const intensity = Math.min(1, v / 3);
            const bg = `rgba(220,38,38,${{(intensity * 0.4).toFixed(2)}})`;
            return `<td style="padding:3px 5px;text-align:center;font-size:11px;background:${{bg}};border-radius:3px;">
              <div style="font-weight:700;color:#0f172a;">${{h.toString().padStart(2,"0")}}</div>
              <div style="color:#dc2626;">${{v.toFixed(2)}}</div>
            </td>`;
          }}).join("") + `</tr>`;
        }}
      }}

      /* 2. Draw congestion road in RED using API-provided polyline */
      {{
        const congestionPopup = `<div style="font-family:Inter,sans-serif;min-width:260px;padding:6px;">
          <div style="color:#dc2626;font-size:13px;font-weight:700;margin-bottom:6px;">🔴 Congestion: ${{esc(corridorName || 'Incident Road')}}</div>
          <table style="font-size:12px;color:#374151;border-collapse:collapse;width:100%;">
            <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">CIS Score (this event)</td><td><b>${{cisVal}}</b></td></tr>
            ${{avgCIS !== undefined ? `<tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Avg CIS (historical)</td><td><b>${{Number(avgCIS).toFixed(3)}}</b></td></tr>` : ""}}
            <tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Closure risk</td><td><b>${{closurePct}}%</b></td></tr>
          </table>
          ${{hourlyRows ? `<table style="width:100%;border-collapse:collapse;margin-top:8px;">${{hourlyRows}}</table>` : ""}}
          <div style="font-size:10px;color:#94a3b8;margin-top:6px;">CIS = Congestion Impact Score (higher = worse congestion)</div>
        </div>`;

        const congestionPath = result.congestion_polyline;
        if (congestionPath && congestionPath.length >= 2) {{
          drawPolyline(api, map, congestionPath, "#dc2626", 7, 0.92, congestionPopup);
          congestionPath.forEach(p => allPoints.push(toLatLng(p)));
        }} else {{
          /* Fallback: short segment through incident */
          const fallback = [
            [incLat - 0.005, incLng - 0.005],
            [incLat, incLng],
            [incLat + 0.005, incLng + 0.005]
          ];
          drawPolyline(api, map, fallback, "#dc2626", 7, 0.92, congestionPopup);
          fallback.forEach(p => allPoints.push(toLatLng(p)));
        }}
      }}

      /* 3. Diversion routes in BLUE — proper bypass paths */
      const divRoutes = result.diversion_routes || [];
      const divColors = ["#1d4ed8", "#7c3aed", "#0891b2"];  // blue, purple, cyan
      divRoutes.forEach((route, idx) => {{
        const rawPath = route.polyline || [];
        if (rawPath.length < 2) return;
        const routeColor = divColors[idx % divColors.length];
        const routeWeight = idx === 0 ? 6 : 4;

        /* Build hourly CIS table for this diversion corridor */
        const dHourlyCIS = route.hourly_cis || {{}};
        let dHourlyRows = "";
        const dHourKeys = Object.keys(dHourlyCIS).map(Number).sort((a,b) => a-b);
        if (dHourKeys.length) {{
          dHourlyRows += `<tr style="background:#eff6ff;"><td colspan="4" style="padding:4px 6px;font-size:11px;font-weight:700;color:#1d4ed8;">Avg Congestion Score by Hour</td></tr>`;
          for (let i = 0; i < dHourKeys.length; i += 4) {{
            const slice = dHourKeys.slice(i, i+4);
            dHourlyRows += `<tr>` + slice.map(h => {{
              const v = dHourlyCIS[h];
              const intensity = Math.min(1, v / 3);
              const bg = `rgba(29,78,216,${{(intensity * 0.35).toFixed(2)}})`;
              return `<td style="padding:3px 5px;text-align:center;font-size:11px;background:${{bg}};border-radius:3px;">
                <div style="font-weight:700;color:#0f172a;">${{h.toString().padStart(2,"0")}}</div>
                <div style="color:#1d4ed8;">${{v.toFixed(2)}}</div>
              </td>`;
            }}).join("") + `</tr>`;
          }}
        }}

        const dPopup = `<div style="font-family:Inter,sans-serif;min-width:260px;padding:6px;">
          <div style="color:${{routeColor}};font-size:13px;font-weight:700;margin-bottom:4px;">↪ ${{esc(route.name)}}</div>
          <div style="font-size:11px;color:#64748b;margin-bottom:6px;">${{esc(route.description || "")}}</div>
          <table style="font-size:12px;color:#374151;border-collapse:collapse;width:100%;">
            ${{route.avg_cis !== undefined ? `<tr><td style="padding:2px 8px 2px 0;color:#6b7280;">Avg CIS (historical)</td><td><b>${{Number(route.avg_cis).toFixed(3)}}</b></td></tr>` : ""}}
          </table>
          ${{dHourlyRows ? `<table style="width:100%;border-collapse:collapse;margin-top:8px;">${{dHourlyRows}}</table>` : ""}}
          <div style="font-size:10px;color:#94a3b8;margin-top:6px;">CIS = Congestion Impact Score (higher = worse congestion)</div>
        </div>`;

        drawPolyline(api, map, rawPath, routeColor, routeWeight, 0.88, dPopup);
        rawPath.forEach(p => allPoints.push(toLatLng(p)));
      }});

      /* 4. Final zoom — centre is already on incident (set above).
            Just tighten zoom so all local diversion arcs are visible.
            allPoints only has local geometry (±~0.015° from incident),
            so the bounding box will always be small and stay in Bengaluru. */
      {{
        const lats = allPoints.map(p => Number(Array.isArray(p) ? p[0] : p.lat)).filter(Number.isFinite);
        const lngs = allPoints.map(p => Number(Array.isArray(p) ? p[1] : p.lng)).filter(Number.isFinite);
        if (lats.length > 1) {{
          const latSpread = Math.max(...lats) - Math.min(...lats);
          const lngSpread = Math.max(...lngs) - Math.min(...lngs);
          const spread = Math.max(latSpread, lngSpread);
          /* zoom 14 fits ~0.015° (~1.5 km), zoom 13 fits ~0.03° (~3 km) */
          let zoom = 14;
          if (spread > 0.06) zoom = 12;
          else if (spread > 0.03) zoom = 13;
          else if (spread > 0.012) zoom = 14;
          else zoom = 15;
          if (map.setZoom) map.setZoom(zoom);
        }}
      }}

      const layerSummary = [
        "📍 Incident pinned",
        corridorSeg ? "🔴 Congestion road highlighted" : null,
        divRoutes.length ? `🔵 ${{divRoutes.length}} diversion route(s) — click lines for CIS details` : null,
      ].filter(Boolean).join("  •  ");
      setStatus(layerSummary, "#0f172a");

    }} catch (err) {{
      console.error(err);
      setStatus("Map error: " + (err && err.message ? err.message : String(err)), "#dc2626");
    }}
  }}

  draw();
</script>
</body>
</html>"""


def render_map(mappls_key: str, overview: dict, prediction_result: dict | None) -> None:
    if not mappls_key:
        st.markdown(
            """
            <div style="height: 610px; display: flex; align-items: center; justify-content: center; text-align: center;
                 background: linear-gradient(135deg, #f0f9f8 0%, #e8eef5 100%);
                 border: 1px dashed #94a3b8; border-radius: 12px;">
              <div>
                <div style="font-size: 2.5rem; margin-bottom: 12px;">🗺️</div>
                <h3 style="color: #0f172a; margin: 0 0 8px; font-size: 1.1rem;">Enter a MapMyIndia / Mappls Web SDK key</h3>
                <p style="color: #64748b; margin: 0; font-size: 0.85rem;">Submit your key in the sidebar to load the Bengaluru operations map.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    import time as _time
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    map_file = static_dir / "map.html"
    map_file.write_text(build_map_html(mappls_key, overview, prediction_result), encoding="utf-8")
    # cache-bust so browser always fetches fresh HTML after a new prediction
    ts = int(_time.time() * 1000) if prediction_result else 0
    components.iframe(f"app/static/map.html?ts={ts}", height=640, scrolling=False)
    

# Known Bengaluru road name → (lat, lng, address) mapping
ROAD_LOCATIONS: dict[str, tuple[float, float, str]] = {
    "Mysore Road":            (12.9421, 77.5149, "Mysore Road, Bengaluru"),
    "Magadi Road":            (12.9764, 77.5473, "Magadi Road, Bengaluru"),
    "Outer Ring Road (ORR)":  (12.9352, 77.6854, "Outer Ring Road, Bengaluru"),
    "Hosur Road":             (12.8985, 77.6270, "Hosur Road, Bengaluru"),
    "Bellary Road (NH 44)":   (13.0543, 77.5791, "Bellary Road, Bengaluru"),
    "Old Madras Road":        (12.9960, 77.6540, "Old Madras Road, Bengaluru"),
    "Tumkur Road (NH 48)":    (13.0298, 77.5085, "Tumkur Road, Bengaluru"),
    "Bannerghatta Road":      (12.8721, 77.5965, "Bannerghatta Road, Bengaluru"),
    "Sarjapur Road":          (12.8997, 77.6874, "Sarjapur Road, Bengaluru"),
    "Whitefield Main Road":   (12.9698, 77.7499, "Whitefield, Bengaluru"),
    "NICE Road":              (12.8901, 77.5500, "NICE Road, Bengaluru"),
    "Ballari Road":           (13.0282, 77.5913, "Ballari Road, Bengaluru"),
    "KR Puram Bridge Road":   (13.0017, 77.6952, "KR Puram, Bengaluru"),
    "Hennur Road":            (13.0366, 77.6296, "Hennur Road, Bengaluru"),
    "Electronic City Flyover": (12.8445, 77.6629, "Electronic City, Bengaluru"),
}

# Approximate bounding box for Bengaluru road network validation
BENGALURU_LAT_MIN, BENGALURU_LAT_MAX = 12.75, 13.20
BENGALURU_LNG_MIN, BENGALURU_LNG_MAX = 77.38, 77.82


import math as _math

# Known non-road zones (lat, lng, radius_degrees, display_name, place_type)
_NON_ROAD_ZONES = [
    (12.9738, 77.5906, 0.0035, "Cubbon Park",              "park"),
    (12.9340, 77.5840, 0.0060, "Lalbagh Botanical Garden", "botanical garden"),
    (12.9616, 77.6417, 0.0080, "Ulsoor Lake",              "lake"),
    (13.0475, 77.5798, 0.0030, "Sankey Tank",              "lake / park"),
    (12.9088, 77.5633, 0.0050, "Bannerghatta National Park entrance", "national park"),
    (13.1986, 77.7066, 0.0200, "Kempegowda International Airport", "airport"),
    (12.9772, 77.5718, 0.0015, "KSR Bengaluru City Railway Station", "railway station"),
    (12.9784, 77.5993, 0.0020, "M. Chinnaswamy Stadium",  "stadium"),
    (12.9500, 77.5975, 0.0015, "Kanteerava Stadium",       "stadium"),
    (12.9308, 77.6338, 0.0040, "Bellandur Lake",           "lake"),
    (12.9076, 77.6600, 0.0025, "Varthur Lake",             "lake"),
]


def classify_non_road_location(lat: float, lng: float):
    """Return a human-readable description if coordinates are a known non-road zone, else None."""
    if not (BENGALURU_LAT_MIN <= lat <= BENGALURU_LAT_MAX and
            BENGALURU_LNG_MIN <= lng <= BENGALURU_LNG_MAX):
        return "outside Bengaluru city limits"
    for zone_lat, zone_lng, radius, name, ptype in _NON_ROAD_ZONES:
        dist = _math.hypot(lat - zone_lat, lng - zone_lng)
        if dist <= radius:
            return f"{name} ({ptype})"
    return None  # location is plausibly on a road


def event_payload(causes: list[str]) -> dict | None:
    # ── Input mode toggle ──────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:0.78rem;font-weight:700;color:#64748b;text-transform:uppercase;"
        "letter-spacing:0.07em;margin-bottom:6px;'>📍 Location Input Mode</div>",
        unsafe_allow_html=True,
    )
    col_tog1, col_tog2 = st.columns([1, 2])
    with col_tog1:
        use_road_dropdown = st.toggle("Use Road Name", value=False, help="Switch between entering coordinates manually or picking a road from the list")

    with st.form("live_event_form"):
        # ── Location section ───────────────────────────────────────────────────
        if use_road_dropdown:
            road_input = st.text_input("Enter Road Name", "Mysore Road, Bengaluru")
            st.markdown(
                f"<div style='font-size:0.8rem;color:#64748b;margin-top:4px;margin-bottom:8px;'>"
                f"📌 Coordinates will be fetched dynamically via API.</div>",
                unsafe_allow_html=True,
            )
            latitude = 0.0
            longitude = 0.0
            addr_default = road_input
        else:
            c_loc1, c_loc2 = st.columns(2)
            with c_loc1:
                latitude = st.number_input("Latitude", value=12.9716, step=0.000001, format="%.6f",
                                           help="Must be within Bengaluru road network bounds (12.75–13.20)")
            with c_loc2:
                longitude = st.number_input("Longitude", value=77.5573, step=0.000001, format="%.6f",
                                            help="Must be within Bengaluru road network bounds (77.38–77.82)")
            addr_default = "Mysore Road, Bengaluru"

        # ── Validate location is within road network bounds ────────────────────
        location_valid = (
            BENGALURU_LAT_MIN <= latitude <= BENGALURU_LAT_MAX and
            BENGALURU_LNG_MIN <= longitude <= BENGALURU_LNG_MAX
        )

        # ── Other fields ───────────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        with c1:
            cause = st.selectbox("Cause", causes, index=0)
            priority = st.selectbox("Priority", ["LOW", "HIGH"], index=0)
        with c2:
            event_type = st.selectbox("Event Type", ["unplanned", "planned"], index=0)
            now = datetime.now()
            event_date = st.date_input("Event Date", value=now.date())
            event_time = st.time_input("Event Time", value=now.time().replace(microsecond=0))

        description = st.text_area("Description", value="lorry breakdown on left lane, slow traffic", height=88)
        address = st.text_input("Address", value=addr_default if use_road_dropdown else "Mysore Road, Bengaluru")
        r1, r2, r3 = st.columns([1, 1, 2])
        with r1:
            was_escalated = st.checkbox("Escalated", value=False)
        with r2:
            authenticated = st.checkbox("Authenticated", value=True)
        with r3:
            submitted = st.form_submit_button("Predict", use_container_width=True)

    if not submitted:
        return None

    # ── Mandatory field validation ─────────────────────────────────────────────
    validation_errors = []

    if not cause:
        validation_errors.append("**Cause** is required.")
    if not priority:
        validation_errors.append("**Priority** is required.")
    if not event_type:
        validation_errors.append("**Event Type** is required.")
    if event_date is None:
        validation_errors.append("**Event Date** is required.")
    if event_time is None:
        validation_errors.append("**Event Time** is required.")
    if not use_road_dropdown:
        # For manual coordinate entry, check they're not still at exact 0,0 default
        if latitude == 0.0 and longitude == 0.0:
            validation_errors.append("**Latitude / Longitude** must not both be zero.")
    if not description or not description.strip():
        validation_errors.append("**Description** cannot be empty.")

    if validation_errors:
        st.error(
            "⚠️ **Please fill in all required fields before predicting:**\n\n"
            + "\n".join(f"- {e}" for e in validation_errors)
        )
        return None

    # ── Location validation gate ───────────────────────────────────────────────
    if not use_road_dropdown:
        place_issue = classify_non_road_location(latitude, longitude)
        if place_issue:
            st.error(
                f"⚠️ **Invalid location.** The coordinates ({latitude:.6f}, {longitude:.6f}) "
                f"appear to be **{place_issue}**, not a road. "
                f"Road incident predictions only work for actual road locations. "
                f"Please enter coordinates on a road, or use the **Road Name** toggle to pick a known road."
            )
            return None

    return {
        "latitude": latitude,
        "longitude": longitude,
        "event_cause": cause,
        "event_type": event_type,
        "priority": priority,
        "timestamp": datetime.combine(event_date, event_time).isoformat(),
        "was_escalated": was_escalated,
        "authenticated": authenticated,
        "description": description,
        "address": address,
        "use_geocoding": use_road_dropdown,
    }


def render_prediction(result: dict | None) -> None:
    if not result:
        st.markdown(
            """
            <div style="border:1.5px dashed #e2e8f0;border-radius:12px;padding:28px;text-align:center;background:#fafbfc;">
              <div style="font-size:2rem;margin-bottom:8px;">📡</div>
              <div style="font-size:0.95rem;font-weight:600;color:#334155;">No forecast yet</div>
              <div style="font-size:0.82rem;color:#94a3b8;margin-top:4px;">Submit an incident in the Forecast panel above to generate closure risk, CIS, and resource recommendations.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    prediction = result["prediction"]
    plan = result["resource_plan"]
    closure = prediction["closure_prediction"]
    cis = prediction["congestion_impact_score"]
    loc = prediction["resolved_location"]

    closure_pct = pct(closure.get("closure_probability"))
    cis_val = fmt(cis.get("cis_ml_based"), 2)
    tier = plan.get("final_tier", "--")
    officers = plan.get("officer_count", "--")
    barricades = plan.get("barricade_count", "--")
    diversion_pri = plan.get("diversion_priority", "--")
    corridor = loc.get("corridor_final", "--")
    confidence = fmt(loc.get("corridor_confidence"), 3)
    agreement_bool = loc.get("corridor_agreement")
    agreement = "Yes" if agreement_bool else "No"
    agreement_color = "#16a34a" if agreement_bool else "#dc2626"
    police = loc.get("police_station", "--")
    threshold = fmt(closure.get("decision_threshold"), 3)
    text_avail = closure.get("text_available")
    text_used = "Yes" if text_avail else "No"
    text_color = "#16a34a" if text_avail else "#64748b"
    rationale = plan.get("rationale", "")

    # Make the rationale more human-readable
    def humanize_rationale(raw: str) -> str:
        if not raw:
            return ""
        # Try to build a friendlier version based on common keywords
        r = raw.strip()
        # Replace technical jargon patterns
        import re
        r = re.sub(r"bottom quartile of the ML-predicted CIS distribution", "low end of the congestion severity scale", r, flags=re.IGNORECASE)
        r = re.sub(r"historical closure rate in this band is ~?([\d.]+)%", r"similar incidents in the past have led to road closure only about \1% of the time", r, flags=re.IGNORECASE)
        r = re.sub(r"Single officer for traffic guidance/logging", "One officer is enough — mainly for guiding traffic and logging the incident", r, flags=re.IGNORECASE)
        r = re.sub(r"no physical barricading by default", "no physical barricades are needed at this stage", r, flags=re.IGNORECASE)
        r = re.sub(r"Minor incident,?\s*", "This is a minor incident. ", r, flags=re.IGNORECASE)
        return r

    friendly_rationale = humanize_rationale(rationale)

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">

          <!-- Closure block (no CIS here) -->
          <div style="background:linear-gradient(135deg,#fff1f2,#fff5f5);border:1.5px solid #fecaca;border-radius:12px;padding:18px 20px;">
            <div style="font-size:0.7rem;font-weight:800;text-transform:uppercase;letter-spacing:0.09em;color:#dc2626;margin-bottom:12px;">🔴 Closure &amp; Congestion</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #fecaca;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">Closure Risk</div>
                <div style="font-size:1.5rem;font-weight:800;color:#dc2626;">{closure_pct}</div>
              </div>
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #fecaca;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">Tier</div>
                <div style="font-size:1.5rem;font-weight:800;color:#dc2626;">{html_escape(str(tier))}</div>
              </div>
            </div>
          </div>

          <!-- Resource plan block (CIS Score moved here) -->
          <div style="background:linear-gradient(135deg,#f0f9ff,#eff6ff);border:1.5px solid #bfdbfe;border-radius:12px;padding:18px 20px;">
            <div style="font-size:0.7rem;font-weight:800;text-transform:uppercase;letter-spacing:0.09em;color:#2563eb;margin-bottom:12px;">🔵 Resource Plan</div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #bfdbfe;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">CIS Score</div>
                <div style="font-size:1.5rem;font-weight:800;color:#2563eb;">{cis_val}</div>
              </div>
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #bfdbfe;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">Officers</div>
                <div style="font-size:1.5rem;font-weight:800;color:#2563eb;">{html_escape(str(officers))}</div>
              </div>
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #bfdbfe;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">Barricades</div>
                <div style="font-size:1.5rem;font-weight:800;color:#2563eb;">{html_escape(str(barricades))}</div>
              </div>
              <div style="background:white;border-radius:8px;padding:12px;text-align:center;border:1px solid #bfdbfe;">
                <div style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;margin-bottom:4px;">Diversion</div>
                <div style="font-size:1.5rem;font-weight:800;color:#2563eb;">{html_escape(str(diversion_pri))}</div>
              </div>
            </div>
          </div>

        </div>

        <!-- Location resolution -->
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;margin-bottom:10px;">
          <div style="font-size:0.7rem;font-weight:800;text-transform:uppercase;letter-spacing:0.09em;color:#64748b;margin-bottom:12px;">📍 Location Resolution</div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-size:0.82rem;">
            <div><span style="color:#94a3b8;font-weight:600;">Corridor</span><br/><b style="color:#0f172a;">{html_escape(str(corridor))}</b></div>
            <div><span style="color:#94a3b8;font-weight:600;">Confidence</span><br/><b style="color:#0f172a;">{html_escape(str(confidence))}</b></div>
            <div><span style="color:#94a3b8;font-weight:600;">RF/KNN Agreement</span><br/><b style="color:{agreement_color};">{agreement}</b></div>
            <div><span style="color:#94a3b8;font-weight:600;">Police Station</span><br/><b style="color:#0f172a;">{html_escape(str(police))}</b></div>
            <div><span style="color:#94a3b8;font-weight:600;">Closure Threshold</span><br/><b style="color:#0f172a;">{html_escape(str(threshold))}</b></div>
            <div><span style="color:#94a3b8;font-weight:600;">Text Signal Used</span><br/><b style="color:{text_color};">{text_used}</b></div>
          </div>
          {f'<div style="margin-top:12px;padding-top:10px;border-top:1px solid #e2e8f0;font-size:0.82rem;color:#334155;background:#f1f5f9;border-radius:8px;padding:12px 14px;line-height:1.6;">💡 <b>Summary:</b> {html_escape(friendly_rationale)}</div>' if friendly_rationale else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    css()

    st.markdown(
        """
        <div class="m7-hero">
          <div class="badge">🚦 Live System</div>
          <h1>Event-Driven Congestion Dashboard</h1>
          <p>Forecast road closure event-related traffic impact and recommend optimal manpower, barricading, and diversion plans.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div style="padding: 8px 0 16px;"><span style="font-size:1.3rem;">🚦</span>'
            '<span style="font-size:0.95rem;font-weight:800;color:#f1f5f9;margin-left:8px;">Congestion Dashboard</span></div>',
            unsafe_allow_html=True,
        )
        st.header("Runtime Setup")
        mappls_key = st.text_input(
            "MapMyIndia / Mappls Web SDK key",
            value=os.environ.get("M7_MAPPLS_SDK_KEY") or os.environ.get("MAPPLS_API_KEY") or "",
            type="password",
            help="The key is entered at runtime and is not saved into source code.",
        ).strip()
        if st.button("Submit Key", use_container_width=True):
            cached_overview.clear()
            st.rerun()
        st.markdown("---")

    try:
        overview = cached_overview()
    except Exception as exc:
        st.error(f"Could not load pipeline artifacts: {exc}")
        st.stop()

    causes = sorted({row.get("cause") for row in overview.get("top_causes", []) if row.get("cause")} | set(CAUSES))
    if "prediction_result" not in st.session_state:
        st.session_state.prediction_result = None

    s = overview.get("summary", {})
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        card("Historical Incidents", f"{int(s.get('incidents') or 0):,}", "Clean incident rows")
    with k2:
        card("Closure Rate", pct(s.get("closure_rate")), "Road closure share")
    with k3:
        card("Corridors", str(s.get("corridors") or "--"), "Resolved network coverage")
    with k4:
        card("Causes", str(s.get("causes") or "--"), "Incident categories")

    map_col, side_col = st.columns([1.55, 1], gap="large")
    with map_col:
        render_map(mappls_key, overview, st.session_state.prediction_result)

    with side_col:
        st.markdown("### Forecast")
        event = event_payload(causes)
        if event:
            with st.spinner("Forecasting congestion impact and resource plan..."):
                try:
                    st.session_state.prediction_result = m7.to_jsonable(m7.predict_live_event(event, mappls_key=mappls_key))
                    st.success("✅ Forecast generated. Map updated with incident location and diversion routes.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Prediction failed: {exc}")

    st.markdown("### Forecast Prediction")
    render_prediction(st.session_state.prediction_result)

    lower_left, lower_mid, lower_right = st.columns(3)
    with lower_left:
        st.markdown('<div class="m7-section"><h3>Incident Hotspots</h3>', unsafe_allow_html=True)
        rank_list((overview.get("forecast_hotspots") or [])[:8], "corridor", "predicted_incidents", 1)
        st.markdown("</div>", unsafe_allow_html=True)
    with lower_mid:
        st.markdown('<div class="m7-section"><h3>Top Corridors</h3>', unsafe_allow_html=True)
        rank_list((overview.get("top_corridors") or [])[:8], "corridor", "count")
        st.markdown("</div>", unsafe_allow_html=True)
    with lower_right:
        st.markdown('<div class="m7-section"><h3>Top Causes</h3>', unsafe_allow_html=True)
        rank_list((overview.get("top_causes") or [])[:8], "cause", "count")
        st.markdown("</div>", unsafe_allow_html=True)

    metrics = overview.get("metrics", {})
    closure = metrics.get("closure", {})

    st.markdown("### Model Readout")

    roc_auc   = fmt(closure.get("roc_auc"), 3)
    precision = fmt(closure.get("precision"), 3)
    recall    = fmt(closure.get("recall"), 3)

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:4px;">

          <!-- Road Closure Model -->
          <div style="border-radius:14px;border:1.5px solid #d1fae5;background:linear-gradient(135deg,#f0fdf4 0%,#ecfdf5 100%);padding:20px 24px;box-shadow:0 2px 12px rgba(13,148,136,0.08);">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
              <span style="width:10px;height:10px;border-radius:50%;background:#0d9488;display:inline-block;box-shadow:0 0 6px rgba(13,148,136,0.5);"></span>
              <span style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.10em;color:#0d9488;">Road Closure Model</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #d1fae5;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">ROC-AUC</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{roc_auc}</div>
              </div>
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #d1fae5;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">Precision</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{precision}</div>
              </div>
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #d1fae5;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">Recall</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{recall}</div>
              </div>
            </div>
          </div>

          <!-- Resource Recommendation Model -->
          <div style="border-radius:14px;border:1.5px solid #dbeafe;background:linear-gradient(135deg,#eff6ff 0%,#eef2ff 100%);padding:20px 24px;box-shadow:0 2px 12px rgba(37,99,235,0.08);">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
              <span style="width:10px;height:10px;border-radius:50%;background:#2563eb;display:inline-block;box-shadow:0 0 6px rgba(37,99,235,0.5);"></span>
              <span style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.10em;color:#2563eb;">Resource Recommendation Model</span>
              <span style="font-size:0.65rem;color:#94a3b8;font-weight:600;">XGBoost CIS · n=1,605</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #dbeafe;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">MAE</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">0.444</div>
                <div style="font-size:0.67rem;color:#94a3b8;margin-top:3px;">on 0–10 scale</div>
              </div>
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #dbeafe;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">RMSE</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">0.926</div>
              </div>
              <div style="background:white;border-radius:10px;padding:14px 16px;border:1px solid #dbeafe;text-align:center;">
                <div style="font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-bottom:6px;">R²</div>
                <div style="font-size:1.7rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">0.893</div>
              </div>
            </div>
          </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
r"""
M7 - Dynamic dashboard server
=============================

Runs a no-extra-dependency dashboard API over your existing pipeline outputs.
It serves the frontend from ./web and exposes:

  GET  /api/config    Map SDK/runtime config
  GET  /api/overview  Historical incidents, forecasts, model metrics
  POST /api/predict   Live event -> M5 prediction -> M6 resource plan

Usage:
  set THEME2_PIPELINE_DIR=C:\Users\Hp\Downloads\flipkart-20260621T143502Z-3-001\flipkart
  set M7_MAPPLS_SDK_KEY=your_mappls_or_mapmyindia_web_sdk_key
  python m7_dashboard_server.py
"""

from __future__ import annotations

import json
import math
import os
import pickle
import sys
import traceback
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import joblib


HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
DEFAULT_PIPELINE_DIR = Path(r"/content/drive/MyDrive/flipkart/")
PIPELINE_DIR = Path(os.environ.get("THEME2_PIPELINE_DIR", str(DEFAULT_PIPELINE_DIR))).resolve()
HOST = os.environ.get("M7_HOST", "127.0.0.1")
PORT = int(os.environ.get("M7_PORT", "8057"))
MAPPLS_SDK_KEY = (os.environ.get("M7_MAPPLS_SDK_KEY") or os.environ.get("MAPPLS_API_KEY") or "").strip()

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

os.environ.setdefault("THEME2_PIPELINE_DIR", str(PIPELINE_DIR))


ARTIFACTS = None
M5_MODULE = None
M6_MODULE = None
OVERVIEW_CACHE = None
USING_FALLBACK_SCORER = False


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def finite_float(value, default=None):
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return default


def to_jsonable(value: Any):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def load_pipeline_modules():
    global ARTIFACTS, M5_MODULE, M6_MODULE, USING_FALLBACK_SCORER
    if ARTIFACTS is not None:
        return M5_MODULE, M6_MODULE, ARTIFACTS

    import importlib

    M5_MODULE = importlib.import_module("m5_inference_engine")
    M6_MODULE = importlib.import_module("m6_resource_rule_engine")
    try:
        ARTIFACTS = M5_MODULE.PipelineArtifacts()
    except ModuleNotFoundError as exc:
        if exc.name != "xgboost":
            raise
        print("[M7] xgboost is not installed; using dashboard fallback CIS scorer.")
        ARTIFACTS = build_dashboard_artifacts_without_xgboost()
        USING_FALLBACK_SCORER = True
    return M5_MODULE, M6_MODULE, ARTIFACTS


def load_pickle_or_joblib(path: Path):
    try:
        with path.open("rb") as f:
            return pickle.load(f)
    except Exception:
        return joblib.load(path)


class FallbackCISScorer:
    """Small dashboard fallback when xgboost is unavailable locally.

    It uses historical CIS means from cis_scores.csv by cause, corridor, and
    hour. This keeps the dashboard runnable, while environments with xgboost
    still use the real scorer_model.pkl through M5's normal path.
    """

    def __init__(self, encoding_maps: dict, cis_scores: pd.DataFrame):
        self.inverse_maps = {
            col: {int(code): cat for cat, code in mapping.items()}
            for col, mapping in encoding_maps.items()
        }
        self.global_mean = float(pd.to_numeric(cis_scores["CIS"], errors="coerce").mean())
        self.by_cause = cis_scores.groupby("event_cause")["CIS"].mean().to_dict()
        self.by_corridor = cis_scores.groupby("corridor_final")["CIS"].mean().to_dict()
        self.by_hour = cis_scores.groupby("hour")["CIS"].mean().to_dict()

    def predict(self, X):
        rows = X.to_dict(orient="records") if hasattr(X, "to_dict") else list(X)
        preds = []
        for row in rows:
            cause = self.inverse_maps.get("event_cause", {}).get(int(row.get("event_cause_code", -1)))
            corridor = self.inverse_maps.get("corridor_final", {}).get(int(row.get("corridor_final_code", -1)))
            hour = row.get("hour")
            values = [
                self.by_cause.get(cause),
                self.by_corridor.get(corridor),
                self.by_hour.get(hour),
                self.global_mean,
            ]
            values = [float(v) for v in values if v is not None and math.isfinite(float(v))]
            preds.append(sum(values) / len(values))
        return preds


class DashboardArtifacts:
    pass


def build_dashboard_artifacts_without_xgboost():
    artifacts = DashboardArtifacts()
    with (PIPELINE_DIR / "category_encoding_maps.json").open("r", encoding="utf-8") as f:
        artifacts.encoding_maps = json.load(f)

    artifacts.corridor_model = load_pickle_or_joblib(PIPELINE_DIR / "corridor_model.pkl")

    with (PIPELINE_DIR / "nearest_corridor_nn.pkl").open("rb") as f:
        d = pickle.load(f)
        artifacts.corridor_nn_model = d["model"]
        artifacts.corridor_nn_labels = d["labels"]

    with (PIPELINE_DIR / "police_station_nn.pkl").open("rb") as f:
        d = pickle.load(f)
        artifacts.police_station_nn_model = d["model"]
        artifacts.police_station_nn_labels = d["labels"]

    with (PIPELINE_DIR / "cis_signal_tables.json").open("r", encoding="utf-8") as f:
        artifacts.cis_signal_tables = json.load(f)

    with (PIPELINE_DIR / "eta_baselines.json").open("r", encoding="utf-8") as f:
        artifacts.eta_baselines = json.load(f)

    artifacts.closure_bundle = joblib.load(PIPELINE_DIR / "closure_model_bundle.pkl")
    artifacts.closure_metrics = read_json(PIPELINE_DIR / "closure_eval_metrics.json", {})
    artifacts.scorer_metrics = read_json(PIPELINE_DIR / "scorer_eval_metrics.json", {})
    cis_scores = pd.read_csv(PIPELINE_DIR / "cis_scores.csv")
    artifacts.scorer_model = FallbackCISScorer(artifacts.encoding_maps, cis_scores)
    artifacts.scorer_model_class = "HistoricalCISMeanFallback"
    artifacts.forecast = read_json(PIPELINE_DIR / "forecast.json", {})
    return artifacts


def top_forecast_hotspots(forecast: dict, limit=12):
    rows = []
    for corridor, payload in (forecast or {}).items():
        next_forecast = (payload.get("next_weeks_forecast") or [{}])[0]
        predicted = finite_float(next_forecast.get("predicted_incidents"), 0.0)
        rows.append({
            "corridor": corridor,
            "predicted_incidents": round(predicted, 2),
            "confidence": payload.get("confidence", "UNKNOWN"),
            "avg_weekly_incidents_historical": round(
                finite_float(payload.get("avg_weekly_incidents_historical"), 0.0), 2
            ),
            "week_start": next_forecast.get("week_start"),
        })
    return sorted(rows, key=lambda r: r["predicted_incidents"], reverse=True)[:limit]


def endpoint_segments(endpoints: dict, forecast: dict):
    segments = []
    for corridor, points in (endpoints or {}).items():
        origin = points.get("origin")
        destination = points.get("destination")
        if not origin or not destination:
            continue
        forecast_payload = (forecast or {}).get(corridor, {})
        next_forecast = (forecast_payload.get("next_weeks_forecast") or [{}])[0]
        segments.append({
            "corridor": corridor,
            "origin": origin,
            "destination": destination,
            "forecast": finite_float(next_forecast.get("predicted_incidents"), 0.0),
            "confidence": forecast_payload.get("confidence", "UNKNOWN"),
        })
    return segments


def historical_heat_points(clean_df: pd.DataFrame, cis_df: pd.DataFrame | None, limit=1600):
    cols = ["id", "latitude", "longitude", "event_cause", "corridor", "requires_road_closure", "start_datetime"]
    df = clean_df[[c for c in cols if c in clean_df.columns]].copy()
    if cis_df is not None and {"id", "CIS"}.issubset(cis_df.columns):
        df = df.merge(cis_df[["id", "CIS"]], on="id", how="left")
    else:
        df["CIS"] = 0.0

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["CIS"] = pd.to_numeric(df["CIS"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["latitude", "longitude"])
    if len(df) > limit:
        high = df.sort_values("CIS", ascending=False).head(limit // 2)
        rest = df.drop(high.index).sample(limit - len(high), random_state=42)
        df = pd.concat([high, rest], ignore_index=True)

    out = []
    for row in df.itertuples(index=False):
        item = row._asdict()
        closed = str(item.get("requires_road_closure", "")).lower() in {"true", "1", "yes"}
        out.append({
            "id": item.get("id"),
            "lat": finite_float(item.get("latitude")),
            "lng": finite_float(item.get("longitude")),
            "cause": item.get("event_cause"),
            "corridor": item.get("corridor"),
            "closure": closed,
            "cis": round(finite_float(item.get("CIS"), 0.0), 3),
            "start": str(item.get("start_datetime", "")),
        })
    return out


def model_metric_cards():
    closure = read_json(PIPELINE_DIR / "closure_eval_metrics.json", {})
    scorer = read_json(PIPELINE_DIR / "scorer_eval_metrics.json", {})
    forecaster = read_json(PIPELINE_DIR / "forecaster_eval_metrics.json", {})

    closure_metrics = closure.get("metrics", closure)
    return {
        "closure": {
            "model": closure.get("model_name"),
            "roc_auc": closure_metrics.get("roc_auc"),
            "precision": closure_metrics.get("precision"),
            "recall": closure_metrics.get("recall"),
            "f1": closure_metrics.get("f1"),
            "threshold": closure.get("decision_threshold"),
        },
        "cis": {
            "model": scorer.get("model_name") or scorer.get("model"),
            "mae": scorer.get("mae"),
            "r2": scorer.get("r2"),
            "max_possible_95th_pct": scorer.get("max_possible_95th_pct"),
        },
        "forecast": {
            "summary": forecaster.get("summary") or forecaster.get("model_summary"),
            "generated_rows": forecaster.get("generated_rows"),
        },
    }


def build_overview():
    global OVERVIEW_CACHE
    if OVERVIEW_CACHE is not None:
        return OVERVIEW_CACHE

    clean_path = PIPELINE_DIR / "clean_incidents.csv"
    feature_path = PIPELINE_DIR / "feature_matrix.csv"
    cis_path = PIPELINE_DIR / "cis_scores.csv"

    clean = pd.read_csv(clean_path)
    feature = pd.read_csv(feature_path) if feature_path.exists() else None
    cis = pd.read_csv(cis_path) if cis_path.exists() else None
    forecast = read_json(PIPELINE_DIR / "forecast.json", {})
    endpoints = read_json(PIPELINE_DIR / "corridor_endpoints.json", {})
    resource_plan = read_json(PIPELINE_DIR / "resource_plan.json", [])

    closure_rate = (
        clean["requires_road_closure"].astype(str).str.lower().isin(["true", "1", "yes"]).mean()
        if "requires_road_closure" in clean.columns else 0.0
    )
    top_causes = (
        clean["event_cause"].fillna("UNKNOWN").value_counts().head(10).rename_axis("cause")
        .reset_index(name="count").to_dict(orient="records")
    )

    if feature is not None and "corridor_final" in feature.columns:
        top_corridors = (
            feature["corridor_final"].fillna("UNKNOWN").value_counts().head(12)
            .rename_axis("corridor").reset_index(name="count").to_dict(orient="records")
        )
    else:
        top_corridors = (
            clean["corridor"].fillna("UNKNOWN").value_counts().head(12)
            .rename_axis("corridor").reset_index(name="count").to_dict(orient="records")
        )

    OVERVIEW_CACHE = {
        "pipeline_dir": str(PIPELINE_DIR),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "incidents": int(len(clean)),
            "closure_rate": round(float(closure_rate), 4),
            "corridors": int(clean["corridor"].nunique()) if "corridor" in clean.columns else None,
            "causes": int(clean["event_cause"].nunique()) if "event_cause" in clean.columns else None,
        },
        "metrics": model_metric_cards(),
        "top_causes": top_causes,
        "top_corridors": top_corridors,
        "heat_points": historical_heat_points(clean, cis),
        "forecast_hotspots": top_forecast_hotspots(forecast),
        "corridor_segments": endpoint_segments(endpoints, forecast),
        "resource_examples": resource_plan[:3] if isinstance(resource_plan, list) else [],
    }
    return OVERVIEW_CACHE


def nearest_corridor_segments(corridor: str, event_lat: float, event_lng: float, limit=3, mappls_key=None):
    """
    Build proper diversion routes using the Mappls Routing API for real road geometry.

    Strategy:
      1. Pick two points ~1.5 km upstream/downstream from the incident along the corridor direction.
      2. Route between them → first route = congestion road (red), alternates = diversions (blue).
      3. All polylines are real road-snapped geometry from the API.
      4. Falls back to geometric offsets if the API call fails.
    """
    endpoints = read_json(PIPELINE_DIR / "corridor_endpoints.json", {})
    forecast = read_json(PIPELINE_DIR / "forecast.json", {})
    cis_scores_path = PIPELINE_DIR / "cis_scores.csv"

    # Build per-corridor CIS averages
    cis_by_corridor: dict = {}
    cis_hourly_by_corridor: dict = {}
    if cis_scores_path.exists():
        try:
            cis_df = pd.read_csv(cis_scores_path)
            if {"corridor_final", "CIS"}.issubset(cis_df.columns):
                cis_by_corridor = (
                    cis_df.groupby("corridor_final")["CIS"]
                    .mean().round(3).to_dict()
                )
            if {"corridor_final", "CIS", "hour"}.issubset(cis_df.columns):
                for corr, grp in cis_df.groupby("corridor_final"):
                    hourly = grp.groupby("hour")["CIS"].mean().round(3).to_dict()
                    cis_hourly_by_corridor[str(corr)] = {
                        int(h): float(v) for h, v in hourly.items()
                    }
        except Exception:
            pass

    affected = endpoints.get(corridor, {})
    aff_origin = affected.get("origin")
    aff_dest   = affected.get("destination")

    diversions = []
    congestion_polyline = None

    next_fc_raw = ((forecast.get(corridor, {}) or {}).get("next_weeks_forecast") or [{}])[0]
    corridor_cis = cis_by_corridor.get(corridor, 0.0)
    corridor_hourly = cis_hourly_by_corridor.get(corridor, {})

    # Compute direction vector along corridor for offset waypoints
    OFFSET = 0.014  # ~1.5 km in degrees
    if aff_origin and aff_dest:
        dlat = aff_dest[0] - aff_origin[0]
        dlng = aff_dest[1] - aff_origin[1]
        length = max(math.hypot(dlat, dlng), 1e-9)
        norm_lat = dlat / length
        norm_lng = dlng / length
    else:
        norm_lat, norm_lng = 0.0, 1.0

    # Two points ~1.5 km before/after incident along the corridor
    start_lat = event_lat - norm_lat * OFFSET
    start_lng = event_lng - norm_lng * OFFSET
    end_lat   = event_lat + norm_lat * OFFSET
    end_lng   = event_lng + norm_lng * OFFSET

    api_success = False

    # ── Try Mappls Routing API for real road geometry ─────────────────────────
    if mappls_key:
        import requests

        # 1) Get congestion polyline using wider waypoints (~1.5 km)
        cong_url = (
            f"https://apis.mappls.com/advancedmaps/v1/{mappls_key}/route_adv/driving/"
            f"{start_lng},{start_lat};{end_lng},{end_lat}"
            f"?alternatives=false&steps=true&geometries=geojson&overview=full"
        )
        try:
            resp = requests.get(cong_url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes:
                    geom = routes[0].get("geometry", {})
                    if isinstance(geom, dict) and geom.get("type") == "LineString":
                        congestion_polyline = [[p[1], p[0]] for p in geom.get("coordinates", [])]
        except Exception as e:
            print(f"[M7] Congestion route API error: {e}")

        # 2) Get diversion alternates using shorter entry/exit points (~500m)
        #    — same approach as the old working version
        if aff_origin and aff_dest:
            ALONG = 0.0045
            entry_pt = [event_lat - norm_lat * ALONG, event_lng - norm_lng * ALONG]
            exit_pt  = [event_lat + norm_lat * ALONG, event_lng + norm_lng * ALONG]
        else:
            entry_pt = [event_lat - 0.0045, event_lng - 0.0045]
            exit_pt  = [event_lat + 0.0045, event_lng + 0.0045]

        div_url = (
            f"https://apis.mappls.com/advancedmaps/v1/{mappls_key}/route_adv/driving/"
            f"{entry_pt[1]},{entry_pt[0]};{exit_pt[1]},{exit_pt[0]}"
            f"?alternatives=true&steps=true&geometries=geojson"
        )
        try:
            resp = requests.get(div_url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes:
                    for i, r in enumerate(routes):
                        if i >= limit:
                            break
                        geom = r.get("geometry", {})
                        if isinstance(geom, dict) and geom.get("type") == "LineString":
                            path = [[p[1], p[0]] for p in geom.get("coordinates", [])]
                        else:
                            continue
                        if len(path) < 2:
                            continue

                        road_names = []
                        for leg in r.get("legs", []):
                            for step in leg.get("steps", []):
                                name = step.get("name", "")
                                if name and name.lower() not in [rn.lower() for rn in road_names]:
                                    road_names.append(name)

                        road_desc = "via " + ", ".join(road_names[:3]) if road_names else "via local roads"
                        diversions.append({
                            "name": f"Alternate {i+1} ({road_desc})",
                            "type": "api_bypass",
                            "corridor": corridor,
                            "polyline": path,
                            "forecast_incidents": finite_float(next_fc_raw.get("predicted_incidents"), 0.0),
                            "avg_cis": corridor_cis,
                            "hourly_cis": corridor_hourly,
                            "description": f"Alternate route: {road_desc}. Avoids the congested incident segment.",
                        })

                    if len(diversions) > 0:
                        api_success = True
                        if len(diversions) <= 2:
                            diversions[0]["description"] += (
                                " Note: Congestion is there, I want to show you more paths but since only one or "
                                "two bypass the incident path and will eventually bring you to the same road."
                            )
        except Exception as e:
            print(f"[M7] Diversion routing API error: {e}")

    # ── Fallback: geometric lines + alternate corridors if API failed ─────────
    if not api_success and aff_origin and aff_dest:
        perp_lat = -norm_lng
        perp_lng =  norm_lat
        ALONG   = 0.0045
        LATERAL = 0.0036
        entry_pt = [event_lat - norm_lat * ALONG, event_lng - norm_lng * ALONG]
        exit_pt  = [event_lat + norm_lat * ALONG, event_lng + norm_lng * ALONG]
        detour_L = [event_lat + perp_lat * LATERAL, event_lng + perp_lng * LATERAL]
        detour_R = [event_lat - perp_lat * LATERAL, event_lng - perp_lng * LATERAL]
        if not congestion_polyline:
            congestion_polyline = [entry_pt, [event_lat, event_lng], exit_pt]
        diversions.append({
            "name": f"{corridor} — Upstream diversion",
            "type": "upstream_bypass", "corridor": corridor,
            "polyline": [entry_pt, detour_L, exit_pt],
            "forecast_incidents": finite_float(next_fc_raw.get("predicted_incidents"), 0.0),
            "avg_cis": corridor_cis, "hourly_cis": corridor_hourly,
            "description": f"Upstream diversion on {corridor}: detour via parallel road.",
        })
        diversions.append({
            "name": f"{corridor} — Downstream diversion",
            "type": "downstream_bypass", "corridor": corridor,
            "polyline": [exit_pt, detour_R, entry_pt],
            "forecast_incidents": finite_float(next_fc_raw.get("predicted_incidents"), 0.0),
            "avg_cis": corridor_cis, "hourly_cis": corridor_hourly,
            "description": f"Downstream diversion on {corridor}: detour via parallel road.",
        })

    # ── If still not enough diversions, add nearby alternate corridors ────────
    if len(diversions) < limit:
        CLIP_RADIUS = 0.018
        def _clip_segment(p1, p2, ilat, ilng, radius):
            pts = []
            for t in [i / 40.0 for i in range(41)]:
                lat = p1[0] + t * (p2[0] - p1[0])
                lng = p1[1] + t * (p2[1] - p1[1])
                if math.hypot(lat - ilat, lng - ilng) <= radius:
                    pts.append([lat, lng])
            if len(pts) < 2:
                pts = [p1, p2]
            return pts

        endpoints = read_json(PIPELINE_DIR / "corridor_endpoints.json", {})
        alt_rows = []
        for name, points in endpoints.items():
            if name == corridor:
                continue
            origin = points.get("origin")
            destination = points.get("destination")
            if not origin or not destination:
                continue
            mid_lat = (origin[0] + destination[0]) / 2
            mid_lng = (origin[1] + destination[1]) / 2
            dist = math.hypot(mid_lat - event_lat, mid_lng - event_lng)
            next_forecast = ((forecast.get(name, {}) or {}).get("next_weeks_forecast") or [{}])[0]
            alt_cis = cis_by_corridor.get(name, 0.0)
            alt_hourly = cis_hourly_by_corridor.get(name, {})
            clipped = _clip_segment(origin, destination, event_lat, event_lng, CLIP_RADIUS)
            alt_rows.append((dist, {
                "name": f"Alternate: {name}",
                "type": "alternate_corridor",
                "corridor": name,
                "polyline": clipped,
                "forecast_incidents": finite_float(next_forecast.get("predicted_incidents"), 0.0),
                "avg_cis": round(alt_cis, 3),
                "hourly_cis": alt_hourly,
                "description": f"Alternate route: use {name} to bypass the incident area entirely.",
            }))

        alt_rows.sort(key=lambda x: x[0])
        needed = max(0, limit - len(diversions))
        for _, alt in alt_rows[:needed]:
            diversions.append(alt)

    return diversions[:limit], congestion_polyline


def resource_pins(event_lat: float, event_lng: float, plan: dict):
    pins = []
    officer_count = int(plan.get("officer_count", 0) or 0)
    barricade_count = int(plan.get("barricade_count", 0) or 0)
    offsets = [
        (0.0014, 0.0008), (-0.0013, 0.0010), (0.0011, -0.0012), (-0.0012, -0.0009),
        (0.0020, 0.0), (0.0, 0.0020), (-0.0020, 0.0), (0.0, -0.0020),
    ]
    for i in range(officer_count):
        off = offsets[i % len(offsets)]
        pins.append({"type": "officer", "label": f"Officer {i + 1}", "lat": event_lat + off[0], "lng": event_lng + off[1]})
    for i in range(barricade_count):
        angle = (2 * math.pi * i) / max(barricade_count, 1)
        pins.append({
            "type": "barricade",
            "label": f"Barricade {i + 1}",
            "lat": event_lat + math.sin(angle) * 0.0018,
            "lng": event_lng + math.cos(angle) * 0.0018,
        })
    return pins


# ---------------------------------------------------------------------------
# Known non-road zones in Bengaluru: (lat, lng, radius_degrees, place_name, place_type)
# radius_degrees ≈ metres / 111000
# ---------------------------------------------------------------------------
NON_ROAD_ZONES = [
    # Parks & Forests
    (12.9738, 77.5906, 0.0035, "Cubbon Park",              "park"),
    (12.9340, 77.5840, 0.0060, "Lalbagh Botanical Garden", "botanical garden"),
    (12.9616, 77.6417, 0.0080, "Ulsoor Lake",              "lake"),
    (13.0475, 77.5798, 0.0030, "Sankey Tank",              "lake / park"),
    (12.9088, 77.5633, 0.0050, "Bannerghatta National Park entrance", "national park"),
    # Airports / Railway
    (13.1986, 77.7066, 0.0200, "Kempegowda International Airport", "airport"),
    (12.9772, 77.5718, 0.0015, "KSR Bengaluru City Railway Station", "railway station"),
    # Stadiums
    (12.9784, 77.5993, 0.0020, "M. Chinnaswamy Stadium", "stadium"),
    (12.9500, 77.5975, 0.0015, "Kanteerava Stadium",     "stadium"),
    # Major lakes
    (12.9308, 77.6338, 0.0040, "Bellandur Lake",         "lake"),
    (12.9076, 77.6600, 0.0025, "Varthur Lake",           "lake"),
]


def check_non_road_location(lat: float, lng: float) -> dict | None:
    """
    Returns a dict with 'place_name' and 'place_type' if (lat, lng) falls inside
    a known non-road zone, otherwise returns None.
    """
    for zone_lat, zone_lng, radius, name, ptype in NON_ROAD_ZONES:
        dist = math.hypot(lat - zone_lat, lng - zone_lng)
        if dist <= radius:
            return {"place_name": name, "place_type": ptype, "distance_deg": round(dist, 5)}
    return None


def predict_live_event(event: dict, mappls_key: str = None):
    # ── Dynamic Geocoding if requested ─────────────────────────────────────────
    if event.get("use_geocoding") and event.get("address"):
        import requests
        import urllib.parse
        addr = urllib.parse.quote(event["address"])
        resolved = False
        
        # Try Mappls Geocode API first
        if mappls_key:
            try:
                url = f"https://apis.mappls.com/advancedmaps/v1/{mappls_key}/geocode?address={addr}"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("copResults", [])
                    if results:
                        event["latitude"] = float(results[0]["latitude"])
                        event["longitude"] = float(results[0]["longitude"])
                        resolved = True
            except:
                pass
                
        # Fallback to OpenStreetMap Nominatim
        if not resolved:
            try:
                url = f"https://nominatim.openstreetmap.org/search?q={addr}&format=json&limit=1"
                headers = {"User-Agent": "M7Dashboard/1.0"}
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        event["latitude"] = float(data[0]["lat"])
                        event["longitude"] = float(data[0]["lon"])
                        resolved = True
            except:
                pass
                
        if not resolved:
            raise ValueError(f"Could not find coordinates for '{event['address']}'. Please check the road name.")

    lat = finite_float(event.get("latitude"), 12.9716)
    lng = finite_float(event.get("longitude"), 77.5946)

    # ── Non-road location gate (using MapmyIndia API) ─────────────────────────
    if mappls_key:
        try:
            import requests
            url = f"https://apis.mappls.com/advancedmaps/v1/{mappls_key}/rev_geocode?lat={lat}&lng={lng}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    res = results[0]
                    poi = res.get("poi", "").lower()
                    street = res.get("street", "").lower()
                    non_road_keywords = ["park", "hospital", "lake", "garden", "stadium", "mall", "airport", "school", "college"]
                    if not street and any(kw in poi for kw in non_road_keywords):
                        raise ValueError(
                            f"The given lati/longi doesn't belongs to the roads and won't run the model. "
                            f"It appears to be {res.get('poi', 'a non-road area')}."
                        )
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            pass # Fallback to local check if network fails

    non_road = check_non_road_location(lat, lng)
    if non_road:
        raise ValueError(
            f"The given lati/longi doesn't belongs to the roads and won't run the model. "
            f"The coordinates appear to be inside {non_road['place_name']} ({non_road['place_type']})."
        )

    m5, m6, artifacts = load_pipeline_modules()
    prediction = m5.predict_event(event, artifacts)
    plan = m6.build_resource_plan(prediction)
    corridor = prediction["resolved_location"].get("corridor_final", "Non-corridor")
    diversions_result = nearest_corridor_segments(corridor, lat, lng, limit=3, mappls_key=mappls_key)
    if isinstance(diversions_result, tuple):
        diversions, congestion_polyline = diversions_result
    else:
        diversions = diversions_result
        congestion_polyline = None
        
    return {
        "prediction": prediction,
        "resource_plan": plan,
        "diversion_routes": diversions,
        "congestion_polyline": congestion_polyline,
        "resource_pins": resource_pins(lat, lng, plan),
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            if not MAPPLS_SDK_KEY:
                return self.write_error(500, "M7_MAPPLS_SDK_KEY is required for the MapMyIndia/Mappls map.")
            return self.write_json({
                "pipeline_dir": str(PIPELINE_DIR),
                "mappls_sdk_key": MAPPLS_SDK_KEY,
                "map_provider": "mappls",
                "using_fallback_scorer": USING_FALLBACK_SCORER,
            })
        if path == "/api/overview":
            try:
                return self.write_json(build_overview())
            except Exception as exc:
                return self.write_error(500, exc)
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/predict":
            return self.write_error(404, "Unknown endpoint")
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            event = json.loads(body or "{}")
            return self.write_json(predict_live_event(event))
        except Exception as exc:
            return self.write_error(500, exc)

    def write_json(self, payload: Any, status=200):
        body = json.dumps(to_jsonable(payload), indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_error(self, status: int, exc: Any):
        payload = {
            "error": str(exc),
            "traceback": traceback.format_exc(limit=5),
        }
        return self.write_json(payload, status=status)


def main():
    if not PIPELINE_DIR.exists():
        raise FileNotFoundError(f"Pipeline directory not found: {PIPELINE_DIR}")
    if not MAPPLS_SDK_KEY:
        raise RuntimeError("M7_MAPPLS_SDK_KEY is required for the MapMyIndia/Mappls map.")
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"[M7] Serving dashboard at {url}")
    print(f"[M7] Pipeline artifacts: {PIPELINE_DIR}")
    print("[M7] Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
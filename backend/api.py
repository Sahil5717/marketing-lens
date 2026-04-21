"""
FastAPI Backend — Marketing ROI & Budget Optimization Engine
All imports updated to match upgraded engine function names.
Run: uvicorn api:app --reload --port 8000
"""
import os, sys, json, tempfile
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

# Auth & persistence
from auth import register_user, login_user, get_current_user, require_role, require_editor, check_permission
from persistence import init_db, save_session, load_session, save_scenario, list_scenarios, load_scenario, compare_scenarios

# ═══ CORRECTED IMPORTS — matching upgraded engine function names ═══
from mock_data import generate_all_data, export_to_csv
from validator import validate_data
from engines.attribution import run_all_attribution, compute_attribution_roi
from engines.response_curves import fit_response_curves                       # ✅ unchanged
from engines.optimizer import optimize_budget, sensitivity_analysis            # ✅ unchanged
from engines.diagnostics import generate_recommendations                      # ✅ was: run_diagnostics
from engines.leakage import run_three_pillars                                 # ✅ was: calculate_all_pillars
from engines.trend_analysis import run_trend_analysis                         # ✅ was: run_full_trend_analysis
from engines.funnel_analysis import run_funnel_analysis                       # ✅ was: run_full_funnel_analysis
from engines.roi_formulas import compute_all_roi                              # ✅ was: run_full_roi_analysis
from engines.adstock import compute_channel_adstock                           # ✅ unchanged
from engines.mmm import run_mmm                                              # ✅ unchanged
from engines.markov_attribution import run_markov_attribution                 # ✅ was: markov_attribution
from engines.forecasting import run_forecast                                  # ✅ was: run_full_forecast
from engines.cross_channel import run_cross_channel_analysis                  # ✅ unchanged
from engines.shapley import compute_shapley_values                            # ✅ was: run_shapley
from engines.multi_objective import pareto_optimize                           # ✅ was: multi_objective_optimize
from engines.geo_lift import run_geo_lift                                     # ✅ was: design_geo_test
from engines.hierarchical_forecast import run_hierarchical_forecast           # ✅ was: hierarchical_forecast
from engines.automated_recs import automated_recommendations, check_model_drift, track_realization

app = FastAPI(title="Marketing ROI & Budget Optimization Engine", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── New: macro baseline router (per build plan v2 §2A.1) ───
# Included here so its /api/market-context handler wins routing over the
# older in-module handler lower in this file. The older handler reads from
# per-tenant uploaded "external data" state; the new one reads from the
# centrally-curated macro baseline. Once callers migrate, the old handler
# is scheduled for removal.
from routes_macro_baseline import router as macro_baseline_router
app.include_router(macro_baseline_router)

from routes_executive_summary import router as executive_summary_router
app.include_router(executive_summary_router)

from routes_budget_optimization import router as budget_optimization_router
app.include_router(budget_optimization_router)

from routes_channel_performance import router as channel_performance_router
app.include_router(channel_performance_router)


@app.on_event("startup")
def _startup_seed_demo_users():
    """
    Seed the MarketLens demo users on server boot so fresh deploys
    (including Railway, Docker, or any clean sqlite start) have valid
    credentials available immediately.

    Idempotent — safe to run on every boot; existing users are skipped.
    If seeding fails for any reason (e.g., DB not yet initialized),
    the error is logged but doesn't block server startup.
    """
    try:
        from auth import seed_demo_users
        seed_demo_users()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Demo user seeding failed at startup: %s — users can be created "
            "manually via /api/auth/register if needed.", e,
        )

from engines.data_splitter import split_data, validate_split
from engines.insights import generate_insights, compute_qoq_yoy_trends, generate_smart_recommendations
from engines.external_data import process_competitive_data, process_market_events, process_market_trends, merge_external_recommendations

# In-memory state
_state: Dict = {
    "campaign_data": None, "journey_data": None, "validation": None,
    "curves": None, "attribution": None, "attribution_roi": None,
    "optimization": None, "diagnostics": None, "pillars": None,
    "trend_analysis": None, "funnel_analysis": None, "roi_analysis": None,
    "data_split": None,  # reporting vs training split metadata
    "reporting_data": None,  # last 12 months for ROI/KPIs
    "training_data": None,   # full history for models
    "insights": None, "smart_recs": None,
    "qoq_yoy": None, "channel_trends": None,
    "model_selections": {
        "attribution": "markov", "response_curves": "auto",
        "mmm": "auto", "forecasting": "prophet", "optimizer": "slsqp",
    },
    "external_competitive": None, "external_events": None, "external_trends": None,
    "competitive_result": None, "events_result": None, "trends_result": None,
    # Engagements — ephemeral, in-memory for the pitch. Real multi-tenancy
    # would be a separate SQLite table with engagement_id on every data row.
    # Pre-seeded with a handful of plausible engagements so the screen
    # feels populated on first view. The "active" one (id matches
    # active_engagement_id) is what Diagnosis/Plan/etc. render against —
    # today they all render against the same mock data regardless, but
    # the field exists so the shell can show a "current engagement" badge.
    "engagements": None,  # populated lazily on first /api/engagements call
    "active_engagement_id": "acme-fy2025",
    # Bayesian MMM — fit in a background thread after run-analysis completes.
    # `_bayes_status` holds the current lifecycle state the UI polls; `_bayes_result`
    # is the full result once the fit converges. Never blocks the main
    # request cycle. See _kickoff_bayesian_fit.
    "bayes_status": {
        "state": "idle",         # idle | pending | running | ready | failed | non_converged
        "started_at": None,      # ISO timestamp
        "finished_at": None,     # ISO timestamp
        "elapsed_s": None,
        "r_hat_max": None,
        "ess_min": None,
        "n_channels": None,
        "message": None,
    },
    "bayes_result": None,
}

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, pd.Timestamp): return obj.isoformat()
        if isinstance(obj, (bool,)): return bool(obj)
        return super().default(obj)

def _j(obj):
    """Safely serialize numpy/pandas objects to JSON."""
    return json.loads(json.dumps(obj, cls=NumpyEncoder))


def _ensure_analysis():
    """Lazy execution: auto-run analysis if data is loaded but engines haven't run."""
    if _state["campaign_data"] is not None and _state["curves"] is None:
        _run_all_engines()


def _get_data_warnings():
    """Return warnings about data quality and sufficiency."""
    warnings = []
    df = _state.get("reporting_data")
    if df is None: df = _state.get("campaign_data")
    if df is None: return ["No data loaded"]
    n_rows = len(df)
    n_channels = df["channel"].nunique() if "channel" in df.columns else 0
    n_months = df["month"].nunique() if "month" in df.columns else 0
    if n_rows < 50: warnings.append(f"Only {n_rows} rows — results may be statistically weak. Upload more data for reliable outputs.")
    if n_channels < 3: warnings.append(f"Only {n_channels} channels — optimizer needs 3+ channels for meaningful reallocation.")
    if n_months < 6: warnings.append(f"Only {n_months} months of reporting data — KPIs may not represent full seasonal cycle.")
    training = _state.get("training_data")
    if training is not None:
        t_months = training["month"].nunique() if "month" in training.columns else 0
        if t_months < 24: warnings.append(f"Only {t_months} months of training data — response curves and forecasts have wide uncertainty.")
        if t_months < 36: warnings.append(f"Only {t_months} months for MMM — Bayesian model needs 36+ months for convergent posteriors.")
    return warnings


# ═══════════════════════════════════════════════
#  CORE ENDPOINTS
# ═══════════════════════════════════════════════

@app.get("/api/status")
def api_status():
    """Engine status JSON. Moved from `/` to `/api/status` in v18c so
    that `/` can serve the MarketLens client HTML. Kept because some
    monitoring or smoke-test scripts may depend on it."""
    return {"status": "ok", "engine": "Marketing ROI & Budget Optimization Engine v2.0",
            "engines_loaded": True, "api_version": "2.0"}


@app.get("/api/health")
def health_check():
    """Health endpoint for deployment monitoring."""
    data_loaded = _state["campaign_data"] is not None
    engines_run = _state["curves"] is not None
    return {
        "status": "healthy" if data_loaded and engines_run else "ready" if not data_loaded else "data_loaded",
        "data_loaded": data_loaded,
        "engines_run": engines_run,
        "reporting_rows": len(_state["reporting_data"]) if _state.get("reporting_data") is not None else 0,
        "training_rows": len(_state["training_data"]) if _state.get("training_data") is not None else 0,
        "engines_available": {
            "curves": _state["curves"] is not None and len(_state["curves"]) > 0,
            "optimization": _state["optimization"] is not None,
            "diagnostics": _state["diagnostics"] is not None and len(_state["diagnostics"]) > 0,
            "pillars": _state["pillars"] is not None,
            "attribution": _state["attribution"] is not None,
        },
    }


@app.post("/api/load-mock-data")
def load_mock_data():
    """Load demo data and run all engines automatically."""
    data = generate_all_data()
    _state["campaign_data"] = data["campaign_performance"]
    _state["journey_data"] = data["user_journeys"]
    _state["validation"] = validate_data(_state["campaign_data"])

    # Process mock market data through the existing external_data pipeline
    # so the demo flow shows adjustments without requiring CSV uploads.
    # Same processors handle both — mock just provides the dataframes.
    reporting_df = _state["campaign_data"]
    # Flag so the UI can indicate "this is sample data" in editor view.
    # Cleared the moment real CSV uploads replace any of these.
    _state["_mock_market_data"] = True
    try:
        if "market_events" in data:
            _state["events_result"] = process_market_events(
                data["market_events"], reporting_df
            )
        if "market_trends" in data:
            _state["trends_result"] = process_market_trends(
                data["market_trends"], reporting_df
            )
        if "competitive_data" in data:
            _state["competitive_result"] = process_competitive_data(
                data["competitive_data"], reporting_df
            )
    except Exception as e:
        # Market data failures are non-fatal — the rest of the app works
        # without them. Log and continue.
        import logging
        logging.getLogger(__name__).warning(
            "Mock market data processing failed: %s — continuing without.", e
        )

    # Auto-run all engines so subsequent calls work
    _run_all_engines()
    
    return _j({
        "status": "ok",
        "rows": len(_state["campaign_data"]),
        "journey_rows": len(_state["journey_data"]),
        "channels": int(_state["campaign_data"]["channel"].nunique()),
        "campaigns": int(_state["campaign_data"]["campaign"].nunique()),
        "total_spend": float(_state["campaign_data"]["spend"].sum()),
        "total_revenue": float(_state["campaign_data"]["revenue"].sum()),
        "engines_run": True,
        "market_data_loaded": all([
            _state.get("events_result"),
            _state.get("trends_result"),
            _state.get("competitive_result"),
        ]),
    })


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read(); tmp.write(content); tmp_path = tmp.name
    try:
        if suffix == ".csv": df = pd.read_csv(tmp_path)
        elif suffix in (".xlsx", ".xls"): df = pd.read_excel(tmp_path)
        else: raise HTTPException(400, f"Unsupported: {suffix}")
        _state["campaign_data"] = df
        _state["validation"] = validate_data(df)
        return _j({"filename": file.filename, "rows": len(df), "columns": list(df.columns),
                    "validation": _state["validation"]})
    finally:
        os.unlink(tmp_path)


@app.post("/api/upload-journeys")
async def upload_journey_file(file: UploadFile = File(...)):
    """Upload user journey CSV/XLSX for multi-touch attribution."""
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read(); tmp.write(content); tmp_path = tmp.name
    try:
        if suffix == ".csv": df = pd.read_csv(tmp_path)
        elif suffix in (".xlsx", ".xls"): df = pd.read_excel(tmp_path)
        else: raise HTTPException(400, f"Unsupported: {suffix}")
        _state["journey_data"] = df
        return _j({"filename": file.filename, "rows": len(df), "columns": list(df.columns),
                    "status": "Journey data loaded. Re-run /api/run-analysis to include in attribution."})
    finally:
        os.unlink(tmp_path)


@app.post("/api/upload-competitive")
async def upload_competitive(file: UploadFile = File(...)):
    """Upload competitive intelligence CSV (SEMrush/SimilarWeb export)."""
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read(); tmp.write(content); tmp_path = tmp.name
    try:
        df = pd.read_csv(tmp_path) if suffix == ".csv" else pd.read_excel(tmp_path)
        required = {"date", "competitor", "channel", "estimated_spend"}
        missing = required - set(df.columns)
        if missing: raise HTTPException(400, f"Missing columns: {missing}. Required: {required}")
        _state["external_competitive"] = df
        _state["_mock_market_data"] = False
        # Process immediately if campaign data exists
        if _state["campaign_data"] is not None:
            reporting_df = _state["reporting_data"] if _state.get("reporting_data") is not None else _state["campaign_data"]
            _state["competitive_result"] = process_competitive_data(df, reporting_df)
            # Merge into smart recs
            if _state.get("smart_recs"):
                _state["smart_recs"] = merge_external_recommendations(
                    _state["smart_recs"], comp_result=_state["competitive_result"])
            return _j({"filename": file.filename, "rows": len(df), "competitors": int(df["competitor"].nunique()),
                        "channels": int(df["channel"].nunique()), "recommendations": len(_state["competitive_result"].get("recommendations",[])),
                        "status": "Competitive data loaded and processed"})
        return _j({"filename": file.filename, "rows": len(df), "status": "Competitive data loaded. Load campaign data first to process."})
    finally:
        os.unlink(tmp_path)

@app.post("/api/upload-events")
async def upload_events(file: UploadFile = File(...)):
    """Upload market events CSV (seasonal calendar, competitor actions, market shifts)."""
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read(); tmp.write(content); tmp_path = tmp.name
    try:
        df = pd.read_csv(tmp_path) if suffix == ".csv" else pd.read_excel(tmp_path)
        required = {"event_date", "event_type", "event_name", "impact_direction"}
        missing = required - set(df.columns)
        if missing: raise HTTPException(400, f"Missing columns: {missing}. Required: {required}")
        _state["external_events"] = df
        _state["_mock_market_data"] = False  # real upload overrides mock flag
        if _state["campaign_data"] is not None:
            reporting_df = _state["reporting_data"] if _state.get("reporting_data") is not None else _state["campaign_data"]
            _state["events_result"] = process_market_events(df, reporting_df)
            if _state.get("smart_recs"):
                _state["smart_recs"] = merge_external_recommendations(
                    _state["smart_recs"], events_result=_state["events_result"])
            return _j({"filename": file.filename, "events": len(df),
                        "upcoming": _state["events_result"]["summary"]["upcoming_events"],
                        "recommendations": len(_state["events_result"].get("recommendations",[])),
                        "status": "Market events loaded and processed"})
        return _j({"filename": file.filename, "rows": len(df), "status": "Events loaded. Load campaign data first to process."})
    finally:
        os.unlink(tmp_path)

@app.post("/api/upload-trends")
async def upload_trends(file: UploadFile = File(...)):
    """Upload market trends CSV (CPC/CPM trends, benchmarks, Google Trends)."""
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read(); tmp.write(content); tmp_path = tmp.name
    try:
        df = pd.read_csv(tmp_path) if suffix == ".csv" else pd.read_excel(tmp_path)
        required = {"date", "metric_type", "value"}
        missing = required - set(df.columns)
        if missing: raise HTTPException(400, f"Missing columns: {missing}. Required: {required}")
        _state["external_trends"] = df
        _state["_mock_market_data"] = False
        if _state["campaign_data"] is not None:
            reporting_df = _state["reporting_data"] if _state.get("reporting_data") is not None else _state["campaign_data"]
            _state["trends_result"] = process_market_trends(df, reporting_df)
            if _state.get("smart_recs"):
                _state["smart_recs"] = merge_external_recommendations(
                    _state["smart_recs"], trends_result=_state["trends_result"])
            return _j({"filename": file.filename, "metric_types": list(df["metric_type"].unique()),
                        "channels_covered": int(df["channel"].nunique()) if "channel" in df.columns else 0,
                        "recommendations": len(_state["trends_result"].get("recommendations",[])),
                        "status": "Market trends loaded and processed"})
        return _j({"filename": file.filename, "rows": len(df), "status": "Trends loaded. Load campaign data first to process."})
    finally:
        os.unlink(tmp_path)

@app.get("/api/external-data-status")
def get_external_data_status():
    """Check what external data is loaded."""
    return _j({
        "competitive": {"loaded": _state["external_competitive"] is not None,
            "summary": (_state.get("competitive_result") or {}).get("summary", {})},
        "events": {"loaded": _state["external_events"] is not None,
            "summary": (_state.get("events_result") or {}).get("summary", {})},
        "trends": {"loaded": _state["external_trends"] is not None,
            "summary": (_state.get("trends_result") or {}).get("summary", {})},
    })


def _normalize_date_columns(df):
    """Ensure both 'date' and 'month' columns exist for cross-engine compatibility."""
    df = df.copy()
    if "date" in df.columns and "month" not in df.columns:
        df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
    elif "month" in df.columns and "date" not in df.columns:
        df["date"] = pd.to_datetime(df["month"].astype(str).apply(lambda x: x+"-01" if len(str(x))<=7 else x), errors="coerce")
    if "channel_type" not in df.columns:
        df["channel_type"] = df.get("ct", "online")
    for col, alt in [("conversions","conv"),("impressions","imps"),("revenue","rev"),("campaign","camp"),("channel","ch")]:
        if col not in df.columns and alt in df.columns:
            df[col] = df[alt]
    for col in ["impressions","clicks","leads","mqls","sqls","conversions","spend","revenue",
                "bounce_rate","avg_session_duration_sec","form_completion_rate","nps_score"]:
        if col not in df.columns: df[col] = 0
    if "region" not in df.columns: df["region"] = "All"
    if "product" not in df.columns: df["product"] = "All"
    return df


def _run_all_engines():
    """Run all engines. Each engine is wrapped in try/except — one failure never crashes the chain."""
    df = _state["campaign_data"]
    if df is None: return
    
    df = _normalize_date_columns(df)
    _state["campaign_data"] = df
    
    # Split data
    date_col = "month" if "month" in df.columns else "date"
    try:
        split = split_data(df, reporting_months=12, date_column=date_col)
        _state["data_split"] = split["metadata"]
        reporting_df = _normalize_date_columns(split["reporting"])
        training_df = _normalize_date_columns(split["training"])
    except Exception as e:
        print(f"[WARN] Split failed ({e}), using full dataset")
        _state["data_split"] = {"reporting_period":{"months":0},"training_period":{"months":0},"error":str(e)}
        reporting_df = df; training_df = df
    _state["reporting_data"] = reporting_df
    _state["training_data"] = training_df
    
    # Response curves
    try:
        _state["curves"] = fit_response_curves(training_df, model_type=_state.get("_model_type", "power_law"))
        print(f"[OK] Curves: {len(_state['curves'])} channels")
    except Exception as e:
        print(f"[FAIL] Curves: {e}"); _state["curves"] = {}
    
    # Attribution
    attr_dicts = {}
    try:
        if _state["journey_data"] is not None:
            _state["attribution"] = run_all_attribution(_state["journey_data"])
            _state["attribution_roi"] = compute_attribution_roi(_state["attribution"], reporting_df)
            for mn, md in _state["attribution"].items():
                try:
                    if hasattr(md, "groupby"): attr_dicts[mn] = md.groupby("channel")["attributed_revenue"].sum().to_dict()
                    elif isinstance(md, dict): attr_dicts[mn] = md
                except: pass
            print(f"[OK] Attribution: {len(attr_dicts)} models")
            # Markov attribution (needs journey data)
            try:
                from engines.markov_attribution import run_markov_attribution
                j_groups = {}
                for _, r in _state["journey_data"].iterrows():
                    jid = str(r.get("journey_id", r.get("id", "")))
                    if jid not in j_groups: j_groups[jid] = {"tps":[], "cv":False, "rv":0}
                    j_groups[jid]["tps"].append({"ch": str(r.get("channel","")), "o": int(r.get("touchpoint_order",0))})
                    j_groups[jid]["cv"] = bool(r.get("converted", False))
                    j_groups[jid]["rv"] = float(r.get("conversion_revenue", 0))
                markov_result = run_markov_attribution(list(j_groups.values()))
                markov_ch = markov_result.get("channels", {})
                if markov_ch:
                    attr_dicts["markov"] = {ch: info.get("revenue", info.get("attributed_revenue",0)) for ch, info in markov_ch.items()}
                    print(f"[OK] Markov: {len(attr_dicts['markov'])} channels")
                else:
                    print("[WARN] Markov: 0 channels returned")
            except Exception as e:
                print(f"[WARN] Markov: {e}")
    except Exception as e:
        print(f"[FAIL] Attribution: {e}"); _state["attribution"] = {}
    _state["_attr_dicts"] = attr_dicts
    
    # Optimization
    try:
        rs = float(reporting_df["spend"].sum())
        _state["optimization"] = optimize_budget(_state["curves"], rs, objective="balanced")
        print(f"[OK] Optimizer: uplift={_state['optimization'].get('summary',{}).get('uplift_pct',0):.1f}%")
    except Exception as e:
        print(f"[FAIL] Optimizer: {e}")
        _state["optimization"] = {"channels":[],"summary":{"total_budget":0,"current_revenue":0,"optimized_revenue":0,"revenue_uplift":0,"uplift_pct":0,"current_roi":0,"optimized_roi":0}}
    
    # Diagnostics
    try:
        _state["diagnostics"] = generate_recommendations(reporting_df, _state["curves"], attr_dicts)
        print(f"[OK] Recs: {len(_state['diagnostics'])}")
    except Exception as e:
        print(f"[FAIL] Recs: {e}"); _state["diagnostics"] = []
    
    # Pillars
    try:
        _state["pillars"] = run_three_pillars(reporting_df, _state["optimization"])
        print(f"[OK] Pillars: risk={_state['pillars'].get('total_value_at_risk',0):,.0f}")
    except Exception as e:
        print(f"[FAIL] Pillars: {e}")
        _state["pillars"] = {"revenue_leakage":{"total_leakage":0,"leakage_pct":0,"by_channel":[]},"experience_suppression":{"total_suppression":0,"items":[]},"avoidable_cost":{"total_avoidable_cost":0,"items":[]},"total_value_at_risk":0,"correction_potential":{"reallocation_uplift":0,"cx_fix_recovery":0,"cost_savings":0,"total_recoverable":0}}
    
    # Trend, funnel, ROI
    try: _state["trend_analysis"] = run_trend_analysis(training_df); print("[OK] Trends")
    except Exception as e: print(f"[FAIL] Trends: {e}"); _state["trend_analysis"] = {}
    try: _state["funnel_analysis"] = run_funnel_analysis(reporting_df); print("[OK] Funnel")
    except Exception as e: print(f"[FAIL] Funnel: {e}"); _state["funnel_analysis"] = {}
    try: _state["roi_analysis"] = compute_all_roi(reporting_df, _state["curves"]); print("[OK] ROI")
    except Exception as e: print(f"[FAIL] ROI: {e}"); _state["roi_analysis"] = []
    
    # Insights & Smart Recommendations
    try:
        _state["insights"] = generate_insights(
            reporting_df, _state["curves"], _state["optimization"], _state["pillars"],
            attr_dicts, _state.get("mmm_result"), _state.get("trend_analysis"), _state.get("funnel_analysis"))
        print(f"[OK] Insights: {_state['insights'].get('generated_count',0)} generated")
    except Exception as e:
        print(f"[FAIL] Insights: {e}"); _state["insights"] = {"executive_headlines":[],"channel_stories":[],"cross_model_insights":[],"risk_narratives":[],"opportunity_narratives":[],"generated_count":0}
    
    try:
        _state["smart_recs"] = generate_smart_recommendations(
            reporting_df, _state["curves"], attr_dicts, _state["optimization"],
            _state["pillars"], _state.get("trend_analysis"), _state.get("mmm_result"),
            _state.get("model_selections"))
        print(f"[OK] Smart Recs: {len(_state['smart_recs'])}")
    except Exception as e:
        print(f"[FAIL] Smart Recs: {e}"); _state["smart_recs"] = []
    
    # QoQ/YoY trends
    try:
        _state["qoq_yoy"] = compute_qoq_yoy_trends(reporting_df)
        # Per-channel trends
        ch_trends = {}
        for ch in reporting_df["channel"].unique():
            ch_trends[ch] = compute_qoq_yoy_trends(reporting_df, channel=ch)
        _state["channel_trends"] = ch_trends
        print(f"[OK] QoQ/YoY: {len(ch_trends)} channels")
    except Exception as e:
        print(f"[FAIL] QoQ/YoY: {e}"); _state["qoq_yoy"] = {}; _state["channel_trends"] = {}
    
    # External data re-processing (if loaded)
    try:
        if _state.get("external_competitive") is not None:
            _state["competitive_result"] = process_competitive_data(_state["external_competitive"], reporting_df)
            print(f"[OK] Competitive: {len(_state['competitive_result'].get('recommendations',[]))} recs")
        if _state.get("external_events") is not None:
            _state["events_result"] = process_market_events(_state["external_events"], reporting_df)
            print(f"[OK] Events: {_state['events_result']['summary']['upcoming_events']} upcoming")
        if _state.get("external_trends") is not None:
            _state["trends_result"] = process_market_trends(_state["external_trends"], reporting_df)
            print(f"[OK] Trends: {_state['trends_result']['summary']['n_recommendations']} recs")
        
        # Merge external recs into smart recs
        if _state.get("smart_recs") and any([_state.get("competitive_result"), _state.get("events_result"), _state.get("trends_result")]):
            _state["smart_recs"] = merge_external_recommendations(
                _state["smart_recs"],
                _state.get("competitive_result"), _state.get("events_result"), _state.get("trends_result"))
            print(f"[OK] Merged recs: {len(_state['smart_recs'])} total")
    except Exception as e:
        print(f"[FAIL] External data: {e}")
    
    # Persist session
    try:
        save_session("default", _state, user_id=0)
        print("[OK] Session persisted to SQLite")
    except Exception as e:
        print(f"[WARN] Session persist failed: {e}")


# ═══════════════════════════════════════════════
#  BAYESIAN MMM — BACKGROUND FIT
# ═══════════════════════════════════════════════
#
# The Bayesian MMM is run in a background thread so the main
# /api/run-analysis request returns in ~5 seconds (frequentist path)
# instead of ~3 minutes (Bayesian). The UI polls /api/bayes-status
# and renders a "pending | running | ready" chip. Once ready, credible
# intervals on channel ROAS and response curves become available via
# /api/bayes-result.
#
# Fit scope: up to BAYES_MAX_CHANNELS channels (default 6) chosen by
# absolute spend. This keeps a single NUTS fit under ~3 minutes on
# Railway-grade hardware. Pitch channels (paid_search, social_paid,
# tv_national, events, email, direct_mail) are all in the top-spend
# list, so the priority selection happens naturally.
#
# Thread-safety: _state writes are atomic enough for our use (single
# dict key assignments). Python's GIL + the structure of dict writes
# means we don't need a lock for correctness here. We DO need to be
# careful to not MUTATE _state["bayes_status"] in place — always
# replace the whole dict — to avoid torn reads on the polling side.

import threading
import datetime

BAYES_MAX_CHANNELS = 6
BAYES_CHANNEL_WHITELIST = [
    # In priority order. The fit uses the intersection of this list with
    # the channels that are actually in the loaded data, capped at
    # BAYES_MAX_CHANNELS. Picks one channel per archetype so the pitch
    # story ("we handle all your channel types") lands.
    "paid_search", "social_paid", "tv_national", "events", "email", "direct_mail",
    # Fallbacks if any of the above aren't in the data
    "display", "video_youtube", "radio", "ooh", "call_center", "organic_search",
]


def _set_bayes_status(**updates):
    """Atomically update the bayes_status dict. Always replace the dict
    reference so concurrent readers see a consistent snapshot."""
    current = dict(_state.get("bayes_status") or {})
    current.update(updates)
    _state["bayes_status"] = current


def _bayes_subset_df(df):
    """Return the campaign dataframe restricted to the Bayesian fit channels."""
    present = set(df["channel"].unique())
    picks = [c for c in BAYES_CHANNEL_WHITELIST if c in present][:BAYES_MAX_CHANNELS]
    if len(picks) < 3:
        return None, picks
    return df[df["channel"].isin(picks)].copy(), picks


def _kickoff_bayesian_fit():
    """Spawn a daemon thread to run the Bayesian MMM fit. Idempotent:
    if a fit is already running, this is a no-op."""
    current_state = (_state.get("bayes_status") or {}).get("state")
    if current_state in ("pending", "running"):
        print(f"[bayes] Fit already in progress ({current_state}); skipping kickoff")
        return

    _set_bayes_status(
        state="pending",
        started_at=datetime.datetime.utcnow().isoformat() + "Z",
        finished_at=None,
        elapsed_s=None,
        r_hat_max=None,
        ess_min=None,
        message="Queued for background fit",
    )

    t = threading.Thread(target=_run_bayesian_fit_background, daemon=True, name="bayes-fit")
    t.start()


def _run_bayesian_fit_background():
    """Thread body: fit the Bayesian MMM, update state on completion.
    All errors are caught and turned into failed status rather than crashing."""
    import time as _time

    df = _state.get("campaign_data")
    if df is None:
        _set_bayes_status(state="failed", message="No campaign data loaded")
        return

    subset_df, picks = _bayes_subset_df(df)
    if subset_df is None:
        _set_bayes_status(
            state="failed",
            message=f"Only {len(picks)} channels available; Bayesian needs 3+",
        )
        return

    _set_bayes_status(
        state="running",
        n_channels=len(picks),
        message=f"Fitting {len(picks)} channels via PyMC NUTS",
    )
    t0 = _time.time()
    try:
        # Small-budget fit to stay within Railway timeouts. 300 draws × 2 chains
        # × 300 tune = enough for stable posterior summaries on 48 periods
        # and completes in ~90s on commodity hardware. More draws/chains only
        # tighten the HDIs slightly at significant time cost.
        result = run_mmm(
            subset_df, method="bayesian", n_draws=300, n_chains=2, n_tune=300
        )
        elapsed = _time.time() - t0
        diag = result.get("model_diagnostics", {}) or {}
        converged = bool(diag.get("converged"))
        r_hat_max = diag.get("r_hat_max")
        ess_min = diag.get("ess_min")

        if not converged:
            _set_bayes_status(
                state="non_converged",
                finished_at=datetime.datetime.utcnow().isoformat() + "Z",
                elapsed_s=round(elapsed, 1),
                r_hat_max=r_hat_max,
                ess_min=ess_min,
                message=(
                    f"Sampled {len(picks)} channels in {elapsed:.0f}s but did not converge "
                    f"(r-hat={r_hat_max}, ESS={ess_min}). Credible intervals hidden."
                ),
            )
            _state["bayes_result"] = None
            return

        _state["bayes_result"] = result
        _set_bayes_status(
            state="ready",
            finished_at=datetime.datetime.utcnow().isoformat() + "Z",
            elapsed_s=round(elapsed, 1),
            r_hat_max=r_hat_max,
            ess_min=ess_min,
            message=(
                f"Fit complete in {elapsed:.0f}s · r-hat {r_hat_max:.3f} · ESS {int(ess_min)}"
            ),
        )
        print(f"[bayes] Fit ready in {elapsed:.1f}s, r-hat={r_hat_max}, ESS={ess_min}")
    except Exception as e:
        elapsed = _time.time() - t0
        _set_bayes_status(
            state="failed",
            finished_at=datetime.datetime.utcnow().isoformat() + "Z",
            elapsed_s=round(elapsed, 1),
            message=f"Fit raised: {type(e).__name__}: {e}",
        )
        print(f"[bayes] Fit failed after {elapsed:.1f}s: {e}")


@app.get("/api/bayes-status")
def get_bayes_status():
    """Return the current Bayesian fit lifecycle state. Polled by the UI.

    Side effect: if the server has analyzed data but no Bayesian fit has
    been kicked off (state=="idle"), kick one off now. This handles the
    edge case where a session was restored from SQLite after a server
    restart — the analysis data is there but we never ran Bayesian for
    this process instance. Without this, the chip would stay "idle"
    forever and the pitch demo would show no Bayesian.
    """
    status = _state.get("bayes_status") or {}
    if status.get("state") == "idle" and _state.get("campaign_data") is not None:
        _kickoff_bayesian_fit()
        status = _state.get("bayes_status") or {}
    return _j(status)


@app.post("/api/bayes-refit")
def refit_bayesian():
    """Manually trigger a Bayesian fit. Useful for 'refresh' buttons in UI
    or for demo resets. No-ops if a fit is already in progress."""
    if _state.get("campaign_data") is None:
        raise HTTPException(400, "No data loaded")
    _kickoff_bayesian_fit()
    return _j(_state.get("bayes_status") or {})


@app.get("/api/bayes-result")
def get_bayes_result():
    """Return the Bayesian fit result. Returns 404 if not yet ready."""
    status = _state.get("bayes_status") or {}
    state = status.get("state")
    if state != "ready":
        raise HTTPException(
            404,
            f"Bayesian result not available (state={state}). Poll /api/bayes-status.",
        )
    return _j(_state.get("bayes_result") or {})


@app.post("/api/run-analysis")
def run_full_analysis(model_type: str = "power_law"):
    """Run all engines on current data. Accepts model_type: power_law or hill."""
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded")
    _state["_model_type"] = model_type
    _run_all_engines()
    # Fire the Bayesian MMM in the background so the request returns
    # immediately. The UI polls /api/bayes-status to see when it lands.
    _kickoff_bayesian_fit()
    return _j({
        "status": "complete",
        "model_type": model_type,
        "response_curves_channels": list(_state["curves"].keys()) if _state["curves"] else [],
        "recommendations_count": len(_state["diagnostics"]) if _state["diagnostics"] else 0,
        "total_value_at_risk": _state["pillars"].get("total_value_at_risk", 0) if _state["pillars"] else 0,
        "optimization_uplift": _state["optimization"].get("summary",{}).get("uplift_pct",0) if _state["optimization"] else 0,
    })


# ═══════════════════════════════════════════════
#  CURRENT STATE
# ═══════════════════════════════════════════════

@app.get("/api/data-readiness")
def get_data_readiness():
    """Show what data is available, which engines can run, and what needs more data."""
    if _state["data_split"] is None:
        raise HTTPException(400, "No data loaded")
    split_meta = _state["data_split"]
    # Re-validate
    split = split_data(_state["campaign_data"], reporting_months=12,
                       date_column="month" if "month" in _state["campaign_data"].columns else "date")
    readiness = validate_split(split)
    return _j({
        "periods": split_meta,
        "engine_readiness": readiness["engine_readiness"],
        "overall_ready": readiness["overall_ready"],
        "warnings": readiness["warnings"],
        "recommendation": (
            "Upload 3+ years of historical data for reliable MMM and forecasting. "
            "Current reporting period uses the most recent 12 months for ROI and diagnostics."
        ) if not readiness["overall_ready"] else "All engines have sufficient data.",
    })


@app.get("/api/current-state")
def get_current_state(attribution_model: str = "last_touch"):
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded")
    # Use REPORTING period (last 12 months) for current-state KPIs
    df = _state["reporting_data"] if _state["reporting_data"] is not None else _state["campaign_data"]
    
    total_spend = float(df["spend"].sum())
    total_revenue = float(df["revenue"].sum())
    total_conv = int(df["conversions"].sum())
    
    summary = {
        "total_spend": total_spend, "total_revenue": total_revenue,
        "roi": (total_revenue - total_spend) / max(total_spend, 1),
        "roas": total_revenue / max(total_spend, 1),
        "total_conversions": total_conv,
        "cac": total_spend / max(total_conv, 1),
    }
    
    # Channel-campaign matrix
    matrix = df.groupby(["channel", "campaign", "channel_type"]).agg(
        spend=("spend","sum"), revenue=("revenue","sum"), impressions=("impressions","sum"),
        clicks=("clicks","sum"), leads=("leads","sum"), conversions=("conversions","sum"),
    ).reset_index()
    matrix["roi"] = (matrix["revenue"] - matrix["spend"]) / matrix["spend"].clip(lower=1)
    matrix["roas"] = matrix["revenue"] / matrix["spend"].clip(lower=1)
    matrix["cac"] = matrix["spend"] / matrix["conversions"].clip(lower=1)
    
    # Monthly trends (use month if available, else date)
    time_col = "month" if "month" in df.columns else "date"
    trends = df.groupby(time_col).agg(
        spend=("spend","sum"), revenue=("revenue","sum"), conversions=("conversions","sum"),
    ).reset_index()
    trends.rename(columns={time_col: "month"}, inplace=True)
    trends["roi"] = (trends["revenue"] - trends["spend"]) / trends["spend"].clip(lower=1)
    
    # Online vs offline
    split = df.groupby("channel_type").agg(spend=("spend","sum"), revenue=("revenue","sum")).reset_index()
    
    # Attribution
    attr_data = None
    if _state["attribution_roi"] and attribution_model in _state["attribution_roi"]:
        attr_data = _state["attribution_roi"][attribution_model].to_dict(orient="records")
    
    return _j({"summary": summary, "channel_campaign_matrix": matrix.to_dict(orient="records"),
               "monthly_trends": trends.to_dict(orient="records"),
               "online_offline_split": split.to_dict(orient="records"),
               "attribution": attr_data, "attribution_model": attribution_model})


@app.get("/api/full-state")
def get_full_state():
    """
    Returns ALL data the frontend needs in a single call, shaped to match
    the frontend's internal data model. This is the primary integration endpoint.
    """
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded — call POST /api/load-mock-data first")
    
    df = _state["reporting_data"] if _state["reporting_data"] is not None else _state["campaign_data"]
    
    # Build rows array matching frontend shape
    col_map = {"channel":"ch","campaign":"camp","channel_type":"ct","impressions":"imps",
               "conversions":"conv","revenue":"rev","bounce_rate":"br",
               "avg_session_duration_sec":"sd","form_completion_rate":"fc","nps_score":"nps",
               "region":"reg","product":"prod"}
    rows = []
    for _, r in df.iterrows():
        row = {}
        for col in df.columns:
            key = col_map.get(col, col)
            val = r[col]
            if isinstance(val, (np.integer,)): val = int(val)
            elif isinstance(val, (np.floating,)): val = float(val)
            row[key] = val
        # Add ml (month label) from month
        m_str = str(r.get("month", ""))
        if "-" in m_str:
            try: row["ml"] = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][int(m_str.split("-")[1])]
            except: row["ml"] = m_str
        rows.append(row)
    
    # Build optimizer in frontend shape
    opt_data = None
    if _state["optimization"] and "summary" in _state["optimization"]:
        opt = _state["optimization"]
        opt_channels = [{"channel":c["channel"], "cS":round(c.get("current_spend",0)),
            "oS":round(c.get("optimized_spend",0)), "chg":round(c.get("change_pct",0),1),
            "cR":round(c.get("current_revenue",0)), "oR":round(c.get("optimized_revenue",0)),
            "rChg":round(c.get("revenue_delta",0)),
            "cROI":round(c.get("current_roi",0),3), "oROI":round(c.get("optimized_roi",0),3),
            "mROI":round(c.get("marginal_roi",0),4), "locked":c.get("locked",False)}
            for c in opt.get("channels",[])]
        sm = opt.get("summary",{})
        opt_summary = {"cRev":round(sm.get("current_revenue",0)),
            "oRev":round(sm.get("optimized_revenue",0)),
            "uplift":round(sm.get("uplift_pct",0),2),
            "cROI":round(sm.get("current_roi",0),3),
            "oROI":round(sm.get("optimized_roi",0),3)}
        opt_data = {"channels":opt_channels, "summary":opt_summary}
    
    # Build pillars in frontend shape
    pl_data = None
    if _state["pillars"]:
        p = _state["pillars"]
        leak = p.get("revenue_leakage",{})
        exp = p.get("experience_suppression",{})
        cost = p.get("avoidable_cost",{})
        pl_data = {
            "leak":{"total":leak.get("total_leakage",0),"pct":leak.get("leakage_pct",0),
                "byCh":[{"channel":c.get("channel",""),"leakage":c.get("leakage",0),"type":c.get("type","")} 
                    for c in leak.get("by_channel",[])]},
            "exp":{"total":exp.get("total_suppression",0),
                "items":[{"ch":i.get("channel",""),"camp":i.get("campaign",""),"cvr":i.get("cvr",0),
                    "sR":i.get("suppressed_revenue",0),"br":i.get("bounce_rate",0)} for i in exp.get("items",[])]},
            "cost":{"total":cost.get("total_avoidable_cost",0),
                "items":[{"ch":i.get("channel",""),"cac":i.get("cac",0),"av":i.get("avoidable_cost",0)} for i in cost.get("items",[])]},
            "totalRisk":p.get("total_value_at_risk",0)
        }
    
    # Build recs in frontend shape
    recs_data = []
    if _state["diagnostics"]:
        for r in _state["diagnostics"]:
            recs_data.append({"type":r.get("type",""),"ch":r.get("channel",""),
                "camp":r.get("campaign",""),"rationale":r.get("rationale",""),
                "action":r.get("action",""),"impact":r.get("impact",0),
                "conf":r.get("confidence","Medium"),"effort":r.get("effort","Medium"),
                "id":r.get("id",""),"priority":r.get("priority",0)})
    
    # Attribution (use pre-built dicts from engine run, includes markov)
    attr_data = _state.get("_attr_dicts", {})
    if not attr_data and _state["attribution"]:
        for model_name, model_data in _state["attribution"].items():
            if hasattr(model_data, "groupby"):
                attr_data[model_name] = model_data.groupby("channel")["attributed_revenue"].sum().to_dict()
            elif isinstance(model_data, dict):
                attr_data[model_name] = model_data
    
    # Build curves in frontend shape
    curves_data = {}
    if _state["curves"]:
        for ch, info in _state["curves"].items():
            if "error" in info: continue
            p = info.get("params",{})
            curves_data[ch] = {"a":p.get("a",1),"b":p.get("b",0.5),
                "avgSpend":info.get("current_avg_spend",0),"satSpend":info.get("saturation_spend",0),
                "mROI":info.get("marginal_roi",0),"hd":info.get("headroom_pct",0),
                "r2":info.get("diagnostics",{}).get("r_squared",0),
                "model":info.get("model","power_law"),
                "cp":info.get("curve_points",[])}
    
    tS = float(df["spend"].sum())
    
    return _j({
        "rows": rows,
        "opt": opt_data or {"channels":[],"summary":{"cRev":0,"oRev":0,"uplift":0,"cROI":0,"oROI":0}},
        "pl": pl_data or {"leak":{"total":0,"pct":0,"byCh":[]},"exp":{"total":0,"items":[]},"cost":{"total":0,"items":[]},"totalRisk":0},
        "attr": attr_data,
        "curves": curves_data,
        "tS": tS,
        "recs": recs_data,
        "smartRecs": _state.get("smart_recs") or [],
        "insights": _state.get("insights") or {},
        "qoqYoy": _state.get("qoq_yoy") or {},
        "channelTrends": _state.get("channel_trends") or {},
        "modelSelections": _state.get("model_selections") or {},
        "modelDiagnostics": {
            "response_curves": {"model": _state.get("_model_type","power_law"), "channels": len(curves_data), "avg_r2": round(sum(c.get("diagnostics",{}).get("r_squared",0) for c in (_state.get("curves") or {}).values() if "error" not in c) / max(len(curves_data),1), 3)},
            "mmm": {"method": (_state.get("mmm_result") or {}).get("method","not_run"), "r2": (_state.get("mmm_result") or {}).get("model_diagnostics",{}).get("r_squared",0)},
            "forecasting": {"method": "prophet" if _state.get("forecast") else "not_run"},
            "optimizer": {"converged": (_state.get("optimization") or {}).get("optimizer_info",{}).get("converged", True)},
        },
        "externalData": {
            "competitive": (_state.get("competitive_result") or {}).get("summary"),
            "events": (_state.get("events_result") or {}).get("summary"),
            "trends": (_state.get("trends_result") or {}).get("summary"),
            "shareOfVoice": (_state.get("competitive_result") or {}).get("share_of_voice"),
            "benchmarks": (_state.get("trends_result") or {}).get("benchmarks"),
            "costAdjustments": (_state.get("trends_result") or {}).get("cost_adjustments"),
            "eventCalendar": [e for e in ((_state.get("events_result") or {}).get("events") or []) if e.get("is_upcoming")],
            "categoryGrowth": (_state.get("trends_result") or {}).get("category_growth"),
        },
        "dataReadiness": _state.get("data_split"),
        "apiMode": True,
        "warnings": _get_data_warnings(),
    })


@app.get("/api/channels")
def list_channels():
    """
    List all channels present in the campaign data with their current
    spend and (if available) the optimizer's recommended action.

    Powers the Channel Detail picker dropdown and the default-channel
    resolution: when the user clicks "Channels" in the nav without a
    specific channel, the backend picks the highest-priority channel
    (largest absolute change from the optimizer).
    """
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded")
    df = _state["campaign_data"]

    # Build per-channel summary
    by_ch = df.groupby("channel").agg(
        spend=("spend", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    by_ch["roas"] = by_ch["revenue"] / by_ch["spend"].replace(0, 1)

    # Overlay the optimization action if we have one
    opt = _state.get("optimization") or {}
    opt_by_channel = {c.get("channel"): c for c in opt.get("channels", [])}

    channels = []
    for _, row in by_ch.iterrows():
        ch = str(row["channel"])
        ch_opt = opt_by_channel.get(ch, {})
        current = float(ch_opt.get("current_spend", row["spend"]))
        optimized = float(ch_opt.get("optimized_spend", row["spend"]))
        change = optimized - current
        # Action is based on the *direction* of change, not the raw
        # threshold (the earlier version had a sign bug: `change > current * 0.02`
        # is asymmetric in the wrong way because change can be negative).
        if current > 0 and abs(change) / current > 0.02:
            action = "increase" if change > 0 else "decrease"
        else:
            action = "hold"
        channels.append({
            "channel": ch,
            "channel_display": ch.replace("_", " ").title(),
            # current_spend uses the optimizer's basis (same as deep-dive's
            # summary_stats and the Plan screen). Raw `row["spend"]` is the
            # unnormalized historical sum which can be 4x larger for 4-year
            # mock data. Keeping one consistent anchor across the product.
            "current_spend": round(current, 0),
            # Revenue stays as historical aggregate proportionally scaled
            # to match the spend basis.
            "revenue": round(float(row["revenue"]) * (current / max(float(row["spend"]), 1)), 0),
            "roas": round(float(row["roas"]), 2),
            "optimal_spend": round(optimized, 0),
            "change_dollars": round(change, 0),
            "action": action,
        })

    # Sort by absolute change (largest movers first — that's what the
    # default-channel picker uses)
    channels.sort(key=lambda c: abs(c["change_dollars"]), reverse=True)

    return _j({
        "channels": channels,
        "default": channels[0]["channel"] if channels else None,
    })


@app.get("/api/market-context")
def get_market_context():
    """
    Full market-context payload for the dedicated Market Context screen.

    Aggregates what the three external-data engines have produced:
      - events_result: upcoming events timeline + near-term recommendations
      - trends_result: cost-trend snapshots, benchmarks, category growth
      - competitive_result: share-of-voice per channel, pressure index,
        at-risk channels

    The sidebar card on /api/diagnosis surfaces a trimmed version of this
    (up to 6 events, 2 alerts). This endpoint returns the full data for
    the dedicated screen: every event, all trends, per-channel SOV
    breakdown, plus narrative summaries.

    Empty sections are returned as empty arrays so the frontend can
    render empty states gracefully rather than 404'ing when a user
    hasn't uploaded a given file yet.
    """
    events_result = _state.get("events_result") or {}
    trends_result = _state.get("trends_result") or {}
    competitive_result = _state.get("competitive_result") or {}

    sources_loaded = []
    if _state.get("external_events") is not None:
        sources_loaded.append("events")
    if _state.get("external_trends") is not None:
        sources_loaded.append("trends")
    if _state.get("external_competitive") is not None:
        sources_loaded.append("competitive")

    # Events: full timeline sorted by date
    all_events = sorted(
        events_result.get("events", []),
        key=lambda e: e.get("days_away", 999_999)
    )

    # Trends: restructure by metric type for the UI. The engine returns
    # cost_adjustments keyed by channel; we flatten to a list and also
    # pull out benchmarks + category_growth.
    cost_adjustments = []
    for ch, adj in (trends_result.get("cost_adjustments") or {}).items():
        cost_adjustments.append({
            "channel": ch,
            "channel_display": ch.replace("_", " ").title(),
            **(adj if isinstance(adj, dict) else {}),
        })
    cost_adjustments.sort(
        key=lambda c: abs(c.get("yoy_change_pct", 0) or 0),
        reverse=True
    )

    # Competitive: flatten share_of_voice per channel into a list
    sov_list = []
    for ch, sov in (competitive_result.get("share_of_voice") or {}).items():
        if not isinstance(sov, dict):
            continue
        sov_list.append({
            "channel": ch,
            "channel_display": ch.replace("_", " ").title(),
            "our_spend": sov.get("our_spend", 0),
            "competitor_spend": sov.get("competitor_spend", 0),
            "total_market": sov.get("total_market", 0),
            "share_of_voice": sov.get("share_of_voice", 0),
            "competitive_pressure_index": sov.get("competitive_pressure_index", 0),
        })
    # Most competitive pressure first (lowest SOV = under pressure)
    sov_list.sort(key=lambda r: r.get("share_of_voice", 1.0))

    # Headline summary — a single sentence framing the state of the
    # market context overall. Dynamic based on what's loaded.
    headline_bits = []
    if "events" in sources_loaded:
        upcoming = events_result.get("summary", {}).get("upcoming_events", 0)
        if upcoming:
            headline_bits.append(f"{upcoming} upcoming event{'s' if upcoming != 1 else ''}")
    if "trends" in sources_loaded:
        n_adj = len(cost_adjustments)
        if n_adj:
            headline_bits.append(f"{n_adj} channel{'s' if n_adj != 1 else ''} with cost trend signals")
    if "competitive" in sources_loaded:
        at_risk = competitive_result.get("summary", {}).get("at_risk_channels", 0)
        n_ch = competitive_result.get("summary", {}).get("n_channels_tracked", 0)
        if n_ch:
            headline_bits.append(f"{n_ch} channels vs {competitive_result.get('summary', {}).get('n_competitors', '?')} competitors")

    if headline_bits:
        headline = "Tracking " + ", ".join(headline_bits) + "."
    else:
        headline = "No external data uploaded yet. Upload events, trends, or competitive data on the Workspace screen to populate this view."

    return _j({
        "headline": headline,
        "data_sources_loaded": sources_loaded,
        "events": {
            "all": all_events,
            "summary": events_result.get("summary", {}),
            "recommendations": events_result.get("recommendations", []),
        },
        "trends": {
            "cost_adjustments": cost_adjustments,
            "benchmarks": trends_result.get("benchmarks", {}),
            "category_growth": trends_result.get("category_growth", {}),
            "search_interest": trends_result.get("search_interest", {}),
            "recommendations": trends_result.get("recommendations", []),
            "summary": trends_result.get("summary", {}),
        },
        "competitive": {
            "share_of_voice": sov_list,
            "competitive_pressure": competitive_result.get("competitive_pressure", {}),
            "recommendations": competitive_result.get("recommendations", []),
            "summary": competitive_result.get("summary", {}),
        },
    })


# ═══════════════════════════════════════════════
#  ENGAGEMENTS
# ═══════════════════════════════════════════════
#
# Engagements represent consulting projects — a client + period + status.
# The current implementation is DELIBERATELY lightweight:
#
#   - State is in-memory only. Deleting an engagement is ephemeral; a
#     restart reseeds the defaults.
#   - All engagements share the same analysis data (mock data). Switching
#     "active engagement" is a UI-only change; Diagnosis/Plan etc. render
#     the same numbers regardless.
#   - No per-engagement data uploads, no per-engagement authorization.
#
# This is enough for the pitch ("we track multiple engagements") without
# the full multi-tenant data-isolation lift that proper engagements
# require. That lift — separate SQLite table, engagement_id FK on every
# data row, per-engagement auth checks — is explicitly deferred and
# documented.

def _seed_engagements():
    """Return a seeded list of engagements. Called lazily."""
    import datetime
    today = datetime.date.today()
    return [
        {
            "id": "acme-fy2025",
            "client": "Acme Retail",
            "engagement_name": "Acme Retail FY2025 Budget Review",
            "period": "Jan 2025 – Dec 2025",
            "status": "active",
            "owner": "Sarah Rahman",
            "last_updated": today.isoformat(),
            "summary": "Full portfolio review with MMM + attribution + scenario planning.",
        },
        {
            "id": "contoso-q3",
            "client": "Contoso Foods",
            "engagement_name": "Contoso Foods Q3 2025 Scenarios",
            "period": "Jul – Sep 2025",
            "status": "in_review",
            "owner": "Sarah Rahman",
            "last_updated": (today - datetime.timedelta(days=6)).isoformat(),
            "summary": "Budget scenarios for Q3 holiday push.",
        },
        {
            "id": "initech-audit",
            "client": "Initech",
            "engagement_name": "Initech Media Mix Audit",
            "period": "Mar – May 2025",
            "status": "wrapped",
            "owner": "Marcus Li",
            "last_updated": (today - datetime.timedelta(days=45)).isoformat(),
            "summary": "One-time audit of last 18 months of media investment.",
        },
        {
            "id": "umbrella-plan",
            "client": "Umbrella Corp",
            "engagement_name": "Umbrella FY26 Budget Plan",
            "period": "Sep – Nov 2025",
            "status": "active",
            "owner": "Sarah Rahman",
            "last_updated": (today - datetime.timedelta(days=2)).isoformat(),
            "summary": "Building the FY26 marketing plan from internal targets.",
        },
    ]


def _ensure_engagements_seeded():
    if _state.get("engagements") is None:
        _state["engagements"] = _seed_engagements()


@app.get("/api/engagements")
def list_engagements():
    """List all engagements plus the active engagement id."""
    _ensure_engagements_seeded()
    return _j({
        "engagements": _state["engagements"],
        "active_engagement_id": _state.get("active_engagement_id"),
    })


@app.post("/api/engagements")
def create_engagement(payload: dict = Body(...)):
    """
    Create a new engagement. Accepts client, engagement_name, period, status.
    Validates minimally; this is demo-grade CRUD.
    """
    _ensure_engagements_seeded()
    client = str(payload.get("client", "")).strip()
    name = str(payload.get("engagement_name", "")).strip()
    period = str(payload.get("period", "")).strip()
    status = str(payload.get("status", "active")).strip()
    if not client or not name or not period:
        raise HTTPException(400, "client, engagement_name, and period are required")
    if status not in ("active", "in_review", "wrapped"):
        status = "active"

    # ID generation: slug from client + simple increment on collision
    import re, datetime
    base_slug = re.sub(r"[^a-z0-9]+", "-", client.lower()).strip("-")
    suffix = 1
    new_id = base_slug or "engagement"
    existing_ids = {e["id"] for e in _state["engagements"]}
    while new_id in existing_ids:
        suffix += 1
        new_id = f"{base_slug}-{suffix}"

    new_engagement = {
        "id": new_id,
        "client": client,
        "engagement_name": name,
        "period": period,
        "status": status,
        "owner": payload.get("owner") or "Sarah Rahman",
        "last_updated": datetime.date.today().isoformat(),
        "summary": payload.get("summary") or "",
    }
    _state["engagements"].append(new_engagement)
    return _j({"engagement": new_engagement})


@app.delete("/api/engagements/{engagement_id}")
def delete_engagement(engagement_id: str):
    """Delete an engagement. Refuses to delete the active one."""
    _ensure_engagements_seeded()
    if engagement_id == _state.get("active_engagement_id"):
        raise HTTPException(
            400,
            "Cannot delete the currently-active engagement. Switch active first.",
        )
    before = len(_state["engagements"])
    _state["engagements"] = [e for e in _state["engagements"] if e["id"] != engagement_id]
    if len(_state["engagements"]) == before:
        raise HTTPException(404, f"Engagement '{engagement_id}' not found")
    return _j({"status": "deleted", "engagement_id": engagement_id})


@app.post("/api/engagements/{engagement_id}/activate")
def activate_engagement(engagement_id: str):
    """Mark an engagement as active. Does NOT reload data — the demo
    uses the same mock data across all engagements."""
    _ensure_engagements_seeded()
    ids = {e["id"] for e in _state["engagements"]}
    if engagement_id not in ids:
        raise HTTPException(404, f"Engagement '{engagement_id}' not found")
    _state["active_engagement_id"] = engagement_id
    return _j({"status": "ok", "active_engagement_id": engagement_id})


@app.get("/api/deep-dive/{channel}")
def get_channel_deep_dive(channel: str):
    """
    Per-channel drill-down for Channel Detail screen.

    Extended in v18h to include:
      - optimization: the plan's optimized spend for this channel (the
        green marker on the response curve in mockup Image 5). Computed
        from the cached optimizer result rather than re-running, so
        these numbers match the Plan screen exactly.
      - campaigns: campaign-level breakdown (rows for the table at the
        bottom of the Channel Detail screen per the mockup).
      - summary_stats: KPI row values (current_spend total, attributed
        revenue, channel ROAS, confidence tier) so the frontend doesn't
        have to re-aggregate from monthly_trend.
    """
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    df = _state["campaign_data"]
    ch_data = df[df["channel"] == channel]
    if len(ch_data) == 0: raise HTTPException(404, f"Channel '{channel}' not found")

    trend = ch_data.groupby("month").agg(spend=("spend","sum"),revenue=("revenue","sum"),conversions=("conversions","sum"),leads=("leads","sum")).reset_index()
    trend["roi"] = (trend["revenue"] - trend["spend"]) / trend["spend"]
    regional = ch_data.groupby("region").agg(spend=("spend","sum"),revenue=("revenue","sum"),conversions=("conversions","sum")).reset_index()
    regional["roi"] = (regional["revenue"] - regional["spend"]) / regional["spend"]
    funnel = {s: int(ch_data[s].sum()) for s in ["impressions","clicks","leads","mqls","sqls","conversions"]}
    cx = {"avg_bounce_rate":float(ch_data["bounce_rate"].mean()),"avg_session_duration":float(ch_data["avg_session_duration_sec"].mean()),
          "avg_form_completion":float(ch_data["form_completion_rate"].mean()),"avg_nps":float(ch_data["nps_score"].mean())}
    curve_data = _state["curves"].get(channel) if _state["curves"] else None

    # Historical aggregates from raw campaign data
    total_spend = float(ch_data["spend"].sum())
    total_revenue = float(ch_data["revenue"].sum())

    # Optimization context — which spend does the plan want for this channel?
    # From the cached optimizer result so these numbers match Plan.
    optimization = None
    opt = _state.get("optimization") or {}
    for ch_opt in opt.get("channels", []):
        if ch_opt.get("channel") == channel:
            current_spend = float(ch_opt.get("current_spend", total_spend))
            optimal_spend = float(ch_opt.get("optimized_spend", total_spend))
            optimization = {
                "current_spend": round(current_spend, 0),
                "optimal_spend": round(optimal_spend, 0),
                "change_pct": round((optimal_spend - current_spend) / max(current_spend, 1) * 100, 1),
                "action": "increase" if optimal_spend > current_spend * 1.02
                          else "decrease" if optimal_spend < current_spend * 0.98
                          else "hold",
            }
            break

    # KPI row values. Important: current_spend uses the optimizer's
    # normalized basis (the same number the Plan screen shows for this
    # channel) rather than the raw sum of monthly_trend rows. The
    # optimizer operates on annualized spend; the raw monthly data
    # covers the full history, which for 4 years of mock data produces
    # a 4x-larger number. Using two different anchors here would make
    # users lose trust ("Plan said $8M, Channel Detail says $34M —
    # which is it?"). Source of truth = the optimizer.
    display_current_spend = optimization["current_spend"] if optimization else total_spend
    # Revenue uses a proportional slice matching the spend basis so ROAS
    # stays internally consistent (revenue/spend). If we kept the raw
    # 4-year revenue total with 1-year-equivalent spend, the ROAS KPI
    # would be wildly wrong.
    if optimization and total_spend > 0:
        revenue_scale = display_current_spend / total_spend
    else:
        revenue_scale = 1.0
    display_revenue = total_revenue * revenue_scale
    display_roas = display_revenue / max(display_current_spend, 1)

    # Campaign-level breakdown — one row per distinct campaign in the data.
    # Uses whichever column name the mock data happens to have; older data
    # used "camp", newer "campaign", so we fall back gracefully.
    campaign_col = "campaign" if "campaign" in ch_data.columns else ("camp" if "camp" in ch_data.columns else None)
    campaigns = []
    if campaign_col:
        # Aggregate across campaign-level data
        agg_args = {
            "spend": ("spend", "sum"),
            "revenue": ("revenue", "sum"),
            "conversions": ("conversions", "sum"),
        }
        # Add clicks/impressions if available for CTR/CVR
        if "clicks" in ch_data.columns:
            agg_args["clicks"] = ("clicks", "sum")
        if "impressions" in ch_data.columns:
            agg_args["impressions"] = ("impressions", "sum")
        # Offline-specific metrics. These are 0 for digital channels so the
        # sum will also be 0 — the frontend conditionally renders based on
        # the channel's attribution_basis rather than presence of data.
        for col in ("grps", "reach", "store_visits", "calls_generated",
                    "event_attendees", "dealer_enquiries"):
            if col in ch_data.columns:
                # reach is "max over the period" not "sum" — summing monthly
                # reach double-counts the same viewers. For the others, sum
                # is the right aggregation.
                agg_method = "mean" if col == "reach" else "sum"
                agg_args[col] = (col, agg_method)

        by_camp = ch_data.groupby(campaign_col).agg(**agg_args).reset_index()
        by_camp["roas"] = by_camp["revenue"] / by_camp["spend"].replace(0, 1)
        by_camp = by_camp.sort_values("spend", ascending=False).head(20)

        # Channel-level totals for share calculations
        ch_total_spend = float(ch_data["spend"].sum())
        ch_total_revenue = float(ch_data["revenue"].sum())

        # QoQ trend: compare last quarter vs prior quarter per campaign.
        # Requires the date column to be parseable.
        qoq_trend = {}
        sparkline_data = {}
        try:
            ch_data_dated = ch_data.copy()
            ch_data_dated["date"] = pd.to_datetime(ch_data_dated["date"], errors="coerce")
            ch_data_dated = ch_data_dated.dropna(subset=["date"])
            if len(ch_data_dated) > 0:
                max_date = ch_data_dated["date"].max()
                # Last quarter = last 90 days; prior = 91-180 days ago
                last_q = ch_data_dated[ch_data_dated["date"] > (max_date - pd.Timedelta(days=90))]
                prior_q = ch_data_dated[
                    (ch_data_dated["date"] <= (max_date - pd.Timedelta(days=90))) &
                    (ch_data_dated["date"] > (max_date - pd.Timedelta(days=180)))
                ]
                for camp in by_camp[campaign_col]:
                    last_rev = float(last_q[last_q[campaign_col] == camp]["revenue"].sum())
                    prior_rev = float(prior_q[prior_q[campaign_col] == camp]["revenue"].sum())
                    if prior_rev > 0:
                        pct = (last_rev - prior_rev) / prior_rev * 100
                        qoq_trend[camp] = {
                            "pct": round(pct, 1),
                            "direction": "up" if pct > 2 else "down" if pct < -2 else "flat",
                        }
                    else:
                        qoq_trend[camp] = {"pct": 0, "direction": "flat"}

                # Build 12-month revenue sparklines per campaign
                ch_data_dated["month"] = ch_data_dated["date"].dt.to_period("M").astype(str)
                last_12 = sorted(ch_data_dated["month"].unique())[-12:]
                for camp in by_camp[campaign_col]:
                    camp_monthly = ch_data_dated[ch_data_dated[campaign_col] == camp].groupby("month")["revenue"].sum()
                    sparkline_data[camp] = [
                        {"month": m, "revenue": round(float(camp_monthly.get(m, 0)), 0)}
                        for m in last_12
                    ]
        except Exception:
            pass

        for _, row in by_camp.iterrows():
            camp_name = str(row[campaign_col])
            spend_val = float(row["spend"])
            revenue_val = float(row["revenue"])
            conv_val = int(row["conversions"])
            clicks_val = float(row.get("clicks", 0)) if "clicks" in row.index else 0
            impr_val = float(row.get("impressions", 0)) if "impressions" in row.index else 0
            roas = float(row["roas"])

            cpa = (spend_val / conv_val) if conv_val > 0 else None
            ctr = (clicks_val / impr_val * 100) if impr_val > 0 else None
            cvr = (conv_val / clicks_val * 100) if clicks_val > 0 else None
            spend_share = (spend_val / ch_total_spend * 100) if ch_total_spend > 0 else 0
            revenue_share = (revenue_val / ch_total_revenue * 100) if ch_total_revenue > 0 else 0

            # Per-campaign recommendation — decisive text based on metrics
            # rather than inheriting the channel-level action uniformly.
            # Thresholds are gentle by design: "Hold" should be the
            # minority outcome when something stands out, not the default.
            recommendation = "Hold"
            camp_trend = qoq_trend.get(camp_name, {})

            # Find best + worst performing campaign in this channel for
            # relative comparisons
            best_roas = by_camp["roas"].max() if len(by_camp) > 1 else roas
            worst_roas = by_camp["roas"].min() if len(by_camp) > 1 else roas

            if camp_trend.get("direction") == "down" and camp_trend.get("pct", 0) < -10:
                recommendation = "Investigate drop"
            elif cvr is not None and cvr < 0.3 and ctr is not None and ctr > 2:
                recommendation = "Review landing page"
            elif roas >= best_roas * 0.95 and spend_share < revenue_share:
                # Top-tier ROAS and under-indexed on spend share
                recommendation = "Scale"
            elif roas <= worst_roas * 1.1 and spend_share > revenue_share * 1.1:
                # Worst in class and over-indexed — reduce
                recommendation = "Reduce"
            elif roas < 2.0:
                recommendation = "Reduce"
            elif spend_share > revenue_share * 1.15:
                recommendation = "Rebalance down"
            elif spend_share < revenue_share * 0.9 and roas >= 3.0:
                recommendation = "Increase share"
            else:
                recommendation = "Hold"

            campaigns.append({
                "campaign": camp_name,
                "spend": round(spend_val, 0),
                "revenue": round(revenue_val, 0),
                "roas": round(roas, 2),
                "conversions": conv_val,
                "cpa": round(cpa, 0) if cpa is not None else None,
                "ctr_pct": round(ctr, 2) if ctr is not None else None,
                "cvr_pct": round(cvr, 2) if cvr is not None else None,
                "spend_share_pct": round(spend_share, 1),
                "revenue_share_pct": round(revenue_share, 1),
                "qoq_trend": camp_trend,
                "sparkline": sparkline_data.get(camp_name, []),
                "recommendation": recommendation,
                # Offline-specific metrics — the frontend only shows these
                # when the channel's attribution_basis is reach or direct_response.
                "grps": round(float(row.get("grps", 0) or 0), 0),
                "reach": int(row.get("reach", 0) or 0),
                "store_visits": int(row.get("store_visits", 0) or 0),
                "calls_generated": int(row.get("calls_generated", 0) or 0),
                "event_attendees": int(row.get("event_attendees", 0) or 0),
                "dealer_enquiries": int(row.get("dealer_enquiries", 0) or 0),
            })

    # Confidence tier for the KPI card — from the curve diagnostics if
    # available, otherwise derived from R² and data point count.
    confidence_tier = "Directional"
    if curve_data and "diagnostics" in curve_data:
        diag = curve_data["diagnostics"]
        # Engine returns "High"/"Medium"/"Low"/"Inconclusive" — normalize
        raw = diag.get("confidence", "Directional")
        confidence_tier = raw if raw in ("High", "Directional", "Inconclusive") else \
                         ("High" if raw == "High" else
                          "Inconclusive" if raw in ("Low", "Inconclusive") else
                          "Directional")

    # Curve data fix: the MMM engine samples curve_points at a monthly-spend
    # basis (x_max = max(monthly_spend) * 1.8). The optimizer's current_spend
    # and optimal_spend are ANNUALIZED (×12). Result: the dots plot at
    # ~$10M but the curve ends at ~$5M, making them look disconnected
    # and the curve look "clipped." Re-sample the curve here to cover
    # enough range for the dots to sit ON the curve.
    if curve_data and optimization and "params" in curve_data:
        import numpy as np
        max_dot_spend = max(optimization["current_spend"],
                            optimization["optimal_spend"])
        # Extend to 1.3x beyond the farthest dot so there's headroom
        # past the optimal marker without the curve dying at the dot.
        target_xmax = max_dot_spend * 1.3
        existing_xmax = curve_data["curve_points"][-1]["spend"] if curve_data["curve_points"] else 0

        if target_xmax > existing_xmax * 1.05:  # only resample if meaningfully different
            params = curve_data["params"]
            model = curve_data.get("model", "power_law")
            a = params.get("a", 0)
            b = params.get("b", 0.5)
            if model == "power_law":
                # power_law: revenue = a * spend^b
                curve_data = dict(curve_data)  # don't mutate cache
                curve_data["curve_points"] = [
                    {"spend": round(float(s), 0),
                     "revenue": round(float(a * (s ** b)) if s > 0 else 0, 0)}
                    for s in np.linspace(0, target_xmax, 60)
                ]
            elif model == "hill":
                K = params.get("K", 1)
                # hill: revenue = a * (spend^b / (K^b + spend^b))
                curve_data = dict(curve_data)
                curve_data["curve_points"] = [
                    {"spend": round(float(s), 0),
                     "revenue": round(float(a * ((s**b) / ((K**b) + (s**b)))) if s > 0 else 0, 0)}
                    for s in np.linspace(0, target_xmax, 60)
                ]

    # Channel taxonomy + honest framing for offline channels.
    # Pulled from the channel-data rows (every row carries the same
    # attribution_basis/primary_metric for a given channel).
    attribution_basis = "click"
    primary_metric = "clicks"
    channel_type = "online"
    if "attribution_basis" in ch_data.columns and len(ch_data) > 0:
        attribution_basis = str(ch_data["attribution_basis"].iloc[0])
    if "primary_metric" in ch_data.columns and len(ch_data) > 0:
        primary_metric = str(ch_data["primary_metric"].iloc[0])
    if "channel_type" in ch_data.columns and len(ch_data) > 0:
        channel_type = str(ch_data["channel_type"].iloc[0])

    # Aggregate offline metrics at the channel level for KPI display
    channel_offline_agg = {}
    for col in ("grps", "calls_generated", "event_attendees",
                "dealer_enquiries", "store_visits"):
        if col in ch_data.columns:
            total = float(ch_data[col].sum())
            if total > 0:
                channel_offline_agg[col] = int(total)
    # Reach: use the mean monthly reach (not sum — that double-counts)
    if "reach" in ch_data.columns:
        avg_reach = float(ch_data["reach"].mean())
        if avg_reach > 0:
            channel_offline_agg["avg_monthly_reach"] = int(avg_reach)

    # Honest caveat text for non-click channels. This is shown as a
    # banner on the Channel Detail screen — better to signal the
    # limitation up-front than let users think "CTR 0.15%" is a real
    # performance metric for TV.
    offline_notes = None
    if attribution_basis == "reach":
        offline_notes = {
            "kind": "reach_based",
            "headline": f"{channel.replace('_',' ').title()} uses a reach-based attribution model",
            "body": (
                f"This channel doesn't have click-level tracking. The primary "
                f"measurement unit is {primary_metric} — GRPs for broadcast, "
                f"reach for OOH. Revenue attribution here is derived from "
                f"modeled lift rather than direct conversion tracking. "
                f"Click/CTR/CVR columns are hidden because they aren't "
                f"meaningful for this channel."
            ),
        }
    elif attribution_basis == "direct_response":
        offline_notes = {
            "kind": "direct_response",
            "headline": f"{channel.replace('_',' ').title()} uses direct-response attribution",
            "body": (
                f"Primary measurement is {primary_metric.replace('_',' ')}. "
                f"These are inbound responses tied directly to the channel — "
                f"calls for call center, attendees for events, enquiries for "
                f"direct mail. Click metrics are not tracked."
            ),
        }

    # Adstock profile for this channel — surface the model's decay treatment
    # so the UI can explain why broadcast and digital are handled differently.
    # This is light-touch: just echo what the channel-aware fitter decided.
    # Actual adstock diagnostics (decay, carryover %) are on /api/adstock.
    adstock_profile = None
    try:
        from engines.adstock import _channel_adstock_profile
        _ap = _channel_adstock_profile(channel, attribution_basis)
        adstock_profile = {
            "type": _ap["adstock_type"],
            "expected_carryover_pct": _ap["expected_carryover_pct"],
        }
    except Exception:
        pass

    return _j({
        "channel": channel,
        "channel_display": channel.replace("_", " ").title(),
        "channel_meta": {
            "channel_type": channel_type,
            "attribution_basis": attribution_basis,
            "primary_metric": primary_metric,
            "offline_aggregates": channel_offline_agg,
            "offline_notes": offline_notes,
            "adstock_profile": adstock_profile,
        },
        "monthly_trend": trend.to_dict(orient="records"),
        "regional_breakdown": regional.to_dict(orient="records"),
        "funnel": funnel,
        "cx_signals": cx,
        "response_curve": curve_data,
        "optimization": optimization,
        "campaigns": campaigns,
        "summary_stats": {
            "current_spend": round(display_current_spend, 0),
            "attributed_revenue": round(display_revenue, 0),
            "channel_roas": round(display_roas, 2),
            "confidence_tier": confidence_tier,
        },
    })


# ═══════════════════════════════════════════════
#  ANALYSIS ENDPOINTS
# ═══════════════════════════════════════════════

@app.get("/api/validation")
def get_validation():
    if _state["validation"] is None: raise HTTPException(400, "No data loaded")
    return _j(_state["validation"])

@app.get("/api/response-curves")
def get_response_curves():
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    return _j(_state["curves"])

@app.get("/api/recommendations")
def get_recommendations():
    _ensure_analysis()
    if _state["diagnostics"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    return _j(_state["diagnostics"])

@app.post("/api/optimize")
def run_optimization(
    total_budget: Optional[float] = None,
    objective: str = "balanced",
    model_type: str = "power_law",
    weight_revenue: float = 0.4,
    weight_roi: float = 0.3,
    weight_leakage: float = 0.15,
    weight_cost: float = 0.15,
):
    """Run optimization with custom objective, weights, and model type."""
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    
    # Re-fit curves if model type changed
    if model_type != _state.get("_model_type", "power_law"):
        _state["_model_type"] = model_type
        training_df = _state.get("training_data")
        if training_df is None: training_df = _state["campaign_data"]
        training_df = _normalize_date_columns(training_df)
        _state["curves"] = fit_response_curves(training_df, model_type=model_type)
    
    if total_budget is None: total_budget = float(_state["campaign_data"]["spend"].sum())
    weights = {"revenue": weight_revenue, "roi": weight_roi, "leakage": weight_leakage, "cost": weight_cost}
    result = optimize_budget(_state["curves"], total_budget, objective=objective, objective_weights=weights)
    _state["optimization"] = result
    reporting_df = _state.get("reporting_data")
    if reporting_df is None: reporting_df = _state["campaign_data"]
    _state["pillars"] = run_three_pillars(reporting_df, result)
    return _j(result)

@app.post("/api/model-selections")
def update_model_selections(
    attribution: str = "markov",
    response_curves: str = "auto",
    mmm: str = "auto",
    forecasting: str = "prophet",
    optimizer: str = "slsqp",
):
    """Update model selections and re-run full engine chain. Auto-triggers on model change."""
    _ensure_analysis()
    _state["model_selections"] = {
        "attribution": attribution, "response_curves": response_curves,
        "mmm": mmm, "forecasting": forecasting, "optimizer": optimizer,
    }
    # Map response curve selection to _model_type
    rc_map = {"auto":"auto","power_law":"power_law","hill":"hill","growth":"power_law","saturation":"hill"}
    _state["_model_type"] = rc_map.get(response_curves, "auto")
    # Re-run all engines with new selections
    _run_all_engines()
    return _j({"status": "re-run complete", "model_selections": _state["model_selections"],
               "smart_recs_count": len(_state.get("smart_recs") or []),
               "insights_count": (_state.get("insights") or {}).get("generated_count", 0)})

@app.get("/api/insights")
def get_insights():
    """Get all narrative insights."""
    _ensure_analysis()
    return _j({
        "insights": _state.get("insights") or {},
        "smart_recs": _state.get("smart_recs") or [],
        "qoq_yoy": _state.get("qoq_yoy") or {},
        "channel_trends": _state.get("channel_trends") or {},
        "model_selections": _state.get("model_selections") or {},
    })

@app.get("/api/sensitivity")
def get_sensitivity(objective: str = "balanced"):
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    base_budget = float(_state["campaign_data"]["spend"].sum())
    return _j(sensitivity_analysis(_state["curves"], base_budget, objective))

@app.get("/api/pillars")
def get_pillars():
    _ensure_analysis()
    if _state["pillars"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    return _j(_state["pillars"])

@app.get("/api/business-case")
def get_business_case():
    if not all([_state["optimization"], _state["pillars"], _state["diagnostics"]]):
        raise HTTPException(400, "Run full analysis first")
    opt = _state["optimization"]; pillars = _state["pillars"]; recs = _state["diagnostics"]
    return _j({
        "optimization_summary": opt.get("summary", {}),
        "value_at_risk": pillars.get("total_value_at_risk", 0),
        "correction_potential": pillars.get("correction_potential", {}),
        "top_recommendations": recs[:5] if isinstance(recs, list) else [],
        "implementation_phases": [
            {"phase": "Immediate (0-30 days)", "actions": [r for r in recs if r.get("effort") == "Low"][:3]},
            {"phase": "Short-term (30-90 days)", "actions": [r for r in recs if r.get("effort") == "Medium"][:3]},
            {"phase": "Strategic (90+ days)", "actions": [r for r in recs if r.get("effort") == "High"][:3]},
        ] if isinstance(recs, list) else [],
    })

@app.get("/api/diagnosis")
def get_diagnosis(view: str = "client", engagement_id: str = "default"):
    """
    Single-call payload for the Diagnosis screen.

    Query params:
      view: "client" (default) or "editor". Client view filters suppressed
            findings and applies rewrites transparently. Editor view returns
            all findings with suppression/rewrite metadata attached so the
            editor UI can render controls.
      engagement_id: overrides keyspace. Always "default" in v18a.

    Returns a flat dict with:
      - headline_paragraph: generated 2-3 sentence diagnosis
      - kpis: portfolio_roas, value_at_risk, plan_confidence (with tones)
      - findings: ranked list of 3-5 finding cards, each with stable `key`
      - industry_context: benchmarks overlay (if external data uploaded)
      - methodology: engines that contributed, for trust/reference
      - data_coverage: scope metadata
      - ey_overrides: editor overlay metadata — engagement_id, view, counts

    Template-based narrative only (no LLM). Safe to cache between runs of
    the same analysis; regenerate when any underlying engine re-runs.
    """
    if view not in ("client", "editor"):
        raise HTTPException(400, f"Invalid view '{view}' — must be 'client' or 'editor'")
    _ensure_analysis()
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")

    from engines.narrative import generate_diagnosis
    df = _state["reporting_data"] if _state["reporting_data"] is not None else _state["campaign_data"]

    # Pull industry benchmarks from external-data upload if present
    ext = _state.get("trends_result") or {}
    bench = ext.get("benchmarks")

    result = generate_diagnosis(
        campaign_df=df,
        response_curves=_state.get("curves") or {},
        optimization=_state.get("optimization") or {},
        pillars=_state.get("pillars") or {},
        insights=_state.get("insights") or {},
        recommendations=_state.get("diagnostics") or [],
        mmm_result=_state.get("mmm_result"),
        industry_benchmarks=bench,
        engagement_id=engagement_id,
        view=view,
    )

    # Market snippet — interpretive cross-reference of market signals
    # against the findings. Only attached when external data is available;
    # UI hides the section when this is null.
    try:
        from engines.market_adjustments import generate_diagnosis_market_snippet
        market_snippet = generate_diagnosis_market_snippet(
            findings=result.get("findings") or [],
            events_result=_state.get("events_result"),
            trends_result=_state.get("trends_result"),
            competitive_result=_state.get("competitive_result"),
        )
        if market_snippet:
            market_snippet["_is_mock_data"] = bool(_state.get("_mock_market_data"))
            result["market_snippet"] = market_snippet
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to generate diagnosis market snippet: %s — continuing without.", e
        )

    # Enrich KPIs with QoQ deltas so the UI can show "▲ 0.4 vs last
    # quarter" under the Portfolio ROAS number (and equivalent for
    # the other KPI cards). The QoQ data was already computed during
    # run-analysis; we just surface the relevant slices here.
    qoq_state = _state.get("qoq_yoy") or {}
    qoq_portfolio = qoq_state.get("qoq") or {}
    pillars_state = _state.get("pillars") or {}

    kpis = result.get("kpis") or {}

    # Portfolio ROAS: QoQ change in roas
    if isinstance(kpis.get("portfolio_roas"), dict) and qoq_portfolio.get("roas"):
        roas_qoq = qoq_portfolio["roas"]
        pct = roas_qoq.get("change_pct", 0)
        direction = roas_qoq.get("direction", "flat")
        if direction == "up":
            kpis["portfolio_roas"]["delta_text"] = f"{abs(pct):.1f}% vs last quarter"
            kpis["portfolio_roas"]["delta_direction"] = "up"
        elif direction == "down":
            kpis["portfolio_roas"]["delta_text"] = f"{abs(pct):.1f}% vs last quarter"
            kpis["portfolio_roas"]["delta_direction"] = "down"
        else:
            kpis["portfolio_roas"]["delta_text"] = "Flat vs last quarter"
            kpis["portfolio_roas"]["delta_direction"] = "neutral"

    # Value at Risk: no true QoQ since pillars are snapshot. Instead
    # express as "% of attributable revenue" — the mockup shows
    # "13% of attributable revenue" as the context for this KPI.
    if isinstance(kpis.get("value_at_risk"), dict):
        risk = pillars_state.get("total_value_at_risk", 0)
        # Honestly bridge VaR vs optimizer plan_delta. When the optimizer
        # can only recover a fraction of total VaR via reallocation, say so.
        opt_summary = (_state.get("optimization") or {}).get("summary", {}) or {}
        plan_delta = opt_summary.get("revenue_uplift") or 0
        try:
            total_rev = float(df["revenue"].sum())
            pct_of_rev = (risk / total_rev * 100) if total_rev > 0 else 0
            if plan_delta > 0 and risk > plan_delta * 1.1:
                plan_delta_display = (
                    f"${plan_delta/1e6:.1f}M" if plan_delta >= 1e6
                    else f"${plan_delta/1e3:.0f}K"
                )
                kpis["value_at_risk"]["delta_text"] = (
                    f"{plan_delta_display} recoverable via reallocation"
                )
            else:
                kpis["value_at_risk"]["delta_text"] = "Recoverable via reallocation"
            kpis["value_at_risk"]["delta_direction"] = "down"
            kpis["value_at_risk"]["pct_of_revenue_display"] = f"{pct_of_rev:.1f}% of attributable revenue"
        except Exception:
            pass

    # Plan Confidence: surface model R² as the context (mockup shows
    # "Model R² = 0.87 · MAPE 6.2%" under the confidence KPI).
    if isinstance(kpis.get("plan_confidence"), dict):
        curves = _state.get("curves") or {}
        # Average R² across channels with high-confidence fits
        r2s = []
        mapes = []
        for ch, cv in curves.items():
            if isinstance(cv, dict) and cv.get("diagnostics"):
                d = cv["diagnostics"]
                if d.get("r_squared") is not None:
                    r2s.append(d["r_squared"])
                if d.get("mape") is not None:
                    mapes.append(d["mape"])
        if r2s:
            avg_r2 = sum(r2s) / len(r2s)
            kpis["plan_confidence"]["r2_display"] = f"R² = {avg_r2:.2f}"
            if mapes:
                avg_mape = sum(mapes) / len(mapes)
                kpis["plan_confidence"]["mape_display"] = f"MAPE {avg_mape:.1f}%"

    result["kpis"] = kpis

    # Enrich each finding with a richer recommendation block.
    # Per-finding the backend already gives a short "prescribed_action".
    # We pair this with the matching move from the optimizer (so the
    # dollar delta, before→after spend, and confidence tier stay in
    # sync with the Plan screen), and add a risk note where we have
    # enough signal to surface one.
    opt_state = _state.get("optimization") or {}
    moves_by_channel = {m.get("channel"): m for m in opt_state.get("channels", [])}

    findings = result.get("findings") or []
    for f in findings:
        channel = (f.get("evidence_metric") or {}).get("channel")
        move = moves_by_channel.get(channel) if channel else None

        action_text = f.get("prescribed_action")
        impact = f.get("impact_dollars", 0)
        ftype = f.get("type", "opportunity")

        # If there's no matching channel move (cross-cutting findings like
        # channel_gap), build a generic recommendation from the finding's
        # own action text rather than dropping the field entirely
        if not move:
            fallback_action = action_text
            if not fallback_action:
                # Pattern-match on headline for common cross-cutting cases
                headline = (f.get("headline") or "").lower()
                if "online" in headline and "offline" in headline:
                    fallback_action = ("Evaluate online vs offline mix. If offline "
                                       "carries strategic value (brand, reach), "
                                       "maintain; otherwise shift.")
                elif "momentum" in headline or "accelerat" in headline:
                    fallback_action = ("Sustain current strategy. Watch for "
                                       "deceleration in monthly performance.")
                elif "concentration" in headline or "risk" in headline:
                    fallback_action = ("Diversify across channels to reduce "
                                       "single-channel exposure.")
                else:
                    fallback_action = None

            if fallback_action:
                f["recommendation"] = {
                    "action": fallback_action,
                    "impact_display": (f"+${impact/1e6:.1f}M annual uplift"
                                       if impact and impact >= 1e6
                                       else f"+${impact/1e3:.0f}K annual uplift"
                                       if impact else None),
                    "link_to": "plan",
                    "risk": None,
                }
            continue

        current = float(move.get("current_spend") or 0)
        optimized = float(move.get("optimized_spend") or 0)
        change_pct = ((optimized - current) / current * 100) if current > 0 else 0

        # Build a fuller action sentence keyed off the move
        if abs(change_pct) < 2:
            action = f"Hold {channel.replace('_', ' ').title()} near current spend."
        elif change_pct > 0:
            action = (f"Increase {channel.replace('_', ' ').title()} spend by "
                      f"{change_pct:+.0f}% — from ${current/1e6:.1f}M to "
                      f"${optimized/1e6:.1f}M.")
        else:
            action = (f"Reduce {channel.replace('_', ' ').title()} spend by "
                      f"{change_pct:+.0f}% — from ${current/1e6:.1f}M to "
                      f"${optimized/1e6:.1f}M.")

        # Impact line — prefer the optimizer's revenue_delta if present,
        # fall back to the finding's impact_dollars
        rev_delta = move.get("revenue_delta", 0) or impact or 0
        if abs(rev_delta) >= 1e6:
            impact_display = f"Projected revenue {'+' if rev_delta>0 else ''}${rev_delta/1e6:.1f}M"
        elif abs(rev_delta) >= 1e3:
            impact_display = f"Projected revenue {'+' if rev_delta>0 else ''}${rev_delta/1e3:.0f}K"
        else:
            impact_display = None

        # Risk — surface a caution for aggressive moves or low-reliability
        risk = None
        reliability = str(move.get("reliability", "")).lower()
        if abs(change_pct) > 40:
            risk = (f"Aggressive move. Validate with a 4-6 week geo-holdout "
                    f"before scaling beyond 50% of the target.")
        elif reliability in ("low", "inconclusive"):
            risk = ("Response curve for this channel is inconclusive — "
                    "treat the optimizer's target as directional, not a commitment.")
        elif ftype == "warning":
            risk = ("This is a cost/efficiency warning, not a growth move. "
                    "Fix the underlying CAC issue before scaling.")

        f["recommendation"] = {
            "action": action,
            "impact_display": impact_display,
            "link_to": "plan",
            "channel": channel,
            "risk": risk,
            "change_pct": round(change_pct, 1),
            "before_spend": current,
            "after_spend": optimized,
        }

    result["findings"] = findings

    # Market context — surface external data (events, competitive, trends)
    # that's been uploaded. Even if the 90-day recommendation window
    # isn't firing, the user uploaded the data and expects to see it
    # reflected somewhere. This block is where it appears.
    market_context = {
        "events": [],
        "event_recommendations": [],
        "trends_alerts": [],
        "competitive_snapshot": None,
        "data_sources_loaded": [],
    }

    er = _state.get("events_result") or {}
    if er.get("events"):
        # Surface up to 6 upcoming events, sorted soonest first
        upcoming = sorted(
            [e for e in er["events"] if e.get("is_upcoming")],
            key=lambda e: e.get("days_away", 999)
        )[:6]
        market_context["events"] = [
            {
                "name": e.get("name"),
                "date": e.get("date"),
                "days_away": e.get("days_away"),
                "direction": e.get("direction"),
                "magnitude": e.get("magnitude"),
                "impact_pct": e.get("impact_pct"),
                "affected_channels": e.get("affected_channels", []),
                "type": e.get("type"),
            }
            for e in upcoming
        ]
        # Recommendations that ARE in the 90-day window
        market_context["event_recommendations"] = er.get("recommendations", [])[:5]
        market_context["data_sources_loaded"].append("events")

    tr = _state.get("trends_result") or {}
    if tr.get("recommendations"):
        # Alerts from trends (CPC inflation, CPM shifts, CTR benchmarks)
        alerts = []
        for rec in tr.get("recommendations", [])[:5]:
            alerts.append({
                "title": rec.get("action_summary") or rec.get("title"),
                "narrative": rec.get("narrative", "")[:240],
                "channel": rec.get("channel"),
                "impact": rec.get("impact", 0),
            })
        market_context["trends_alerts"] = alerts
        market_context["data_sources_loaded"].append("trends")

    cr = _state.get("competitive_result") or {}
    if cr:
        # Compact snapshot: our SOV vs top competitor, gap, trend
        snapshot = {
            "our_share_of_voice": cr.get("our_share_of_voice"),
            "top_competitor": cr.get("top_competitor"),
            "gap_direction": cr.get("gap_direction"),
            "narrative": cr.get("narrative"),
        }
        if any(v is not None for v in snapshot.values()):
            market_context["competitive_snapshot"] = snapshot
            market_context["data_sources_loaded"].append("competitive")

    result["market_context"] = market_context
    return _j(result)


# ═══ Plan screen (v18c) ═══

@app.get("/api/plan")
def get_plan(view: str = "client", engagement_id: str = "default",
             total_budget: Optional[float] = None, objective: str = "maximize_revenue"):
    """
    Plan screen payload: the recommended budget reallocation.

    Query params:
      view: "client" (default) or "editor" — same semantics as /api/diagnosis
      engagement_id: override keyspace (always "default" in single-tenant)
      total_budget: if provided, re-optimizes at this budget before generating
                    the plan. If omitted, uses current total spend + 5% for
                    a natural "what should we do with roughly this budget"
                    starting point.
      objective: optimizer objective ("balanced", "max_revenue", "max_roi").

    Returns:
      headline_paragraph, kpis, moves (per-channel), tradeoffs,
      methodology, summary, ey_overrides. Same shape family as
      /api/diagnosis, different content semantics.

    Caching: the optimizer has a stochastic multi-restart component,
    which means re-running it on identical inputs can produce slightly
    different allocations (the final picked solution is usually the
    same, but near-tie moves can flip between increase/decrease/hold).
    That flip breaks editor-overlay keys (move:events:decrease vs.
    move:events:increase). To prevent orphaned overrides, we cache the
    optimization result per (budget, objective) pair and only re-run
    when these inputs actually change. The cache is cleared on
    /api/run-analysis (which re-fits curves) so a genuine re-analysis
    picks up new outputs.
    """
    if view not in ("client", "editor"):
        raise HTTPException(400, f"Invalid view '{view}' — must be 'client' or 'editor'")
    _ensure_analysis()
    if _state["campaign_data"] is None:
        raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    if not _state.get("curves"):
        raise HTTPException(400, "Response curves not fit yet — run /api/run-analysis first")

    # Plan budget + optimization sourcing. Both /api/plan and
    # /api/market-adjustments route through _cached_plan_optimization()
    # which is keyed on _default_plan_budget(). Keeping this shared is
    # what prevents the two screens from showing disagreeing numbers.
    #
    # Explicit budget/objective overrides still supported for custom
    # callers — they bypass the shared helper and do their own optimize.
    if total_budget is None and objective == "maximize_revenue":
        optimization = _cached_plan_optimization()
    else:
        # Custom budget/objective — run optimizer directly, don't cache.
        if total_budget is None:
            total_budget = _default_plan_budget()
        total_budget = float(total_budget)
        from engines.optimizer import optimize_budget
        optimization = optimize_budget(
            _state["curves"],
            total_budget,
            objective=objective,
        )

    from engines.narrative_plan import generate_plan
    plan = generate_plan(
        optimization=optimization,
        response_curves=_state.get("curves") or {},
        engagement_id=engagement_id,
        view=view,
        bayes_result=_state.get("bayes_result"),
    )
    return _j(plan)


# ═══ Market adjustments (Week 7) ═══
#
# Engine lives in engines/market_adjustments.py. This endpoint consumes
# the current plan + external data results and returns the structured
# overlay. Frontend Plan/Scenarios/Diagnosis screens call this to render
# the "Market adjustments applied" section + Diagnosis snippet.
#
# Overrides are in-memory per session (no DB table for Week 7 — defer if
# the pitch shows it's actually used). Keyed by adjustment_id.


def _default_plan_budget() -> float:
    """
    Canonical plan budget used by /api/plan AND /api/market-adjustments.

    Both endpoints MUST use this same helper so the optimizer cache key
    matches and both screens show the same moves. If they diverge (e.g.
    one uses _current_total_spend, the other uses curves-based sum),
    the optimizer runs twice with different budgets and produces
    different numbers for "the same plan" — a visible Plan-vs-Overlay
    mismatch the pitch audience will catch.

    Formula: sum(current_avg_spend × 12) across all fitted channels,
    times 1.05 headroom.
    """
    curves = _state.get("curves", {}) or {}
    current_total = sum(
        v.get("current_avg_spend", 0) * 12
        for v in curves.values() if "error" not in v
    )
    return float(current_total * 1.05)


def _cached_plan_optimization(objective: str = "maximize_revenue"):
    """
    Get the optimization result for the default plan budget, using the
    shared _plan_cache. Both /api/plan and /api/market-adjustments call
    this so they see identical moves.

    Returns the optimization dict. Mutates _state["_plan_cache"] as a
    side effect to prime the cache for subsequent calls.
    """
    from engines.optimizer import optimize_budget

    total_budget = _default_plan_budget()
    cache_key = (round(total_budget, 0), objective)
    curves_identity = id(_state.get("curves"))
    plan_cache = _state.get("_plan_cache") or {}
    cached = plan_cache.get(cache_key)
    if cached and cached.get("curves_identity") == curves_identity:
        return cached["optimization"]

    optimization = optimize_budget(
        _state["curves"],
        total_budget,
        objective=objective,
    )
    plan_cache[cache_key] = {
        "optimization": optimization,
        "curves_identity": curves_identity,
    }
    _state["_plan_cache"] = plan_cache
    return optimization


@app.get("/api/market-adjustments")
def get_market_adjustments(engagement_id: str = "default"):
    """
    Return the current market adjustments overlay.

    Structure: see engines/market_adjustments.generate_market_adjustments.
    If no external data uploaded, returns an empty list with
    summary.has_market_data=False — UI should hide the section.
    """
    from engines.market_adjustments import generate_market_adjustments, apply_overrides

    if not _state.get("optimization"):
        return _j({
            "adjustments": [],
            "baseline_total_revenue_delta": 0,
            "adjusted_total_revenue_delta": 0,
            "summary": {
                "adjustment_count": 0, "net_delta": 0,
                "has_market_data": False,
                "message": "Run analysis first.",
            },
        })

    # Use the SAME cached optimization that /api/plan uses so the moves
    # match across screens. Both endpoints route through
    # _cached_plan_optimization() which is keyed on _default_plan_budget().
    optimization = _cached_plan_optimization()

    # Build moves inline — same call shape as generate_plan uses
    from engines.narrative_plan import build_moves
    moves = build_moves(
        optimization.get("channels", []),
        curves=_state.get("curves") or {},
        bayes_result=_state.get("bayes_result"),
    )

    payload = generate_market_adjustments(
        plan_moves=moves,
        events_result=_state.get("events_result"),
        trends_result=_state.get("trends_result"),
        competitive_result=_state.get("competitive_result"),
    )

    # Apply in-memory overrides if any
    overrides = _state.get("market_adjustment_overrides", {}) or {}
    if overrides:
        payload = apply_overrides(payload, overrides)

    return _j(payload)


@app.get("/api/market-adjustments/scenario")
def get_scenario_market_adjustments(total_budget: Optional[float] = None,
                                     objective: str = "maximize_revenue"):
    """
    Market adjustments for a specific scenario's budget.

    Scenarios can use non-default budgets (e.g. "aggressive growth" at +25%
    budget). That different budget produces a different optimizer run →
    different moves → different adjustments. This endpoint computes the
    adjustments for the scenario's specific budget, using the same
    optimizer cache the /api/scenario endpoint uses so numbers agree.

    Query params:
      total_budget: the scenario's budget. Defaults to current total spend
                    (baseline scenario), which produces no moves and therefore
                    no adjustments.
      objective: kept for parity with /api/scenario, defaults to the same
                 "maximize_revenue" used across Plan and the default overlay.
    """
    from engines.market_adjustments import generate_market_adjustments, apply_overrides

    if not _state.get("optimization") or not _state.get("curves"):
        return _j({
            "adjustments": [],
            "baseline_total_revenue_delta": 0,
            "adjusted_total_revenue_delta": 0,
            "summary": {
                "adjustment_count": 0, "net_delta": 0,
                "has_market_data": False,
                "message": "Run analysis first.",
            },
        })

    if total_budget is None:
        total_budget = _current_total_spend()
    total_budget = float(total_budget)

    # Use the scenario cache the same way /api/scenario does so the two
    # endpoints show identical numbers for the same budget/objective pair.
    cache_key = (round(total_budget, 0), objective)
    curves_identity = id(_state.get("curves"))
    plan_cache = _state.get("_plan_cache") or {}
    cached = plan_cache.get(cache_key)
    if cached and cached.get("curves_identity") == curves_identity:
        optimization = cached["optimization"]
    else:
        from engines.optimizer import optimize_budget
        optimization = optimize_budget(
            _state["curves"], total_budget, objective=objective,
        )
        plan_cache[cache_key] = {
            "optimization": optimization,
            "curves_identity": curves_identity,
        }
        _state["_plan_cache"] = plan_cache

    # Build moves for THIS scenario (not the default plan)
    from engines.narrative_plan import build_moves
    moves = build_moves(
        optimization.get("channels", []),
        curves=_state.get("curves") or {},
        bayes_result=_state.get("bayes_result"),
    )

    # Generate adjustments using the scenario's moves — this is the key
    # difference from /api/market-adjustments which uses default plan moves.
    payload = generate_market_adjustments(
        plan_moves=moves,
        events_result=_state.get("events_result"),
        trends_result=_state.get("trends_result"),
        competitive_result=_state.get("competitive_result"),
    )

    # Apply the same in-memory overrides — analyst's toggle state should
    # persist across Plan and Scenarios since adjustments represent the
    # same underlying market signals.
    overrides = _state.get("market_adjustment_overrides", {}) or {}
    if overrides:
        payload = apply_overrides(payload, overrides)

    # Tag the payload with the scenario's budget for the UI to display
    payload["scenario_total_budget"] = round(total_budget, 0)

    return _j(payload)


@app.post("/api/market-adjustments/override")
def override_market_adjustment(payload: Dict[str, Any] = Body(...)):
    """
    Toggle an adjustment on/off. Body: {"adjustment_id": "...", "applied": bool}.
    Editor-only — any authenticated editor can set.
    """
    adj_id = payload.get("adjustment_id")
    applied = bool(payload.get("applied", True))
    if not adj_id:
        return _j({"ok": False, "error": "adjustment_id required"}, 400)

    overrides = dict(_state.get("market_adjustment_overrides") or {})
    overrides[adj_id] = applied
    _state["market_adjustment_overrides"] = overrides

    return _j({"ok": True, "adjustment_id": adj_id, "applied": applied})


# ═══ Scenarios screen (v18f) ═══

def _current_total_spend() -> float:
    """
    Compute the client's current annualized spend across all channels.
    Used as the baseline for scenario comparisons and as the default
    'baseline' preset on the Scenarios screen.
    """
    curves = _state.get("curves", {}) or {}
    return sum(
        v.get("current_avg_spend", 0) * 12
        for v in curves.values() if "error" not in v
    )


def _baseline_optimization() -> Dict:
    """
    Return the optimizer's allocation at the current spend level — the
    'do nothing different' counterfactual the scenario gets compared to.
    Cached per session (curves_identity), so the comparison is stable
    across multiple scenario calls and matches the Plan-screen baseline.
    """
    current_total = _current_total_spend()
    cache_key = (round(current_total, 0), "balanced")
    curves_identity = id(_state.get("curves"))
    plan_cache = _state.get("_plan_cache") or {}
    cached = plan_cache.get(cache_key)
    if cached and cached.get("curves_identity") == curves_identity:
        return cached["optimization"]
    from engines.optimizer import optimize_budget
    opt = optimize_budget(_state["curves"], current_total, objective="balanced")
    plan_cache[cache_key] = {"optimization": opt, "curves_identity": curves_identity}
    _state["_plan_cache"] = plan_cache
    return opt


@app.get("/api/scenario/presets")
def get_scenario_presets():
    """
    Return the four preset budget levels the Scenarios screen offers.
    Computed dynamically from the client's current spend so they're
    always sensible for whatever data is loaded.

    Presets:
      baseline:    current annualized spend (the 'do nothing' lever)
      conservative: current spend × 0.80 (recession / cost-cut scenario)
      growth:       current spend × 1.25 (growth investment scenario)
      recommended:  current spend × 1.05 (matches Plan-screen default,
                    the small headroom that lets the optimizer show
                    upside without being asked to cut)
    """
    _ensure_analysis()
    if not _state.get("curves"):
        raise HTTPException(400, "Response curves not fit yet — run /api/run-analysis first")
    current = _current_total_spend()
    return _j({
        "presets": [
            {"key": "baseline",     "label": "Current spend",     "total_budget": round(current, 0),         "description": "Keep total marketing investment at today's level."},
            {"key": "conservative", "label": "Cut 20%",            "total_budget": round(current * 0.80, 0),  "description": "Recession-style scenario: spend 20% less in aggregate."},
            {"key": "growth",       "label": "Increase 25%",       "total_budget": round(current * 1.25, 0),  "description": "Growth scenario: scale total marketing investment by 25%."},
            {"key": "recommended",  "label": "Optimizer recommended", "total_budget": round(current * 1.05, 0), "description": "What the optimizer suggests — same as the Plan screen baseline."},
        ],
        "current_spend": round(current, 0),
    })


@app.get("/api/scenario")
def get_scenario(total_budget: Optional[float] = None,
                  objective: str = "maximize_revenue",
                  view: str = "client",
                  engagement_id: str = "default"):
    """
    Generate a what-if scenario at a specified total_budget.

    Same payload shape as /api/plan PLUS a `comparison` block that shows
    delta vs. baseline (current allocation at current spend). Without
    that comparison, the screen reads as "Plan at a different budget"
    — which doesn't earn its own surface. The comparison is what makes
    Scenarios meaningful: "at $26M instead of $32M, you'd lose $4.2M of
    revenue but ROI would actually improve by 0.4x."

    Critical for stability: the optimizer is non-convex and a fresh
    multi-restart on the same input can produce a slightly different
    allocation. Without caching, the "Optimizer recommended" scenario
    could disagree with the Plan screen on the same budget — confusing.
    The scenario endpoint shares the Plan endpoint's cache so identical
    budgets produce identical numbers.

    The baseline (current spend) IS also cached because the comparison
    reference shouldn't drift between scenario requests in the same
    session — that would make "you've lost $X in revenue vs. baseline"
    wobble between identical calls.
    """
    if view not in ("client", "editor"):
        raise HTTPException(400, f"Invalid view '{view}' — must be 'client' or 'editor'")
    _ensure_analysis()
    if _state.get("campaign_data") is None:
        raise HTTPException(400, "No data loaded — call /api/load-mock-data first")
    if not _state.get("curves"):
        raise HTTPException(400, "Response curves not fit yet — run /api/run-analysis first")

    if total_budget is None:
        total_budget = _current_total_spend()
    total_budget = float(total_budget)

    # Reuse cached Plan-screen optimization if the scenario budget matches
    # what the Plan endpoint cached. Without this, the "Optimizer recommended"
    # preset could show a different (worse) revenue delta than the Plan
    # screen reports for the same budget — confusing the user about which
    # number to trust. Same backend, same answer.
    cache_key = (round(total_budget, 0), objective)
    curves_identity = id(_state.get("curves"))
    plan_cache = _state.get("_plan_cache") or {}
    cached = plan_cache.get(cache_key)
    if cached and cached.get("curves_identity") == curves_identity:
        scenario_opt = cached["optimization"]
    else:
        from engines.optimizer import optimize_budget
        scenario_opt = optimize_budget(
            _state["curves"], total_budget, objective=objective,
        )
        # Cache the result so subsequent identical scenarios are stable too
        plan_cache[cache_key] = {
            "optimization": scenario_opt,
            "curves_identity": curves_identity,
        }
        _state["_plan_cache"] = plan_cache

    baseline_opt = _baseline_optimization()

    # Generate the same Plan-shape payload for the scenario
    from engines.narrative_plan import generate_plan
    plan = generate_plan(
        optimization=scenario_opt,
        response_curves=_state.get("curves") or {},
        engagement_id=engagement_id,
        view=view,
    )

    # Comparison block: scenario vs. baseline
    s_summary = scenario_opt.get("summary", {}) or {}
    b_summary = baseline_opt.get("summary", {}) or {}
    s_rev = float(s_summary.get("optimized_revenue", 0))
    b_rev = float(b_summary.get("optimized_revenue", 0))
    s_roi = float(s_summary.get("optimized_roi", 0))
    b_roi = float(b_summary.get("optimized_roi", 0))
    s_budget = float(s_summary.get("total_budget", total_budget))
    b_budget = float(b_summary.get("total_budget", _current_total_spend()))

    rev_delta = s_rev - b_rev
    roi_delta = s_roi - b_roi
    budget_delta = s_budget - b_budget

    # Comparison narrative — short, factual, names the tradeoff
    if abs(budget_delta) < 100_000:
        budget_phrase = "same total spend"
    elif budget_delta > 0:
        budget_phrase = f"${abs(budget_delta)/1e6:.1f}M more spend"
    else:
        budget_phrase = f"${abs(budget_delta)/1e6:.1f}M less spend"

    if rev_delta > 100_000:
        rev_phrase = f"would generate {_format_compact(rev_delta)} more annual revenue"
    elif rev_delta < -100_000:
        rev_phrase = f"would lose {_format_compact(abs(rev_delta))} of annual revenue"
    else:
        rev_phrase = "would be roughly revenue-neutral"

    if abs(roi_delta) > 0.1:
        direction = "improve" if roi_delta > 0 else "decline"
        roi_phrase = f", with portfolio ROI {direction} from {b_roi:.1f}x to {s_roi:.1f}x"
    else:
        roi_phrase = f", with portfolio ROI roughly unchanged at {s_roi:.1f}x"

    comparison_narrative = (
        f"Compared to keeping today's allocation, this scenario uses "
        f"{budget_phrase} and {rev_phrase}{roi_phrase}."
    )

    plan["comparison"] = {
        "narrative": comparison_narrative,
        "scenario": {
            "total_budget": round(s_budget, 0),
            "projected_revenue": round(s_rev, 0),
            "projected_roi": round(s_roi, 2),
        },
        "baseline": {
            "total_budget": round(b_budget, 0),
            "projected_revenue": round(b_rev, 0),
            "projected_roi": round(b_roi, 2),
        },
        "deltas": {
            "budget_delta": round(budget_delta, 0),
            "revenue_delta": round(rev_delta, 0),
            "roi_delta": round(roi_delta, 2),
        },
    }
    plan["scenario_inputs"] = {
        "total_budget": round(total_budget, 0),
        "objective": objective,
    }
    return _j(plan)


def _format_compact(amount: float) -> str:
    """Local helper for scenario narrative compact formatting."""
    a = abs(amount)
    if a >= 1e9: return f"${a/1e9:.1f}B"
    if a >= 1e6: return f"${a/1e6:.1f}M"
    if a >= 1e3: return f"${a/1e3:.0f}K"
    return f"${a:.0f}"


# ═══ EY Editor Overlay endpoints (v18a) ═══
#
# These endpoints mutate the editor overrides stored in persistence. They
# are called only by the editor entry point (index-editor.html); the client
# entry point never mutates anything, it only reads /api/diagnosis?view=client.
#
# In v18a there is no auth layer — any caller reaching these endpoints can
# edit overrides. Auth will wrap these endpoints when it comes.

from pydantic import BaseModel


class CommentaryPayload(BaseModel):
    finding_key: str
    text: str
    author: Optional[str] = None


class SuppressionPayload(BaseModel):
    finding_key: str
    reason: str
    author: Optional[str] = None


class RewritePayload(BaseModel):
    finding_key: str
    field: str  # "headline" | "narrative" | "prescribed_action"
    original: str
    rewritten: str
    author: Optional[str] = None


def _engagement_id_param(engagement_id: Optional[str]) -> str:
    """Resolve an engagement_id param, defaulting to 'default'."""
    return (engagement_id or "default").strip() or "default"


@app.post("/api/editor/commentary")
def editor_set_commentary(body: CommentaryPayload,
                          engagement_id: Optional[str] = None,
                          user=Depends(require_editor)):
    """Create or replace EY commentary for a finding. Requires editor role.
    Author is taken from the authenticated user's token, not the request
    body — clients cannot forge authorship."""
    from persistence import set_commentary
    eid = _engagement_id_param(engagement_id)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Commentary text cannot be empty. Use DELETE to remove.")
    set_commentary(eid, body.finding_key, text, author=user["username"])
    return _j({"ok": True, "finding_key": body.finding_key})


@app.delete("/api/editor/commentary/{finding_key:path}")
def editor_delete_commentary(finding_key: str,
                              engagement_id: Optional[str] = None,
                              user=Depends(require_editor)):
    """Remove EY commentary for a finding. Requires editor role."""
    from persistence import delete_commentary
    eid = _engagement_id_param(engagement_id)
    deleted = delete_commentary(eid, finding_key, author=user["username"])
    return _j({"ok": True, "deleted": deleted, "finding_key": finding_key})


@app.post("/api/editor/suppress")
def editor_suppress_finding(body: SuppressionPayload,
                            engagement_id: Optional[str] = None,
                            user=Depends(require_editor)):
    """Mark a finding as hidden from the client view. Reason is required.
    Requires editor role."""
    from persistence import suppress_finding
    eid = _engagement_id_param(engagement_id)
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(400, "A reason is required to suppress a finding (for audit).")
    suppress_finding(eid, body.finding_key, reason, author=user["username"])
    return _j({"ok": True, "finding_key": body.finding_key})


@app.delete("/api/editor/suppress/{finding_key:path}")
def editor_unsuppress_finding(finding_key: str,
                               engagement_id: Optional[str] = None,
                               user=Depends(require_editor)):
    """Restore a previously suppressed finding to the client view.
    Requires editor role."""
    from persistence import unsuppress_finding
    eid = _engagement_id_param(engagement_id)
    deleted = unsuppress_finding(eid, finding_key, author=user["username"])
    return _j({"ok": True, "deleted": deleted, "finding_key": finding_key})


@app.post("/api/editor/rewrite")
def editor_set_rewrite(body: RewritePayload,
                       engagement_id: Optional[str] = None,
                       user=Depends(require_editor)):
    """Save a text rewrite for a finding field (headline/narrative/prescribed_action).
    Requires editor role. Schema-ready in v18a; UI wired in v18b+."""
    from persistence import set_rewrite
    eid = _engagement_id_param(engagement_id)
    if body.field not in ("headline", "narrative", "prescribed_action"):
        raise HTTPException(400, f"Invalid field '{body.field}'")
    if not (body.rewritten or "").strip():
        raise HTTPException(400, "Rewritten text cannot be empty. Use DELETE to revert.")
    set_rewrite(eid, body.finding_key, body.field, body.original, body.rewritten,
                author=user["username"])
    return _j({"ok": True, "finding_key": body.finding_key, "field": body.field})


@app.delete("/api/editor/rewrite/{finding_key:path}/{field}")
def editor_delete_rewrite(finding_key: str, field: str,
                           engagement_id: Optional[str] = None,
                           user=Depends(require_editor)):
    """Revert a rewrite back to the generated text. Requires editor role."""
    from persistence import delete_rewrite
    eid = _engagement_id_param(engagement_id)
    deleted = delete_rewrite(eid, finding_key, field, author=user["username"])
    return _j({"ok": True, "deleted": deleted, "finding_key": finding_key, "field": field})


@app.get("/api/editor/audit-log")
def editor_get_audit_log(engagement_id: Optional[str] = None, limit: int = 50,
                          user=Depends(require_editor)):
    """Return recent audit log entries. Requires editor role — a client
    user viewing audit logs would reveal which findings were suppressed
    and why, defeating the point of suppression."""
    from persistence import get_audit_log
    eid = _engagement_id_param(engagement_id)
    limit = max(1, min(500, limit))
    return _j({"engagement_id": eid, "entries": get_audit_log(eid, limit)})


@app.get("/api/executive-summary")
def get_executive_summary():
    """Generate a downloadable executive summary as text."""
    if not all([_state["optimization"], _state["pillars"], _state["diagnostics"], _state["campaign_data"] is not None]):
        raise HTTPException(400, "Run full analysis first")
    df = _state["reporting_data"] if _state["reporting_data"] is not None else _state["campaign_data"]
    opt = _state["optimization"]; pil = _state["pillars"]; recs = _state["diagnostics"]
    ts = float(df["spend"].sum()); tr = float(df["revenue"].sum())
    sm = opt.get("summary", {})
    lines = [
        "YIELD INTELLIGENCE — EXECUTIVE SUMMARY",
        "=" * 50, "",
        "PORTFOLIO OVERVIEW",
        f"  Total Marketing Spend:   ${ts:,.0f}",
        f"  Total Revenue:           ${tr:,.0f}",
        f"  Portfolio ROI:           {(tr-ts)/max(ts,1):.2f}x",
        f"  ROAS:                    {tr/max(ts,1):.2f}x", "",
        "OPTIMIZATION RESULTS",
        f"  Current Revenue:         ${sm.get('current_revenue',0):,.0f}",
        f"  Optimized Revenue:       ${sm.get('optimized_revenue',0):,.0f}",
        f"  Revenue Uplift:          {sm.get('uplift_pct',0):.1f}%",
        f"  ROI Improvement:         {sm.get('current_roi',0):.2f}x → {sm.get('optimized_roi',0):.2f}x", "",
        "VALUE AT RISK",
        f"  Total Value at Risk:     ${pil.get('total_value_at_risk',0):,.0f}",
        f"  Revenue Leakage:         ${pil.get('revenue_leakage',{}).get('total_leakage',0):,.0f}",
        f"  CX Suppression:          ${pil.get('experience_suppression',{}).get('total_suppression',0):,.0f}",
        f"  Avoidable Cost:          ${pil.get('avoidable_cost',{}).get('total_avoidable_cost',0):,.0f}", "",
        "CHANNEL ALLOCATION (Top changes)", "-" * 50,
    ]
    for c in sorted(opt.get("channels",[]), key=lambda x: abs(x.get("change_pct",0)), reverse=True)[:8]:
        ch = c.get("channel","")
        lines.append(f"  {ch:20s}  ${c.get('current_spend',0):>12,.0f} → ${c.get('optimized_spend',0):>12,.0f}  ({c.get('change_pct',0):+.1f}%)")
    lines += ["", "TOP RECOMMENDATIONS", "-" * 50]
    for i, r in enumerate(recs[:8]):
        lines.append(f"  {i+1}. [{r.get('type','')}] {r.get('channel','')}: {r.get('action','')}")
        if r.get('impact',0): lines.append(f"     Impact: ${abs(r['impact']):,.0f}  Confidence: {r.get('confidence','')}")
    lines += ["", "IMPLEMENTATION ROADMAP", "-" * 50]
    for phase, effort in [("Immediate (0-30 days)","Low"),("Short-term (30-90 days)","Medium"),("Strategic (90+ days)","High")]:
        phase_recs = [r for r in recs if r.get("effort")==effort][:3]
        if phase_recs:
            lines.append(f"  {phase}")
            for r in phase_recs: lines.append(f"    - {r.get('channel','')}: {r.get('action','')}")
    lines += ["", "-" * 50, "Generated by Yield Intelligence Platform", "All estimates are directional. Validate with holdout tests before scaling."]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines), media_type="text/plain",
                            headers={"Content-Disposition": "attachment; filename=executive_summary.txt"})


@app.get("/api/trend-analysis")
def get_trend_analysis():
    if _state["trend_analysis"] is None:
        if _state["campaign_data"] is not None:
            _state["trend_analysis"] = run_trend_analysis(_state["campaign_data"])  # ✅ fixed
        else: raise HTTPException(400, "No data loaded")
    return _j(_state["trend_analysis"])

@app.get("/api/funnel-analysis")
def get_funnel_analysis():
    if _state["funnel_analysis"] is None:
        if _state["campaign_data"] is not None:
            _state["funnel_analysis"] = run_funnel_analysis(_state["campaign_data"])  # ✅ fixed
        else: raise HTTPException(400, "No data loaded")
    return _j(_state["funnel_analysis"])

@app.get("/api/roi-analysis")
def get_roi_analysis(gross_margin_pct: float = 0.65):
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(compute_all_roi(_state["campaign_data"], _state.get("curves"), gross_margin_pct))  # ✅ fixed

@app.get("/api/download-template")
def download_template(kind: str = "campaign"):
    """
    Serve a blank CSV template the analyst can fill in for a given data
    type. Powered by the files in /templates/ at the repo root.

    kind values (matched to the 5 upload endpoints):
      - "campaign"     → campaign_performance_template.csv (primary)
      - "journeys"     → user_journeys_template.csv
      - "competitive"  → competitive_intelligence_template.csv
      - "events"       → market_events_template.csv
      - "trends"       → market_trends_template.csv

    Returns the CSV as a downloadable file with Content-Disposition so
    the browser prompts a save dialog rather than rendering in a tab.
    """
    template_map = {
        "campaign":    "campaign_performance_template.csv",
        "journeys":    "user_journeys_template.csv",
        "competitive": "competitive_intelligence_template.csv",
        "events":      "market_events_template.csv",
        "trends":      "market_trends_template.csv",
    }
    filename = template_map.get(kind)
    if not filename:
        raise HTTPException(400, f"Unknown template kind: {kind}. Valid: {list(template_map.keys())}")

    # Templates live at <repo_root>/templates/ — one level up from backend/
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    template_path = os.path.join(templates_dir, filename)

    if not os.path.exists(template_path):
        # Fall back to the legacy combined template if the new ones aren't
        # deployed for some reason (e.g. backend/data/upload_template.csv).
        # This keeps the endpoint functional during the v18h rollout.
        legacy_path = os.path.join(os.path.dirname(__file__), "data", "upload_template.csv")
        if kind == "campaign" and os.path.exists(legacy_path):
            template_path = legacy_path
        else:
            raise HTTPException(404, f"Template file not found: {filename}")

    from fastapi.responses import FileResponse
    return FileResponse(
        template_path,
        media_type="text/csv",
        filename=filename,
    )


@app.get("/api/analyst-status")
def analyst_status():
    """
    Status payload for the Analyst Tools Hub screen.

    Reports what data has been uploaded, when the model was last run,
    and what the analyst should do next. Does NOT include actual data
    (that lives on other endpoints); this is purely metadata for the
    hub's dashboard.
    """
    state = _state
    has_campaign = state.get("campaign_data") is not None
    has_journeys = state.get("journey_data") is not None
    has_competitive = state.get("external_competitive") is not None
    has_events = state.get("external_events") is not None
    has_trends = state.get("external_trends") is not None
    has_analysis = (
        state.get("curves") is not None
        and state.get("optimization") is not None
    )

    # Row counts per loaded dataset
    def _rows(df):
        try: return int(len(df)) if df is not None else 0
        except Exception: return 0

    data_sources = [
        {
            "kind": "campaign",
            "label": "Campaign performance",
            "description": "Monthly spend, revenue, conversions per channel. Required for all analysis.",
            "loaded": has_campaign,
            "rows": _rows(state.get("campaign_data")),
            "required": True,
        },
        {
            "kind": "journeys",
            "label": "User journeys",
            "description": "Multi-touch journey data for attribution modeling. Optional; improves attribution accuracy.",
            "loaded": has_journeys,
            "rows": _rows(state.get("journey_data")),
            "required": False,
        },
        {
            "kind": "competitive",
            "label": "Competitive intelligence",
            "description": "Competitor spend data from SEMrush, SimilarWeb, or similar. Optional; informs benchmarks.",
            "loaded": has_competitive,
            "rows": _rows(state.get("external_competitive")),
            "required": False,
        },
        {
            "kind": "events",
            "label": "Market events & festivities",
            "description": "Seasonal events, competitor launches, market shifts. Optional; improves diagnostic context.",
            "loaded": has_events,
            "rows": _rows(state.get("external_events")),
            "required": False,
        },
        {
            "kind": "trends",
            "label": "Market trends",
            "description": "CPC/CPM trends, Google Trends, category benchmarks. Optional; contextualizes channel cost.",
            "loaded": has_trends,
            "rows": _rows(state.get("external_trends")),
            "required": False,
        },
    ]

    # Summary counts for the KPI cards
    loaded_sources = sum(1 for s in data_sources if s["loaded"])
    n_channels = 0
    n_campaigns = 0
    if has_campaign:
        df = state["campaign_data"]
        try:
            n_channels = int(df["channel"].nunique())
            for col in ("campaign", "camp"):
                if col in df.columns:
                    n_campaigns = int(df[col].nunique())
                    break
        except Exception:
            pass

    # Next-step hint — what should the analyst do?
    if not has_campaign:
        next_step = "Upload campaign performance data to begin analysis."
    elif not has_analysis:
        next_step = "Data loaded. Re-run analysis to refresh the diagnosis."
    elif loaded_sources < 3:
        next_step = "Analysis complete. Consider uploading market events or trends for richer context."
    else:
        next_step = "All primary data loaded. Review Diagnosis and Plan for client delivery."

    return _j({
        "greeting_name": "Sarah",  # Hardcoded for the pitch; becomes dynamic once auth carries full user records
        "data_sources": data_sources,
        "stats": {
            "loaded_sources": loaded_sources,
            "total_sources": len(data_sources),
            "channels": n_channels,
            "campaigns": n_campaigns,
            "analysis_complete": has_analysis,
        },
        "next_step": next_step,
    })


# ═══════════════════════════════════════════════
#  PHASE 2 ENDPOINTS
# ═══════════════════════════════════════════════

@app.post("/api/adstock")
def run_adstock(adstock_type: str = "auto"):
    """Fit adstock per channel.

    adstock_type:
      - "auto" (default): channel-aware — Weibull for broadcast (TV, radio,
        OOH, events), geometric for digital and direct-response channels.
        Each channel gets the adstock shape appropriate to its
        attribution basis.
      - "geometric" or "weibull": force a single type across all channels.
    """
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(compute_channel_adstock(_state["campaign_data"], adstock_type))

@app.post("/api/mmm")
def run_mmm_endpoint(method: str = "auto", n_draws: int = 500):
    """Run Marketing Mix Model.

    method: "auto" (default, tries Bayesian → MLE → OLS), "bayesian", "mle", "ols".
    n_draws: posterior draws per chain for Bayesian; ignored for MLE/OLS.

    Note: Bayesian fit takes 60-180s on typical datasets. Use method="mle"
    for fast iteration in dev and tests.
    """
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(run_mmm(_state["campaign_data"], method=method, n_draws=n_draws))

@app.get("/api/markov-attribution")
def get_markov_attribution():
    if _state["journey_data"] is None: raise HTTPException(400, "No journey data")
    j_groups = {}
    for _, row in _state["journey_data"].iterrows():
        jid = row["journey_id"]
        if jid not in j_groups:
            j_groups[jid] = {"id":jid,"tps":[],"cv":row["converted"],"rv":0,"nt":row["total_touchpoints"]}
        j_groups[jid]["tps"].append({"ch":row["channel"],"camp":row["campaign"],"o":row["touchpoint_order"]})
        if row["conversion_revenue"] > 0: j_groups[jid]["rv"] = row["conversion_revenue"]
    return _j(run_markov_attribution(list(j_groups.values())))  # ✅ fixed name

@app.get("/api/forecast")
def get_forecast(periods: int = 12):
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(run_forecast(_state["campaign_data"], "revenue", periods))  # ✅ fixed name + args

@app.get("/api/cross-channel")
def get_cross_channel():
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(run_cross_channel_analysis(_state["campaign_data"]))


# ═══════════════════════════════════════════════
#  PHASE 3 ENDPOINTS
# ═══════════════════════════════════════════════

@app.get("/api/shapley")
def get_shapley():
    """Shapley values require response curves for the value function."""
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    curves = _state["curves"]
    channels = list(curves.keys())
    def value_fn(coalition):
        total = 0
        for ch in coalition:
            if ch in curves and "params" in curves[ch]:
                p = curves[ch]["params"]
                a, b = p.get("a",1), p.get("b",0.5)
                avg = curves[ch].get("current_avg_spend", 1000)
                total += a * np.power(max(avg, 1), b) * 12
        return total
    return _j(compute_shapley_values(channels, value_fn))  # ✅ fixed name + args

@app.post("/api/multi-objective")
def run_multi_objective(n_solutions: int = 30):
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    budget = float(_state["campaign_data"]["spend"].sum())
    return _j(pareto_optimize(_state["curves"], budget, n_points=n_solutions))  # ✅ fixed name

@app.get("/api/geo-lift/{region}")
def get_geo_lift(region: str):
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(run_geo_lift(_state["campaign_data"], test_region=region))  # ✅ fixed name

@app.get("/api/hierarchical-forecast")
def get_hierarchical_forecast(periods: int = 12):
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(run_hierarchical_forecast(_state["campaign_data"], periods=periods))  # ✅ fixed name

@app.get("/api/automated-recommendations")
def get_automated_recs():
    if _state["campaign_data"] is None: raise HTTPException(400, "No data loaded")
    return _j(automated_recommendations(_state["campaign_data"],
        response_curves=_state.get("curves"), attribution_results=_state.get("attribution")))

@app.get("/api/model-health")
def get_model_health():
    _ensure_analysis()
    if _state["curves"] is None: raise HTTPException(400, "No data loaded — upload data or call /api/load-mock-data first")
    return _j(check_model_drift(_state["curves"], _state["campaign_data"]))


# ═══════════════════════════════════════════════
#  FRONTEND SERVING
# ═══════════════════════════════════════════════
# Actual serving logic is at the bottom of this file (needs to be registered
# AFTER all API routes so the catch-all HTML routes don't intercept /api/*).

from starlette.staticfiles import StaticFiles

# ═══════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════

@app.post("/api/auth/register")
def api_register(username: str, password: str, role: str = "analyst"):
    """Register a new user (legacy query-param form, kept for analyst app).
    Returns JWT token. Note: passwords in URLs are bad practice; MarketLens
    login uses /api/auth/login-v2 with a JSON body instead."""
    return _j(register_user(username, password, role))

@app.post("/api/auth/login")
def api_login(username: str, password: str):
    """Login (legacy query-param form, kept for analyst app)."""
    return _j(login_user(username, password))


class LoginPayload(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login-v2")
def api_login_v2(body: LoginPayload):
    """
    Login with JSON body (MarketLens login screen uses this).

    Returns { user_id, username, role, token } on success or a 401 with
    a descriptive error on failure. The token is a JWT; the frontend
    stores it and attaches it as `Authorization: Bearer <token>` on
    subsequent requests.
    """
    return _j(login_user(body.username, body.password))


@app.get("/api/auth/me")
async def api_me(user=Depends(get_current_user)):
    """Get current user info from token."""
    if user is None:
        return _j({"authenticated": False, "role": "anonymous"})
    return _j({"authenticated": True, "user_id": user["id"], "username": user["username"], "role": user["role"]})


@app.get("/api/auth/demo-users")
def api_demo_users():
    """
    Return the list of seeded demo credentials for the login screen to
    display. In a production (non-demo) deployment, set the environment
    variable MARKETLENS_HIDE_DEMO_CREDS=1 and this endpoint returns
    an empty list — the login screen just shows the form with no hints.
    """
    from auth import get_demo_credentials_for_login_page
    return _j({"demo_users": get_demo_credentials_for_login_page()})


# ═══════════════════════════════════════════════════════
#  SCENARIO ENDPOINTS
# ═══════════════════════════════════════════════════════

@app.post("/api/scenarios/save")
def api_save_scenario(name: str, description: str = ""):
    """Save current optimizer state as a named scenario."""
    if _state["optimization"] is None:
        raise HTTPException(400, "Run optimization first")
    opt = _state["optimization"]
    params = {
        "model_selections": _state.get("model_selections", {}),
        "model_type": _state.get("_model_type", "auto"),
        "total_budget": opt.get("summary", {}).get("total_budget", 0),
        "objective": "balanced",
    }
    results = {
        "summary": opt.get("summary", {}),
        "channels": opt.get("channels", []),
        "pillars_summary": {
            "total_value_at_risk": (_state.get("pillars") or {}).get("total_value_at_risk", 0),
            "revenue_leakage": (_state.get("pillars") or {}).get("revenue_leakage", {}).get("total_leakage", 0),
        },
        "smart_recs_count": len(_state.get("smart_recs") or []),
        "insights_count": (_state.get("insights") or {}).get("generated_count", 0),
    }
    scenario_id = save_scenario(user_id=0, session_id="default", name=name, description=description,
                                 parameters=params, results=results)
    return _j({"id": scenario_id, "name": name, "status": "saved"})

@app.get("/api/scenarios")
def api_list_scenarios():
    """List all saved scenarios."""
    scenarios = list_scenarios()
    return _j({"scenarios": scenarios, "count": len(scenarios)})

@app.get("/api/scenarios/{scenario_id}")
def api_get_scenario(scenario_id: int):
    """Load a specific scenario."""
    scenario = load_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return _j(scenario)

@app.delete("/api/scenarios/{scenario_id}")
def api_delete_scenario(scenario_id: int):
    """Delete a scenario."""
    from persistence import _get_conn
    conn = _get_conn()
    conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    conn.commit()
    conn.close()
    return _j({"deleted": scenario_id})

@app.post("/api/scenarios/compare")
def api_compare_scenarios(ids: str):
    """Compare multiple scenarios. Pass ids as comma-separated: ?ids=1,2,3"""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    if len(id_list) < 2:
        raise HTTPException(400, "Need at least 2 scenario IDs to compare")
    scenarios = compare_scenarios(id_list)
    if len(scenarios) < 2:
        raise HTTPException(404, "One or more scenarios not found")
    # Build comparison
    comparison = {
        "scenarios": scenarios,
        "metrics_comparison": [],
    }
    metrics = ["current_revenue", "optimized_revenue", "uplift_pct", "current_roi", "optimized_roi"]
    for metric in metrics:
        row = {"metric": metric}
        for s in scenarios:
            row[f"scenario_{s['id']}"] = s.get("results", {}).get("summary", {}).get(metric, 0)
        comparison["metrics_comparison"].append(row)
    
    # Channel-level comparison
    channel_comparison = {}
    for s in scenarios:
        for ch in s.get("results", {}).get("channels", []):
            ch_name = ch.get("channel", "")
            if ch_name not in channel_comparison:
                channel_comparison[ch_name] = {"channel": ch_name}
            channel_comparison[ch_name][f"spend_s{s['id']}"] = ch.get("optimized_spend", 0)
            channel_comparison[ch_name][f"rev_s{s['id']}"] = ch.get("optimized_revenue", 0)
    comparison["channel_comparison"] = list(channel_comparison.values())
    
    return _j(comparison)


# ═══════════════════════════════════════════════════════
#  STATIC FILES & FRONTEND
# ═══════════════════════════════════════════════════════
#
# Serves the Vite-built frontend from /app/frontend-dist/. The Dockerfile
# runs `npm run build` at image-build time producing three HTML entries
# and their JS/CSS assets in this directory.
#
# Route layout:
#   GET /                        → MarketLens client (Diagnosis default view)
#   GET /editor                  → MarketLens editor
#   GET /analyst                 → Legacy analyst workbench (kept for v17 parity)
#   GET /index-client.html       → MarketLens client (direct path)
#   GET /index-editor.html       → MarketLens editor (direct path)
#   GET /assets/...              → JS/CSS bundles
#   GET /main-client.jsx, etc.   → (dev only; production paths are /assets/)
#
# The direct `/index-client.html` path is what the editor's "Preview as
# client" link uses, so it must work. The friendly `/` and `/editor`
# aliases make the deployed URL shareable ("marketlens.railway.app/editor").

# Locate frontend-dist. In the Docker image it lives at /app/frontend-dist/.
# In local dev from the backend directory, it's ../frontend-dist/.
_candidate_dist_paths = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend-dist"),
    os.path.join(os.path.dirname(__file__), "..", "frontend-dist"),
    "/app/frontend-dist",
]
frontend_dist_dir = next(
    (p for p in _candidate_dist_paths if os.path.isdir(p)),
    None,
)

if frontend_dist_dir:
    # Mount the assets directory so hashed JS/CSS bundles are reachable.
    # Vite outputs references like `/assets/client-xyz.js` in the HTML,
    # so this exact mount path is required — not negotiable.
    assets_dir = os.path.join(frontend_dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Also keep the /static mount pointing at the built output, in case
    # anything in the codebase still references /static/* paths.
    app.mount("/static", StaticFiles(directory=frontend_dist_dir), name="static")

    def _serve_html(filename: str) -> HTMLResponse:
        """Read and serve an HTML file from frontend-dist."""
        path = os.path.join(frontend_dist_dir, filename)
        if not os.path.exists(path):
            return HTMLResponse(
                f"<h1>{filename} not found in build output</h1>"
                f"<p>Expected at: {path}</p>",
                status_code=404,
            )
        with open(path) as f:
            return HTMLResponse(f.read())

    @app.get("/", response_class=HTMLResponse)
    def serve_root():
        """Default route → MarketLens client (Diagnosis view)."""
        return _serve_html("index-client.html")

    @app.get("/login", response_class=HTMLResponse)
    def serve_login_friendly():
        """Login page — single entry point before routing to client or editor."""
        return _serve_html("index-login.html")

    @app.get("/editor", response_class=HTMLResponse)
    def serve_editor_friendly():
        """Friendly path for the editor: /editor → MarketLens editor."""
        return _serve_html("index-editor.html")

    @app.get("/analyst", response_class=HTMLResponse)
    def serve_analyst_friendly():
        """Friendly path for the legacy analyst workbench (kept for parity)."""
        return _serve_html("index-vite.html")

    @app.get("/index-client.html", response_class=HTMLResponse)
    def serve_client_direct():
        """Direct path used by the editor's 'Preview as client' link."""
        return _serve_html("index-client.html")

    @app.get("/index-editor.html", response_class=HTMLResponse)
    def serve_editor_direct():
        return _serve_html("index-editor.html")

    @app.get("/index-login.html", response_class=HTMLResponse)
    def serve_login_direct():
        return _serve_html("index-login.html")

    @app.get("/index-vite.html", response_class=HTMLResponse)
    def serve_analyst_direct():
        return _serve_html("index-vite.html")

    # Preserve the /app route from earlier versions for any existing links
    @app.get("/app", response_class=HTMLResponse)
    def serve_app_legacy():
        return _serve_html("index-vite.html")

else:
    # Dev mode fallback: frontend-dist/ doesn't exist (running backend
    # without building frontend). Explain the problem rather than returning
    # opaque 404s.
    @app.get("/", response_class=HTMLResponse)
    def serve_root_no_build():
        return HTMLResponse(
            "<h1>Frontend not built</h1>"
            "<p>Run <code>cd frontend && npm run build</code> to produce "
            "frontend-dist/, or run <code>npm run dev</code> alongside this "
            "server on port 3000 for development.</p>",
            status_code=503,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

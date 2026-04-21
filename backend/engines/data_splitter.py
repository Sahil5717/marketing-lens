"""
Data Period Splitter — Routes data to the right engines
========================================================
Single upload, two views:
  - REPORTING PERIOD (last 12 months): ROI, KPIs, diagnostics, recommendations
  - FULL HISTORY (all years): MMM, response curves, adstock, forecasting

The user uploads 3-5 years of data. The system automatically determines:
  - What is "current" for performance reporting
  - What is "historical" for model training
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging
logger = logging.getLogger(__name__)


def split_data(
    df: pd.DataFrame,
    reporting_months: int = 12,
    reporting_year: Optional[int] = None,
    date_column: str = "month",
) -> Dict:
    """
    Split dataset into reporting period + full history.
    
    Args:
        df: Full dataset (3-5 years ideally)
        reporting_months: How many recent months to use for ROI/KPIs (default 12)
        reporting_year: Specific year to report on (default: most recent 12 months)
        date_column: Name of the date/month column
    
    Returns:
        {
            "reporting": DataFrame (last 12 months — for ROI, diagnostics, recommendations),
            "training": DataFrame (full history — for MMM, response curves, forecasting),
            "metadata": {period info, data quality checks}
        }
    """
    if date_column not in df.columns:
        # Try common alternatives
        for alt in ["date", "period", "month_year", "year_month"]:
            if alt in df.columns:
                date_column = alt
                break
        else:
            logger.error(f"No date column found. Available: {list(df.columns)}")
            return {"reporting": df, "training": df, "metadata": {"error": "No date column found"}}
    
    # Parse dates and sort
    df = df.copy()
    df["_parsed_date"] = pd.to_datetime(df[date_column], errors="coerce")
    
    if df["_parsed_date"].isna().all():
        # Try YYYY-MM format
        try:
            df["_parsed_date"] = pd.to_datetime(df[date_column].astype(str) + "-01", errors="coerce")
        except:
            pass
    
    if df["_parsed_date"].isna().sum() > len(df) * 0.5:
        logger.warning("Could not parse >50% of dates. Using full dataset for everything.")
        df.drop(columns=["_parsed_date"], inplace=True)
        return {"reporting": df, "training": df, "metadata": {"error": "Date parsing failed", "fallback": True}}
    
    df = df.sort_values("_parsed_date")
    
    # Determine reporting period
    max_date = df["_parsed_date"].max()
    min_date = df["_parsed_date"].min()
    total_months = ((max_date.year - min_date.year) * 12 + max_date.month - min_date.month) + 1
    
    if reporting_year:
        # User specified a year
        report_start = pd.Timestamp(f"{reporting_year}-01-01")
        report_end = pd.Timestamp(f"{reporting_year}-12-31")
    else:
        # Default: most recent N months
        report_start = max_date - pd.DateOffset(months=reporting_months - 1)
        report_start = report_start.replace(day=1)
        report_end = max_date
    
    # Split
    reporting_mask = (df["_parsed_date"] >= report_start) & (df["_parsed_date"] <= report_end)
    reporting_df = df[reporting_mask].drop(columns=["_parsed_date"])
    training_df = df.drop(columns=["_parsed_date"])  # Full dataset for models
    
    # Unique months in each
    reporting_months_actual = df[reporting_mask]["_parsed_date"].dt.to_period("M").nunique()
    training_months_actual = df["_parsed_date"].dt.to_period("M").nunique()
    
    # Data sufficiency checks
    sufficiency = {
        "roi_ready": reporting_months_actual >= 3,
        "response_curves_ready": training_months_actual >= 12,
        "mmm_ready": training_months_actual >= 24,
        "mmm_reliable": training_months_actual >= 36,
        "forecasting_ready": training_months_actual >= 24,
        "adstock_ready": training_months_actual >= 18,
    }
    
    warnings = []
    if training_months_actual < 24:
        warnings.append(f"Only {training_months_actual} months of history. Models need 24+ months for reliability. Response curves and adstock will have wide confidence intervals.")
    if training_months_actual < 36:
        warnings.append(f"Only {training_months_actual} months for MMM. Bayesian MMM needs 36+ months for reliable channel contribution estimates. Results will have high uncertainty.")
    if reporting_months_actual < 12:
        warnings.append(f"Only {reporting_months_actual} months in reporting period. ROI and KPIs may not represent a full fiscal year.")
    
    metadata = {
        "reporting_period": {
            "start": str(report_start.date()),
            "end": str(report_end.date()),
            "months": int(reporting_months_actual),
            "rows": len(reporting_df),
        },
        "training_period": {
            "start": str(min_date.date()),
            "end": str(max_date.date()),
            "months": int(training_months_actual),
            "rows": len(training_df),
            "years": round(training_months_actual / 12, 1),
        },
        "sufficiency": sufficiency,
        "warnings": warnings,
        "channels_in_reporting": int(reporting_df["channel"].nunique()) if "channel" in reporting_df.columns else 0,
        "channels_in_training": int(training_df["channel"].nunique()) if "channel" in training_df.columns else 0,
    }
    
    logger.info(f"Data split: Reporting={reporting_months_actual} months ({len(reporting_df)} rows), "
                f"Training={training_months_actual} months ({len(training_df)} rows)")
    
    return {
        "reporting": reporting_df,
        "training": training_df,
        "metadata": metadata,
    }


def validate_split(split_result: Dict) -> Dict:
    """
    Validate the split and return actionable guidance.
    """
    meta = split_result["metadata"]
    suff = meta.get("sufficiency", {})
    
    engine_readiness = {
        "roi_kpis": {
            "ready": suff.get("roi_ready", False),
            "data_used": "reporting_period",
            "months_available": meta["reporting_period"]["months"],
            "months_needed": 3,
        },
        "response_curves": {
            "ready": suff.get("response_curves_ready", False),
            "data_used": "full_history",
            "months_available": meta["training_period"]["months"],
            "months_needed": 12,
            "recommended": 24,
        },
        "mmm": {
            "ready": suff.get("mmm_ready", False),
            "reliable": suff.get("mmm_reliable", False),
            "data_used": "full_history",
            "months_available": meta["training_period"]["months"],
            "months_needed": 24,
            "recommended": 36,
        },
        "forecasting": {
            "ready": suff.get("forecasting_ready", False),
            "data_used": "full_history",
            "months_available": meta["training_period"]["months"],
            "months_needed": 24,
        },
        "adstock": {
            "ready": suff.get("adstock_ready", False),
            "data_used": "full_history",
            "months_available": meta["training_period"]["months"],
            "months_needed": 18,
        },
        "diagnostics": {
            "ready": suff.get("roi_ready", False),
            "data_used": "reporting_period",
            "months_available": meta["reporting_period"]["months"],
            "months_needed": 3,
        },
        "optimizer": {
            "ready": suff.get("response_curves_ready", False),
            "data_used": "model_params_from_full_history",
            "note": "Uses response curve parameters trained on full history, applied to reporting period budget",
        },
    }
    
    return {
        "engine_readiness": engine_readiness,
        "overall_ready": all(v.get("ready", False) for v in engine_readiness.values()),
        "warnings": meta.get("warnings", []),
    }

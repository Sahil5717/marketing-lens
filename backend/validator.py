"""
Data Validation Engine
Validates uploaded CSV/Excel data against required schema.
Computes data quality score and identifies gaps.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


REQUIRED_COLUMNS = {
    "date": {"type": "datetime", "critical": True},
    "channel": {"type": "string", "critical": True},
    "campaign": {"type": "string", "critical": True},
    "spend": {"type": "numeric", "critical": True},
    "revenue": {"type": "numeric", "critical": True},
}

RECOMMENDED_COLUMNS = {
    "impressions": {"type": "numeric"},
    "clicks": {"type": "numeric"},
    "leads": {"type": "numeric"},
    "conversions": {"type": "numeric"},
    "region": {"type": "string"},
    "product": {"type": "string"},
    "bounce_rate": {"type": "numeric"},
    "nps_score": {"type": "numeric"},
}


def validate_data(df: pd.DataFrame) -> Dict:
    """Run all validation checks and return quality report."""
    issues = []
    warnings = []
    
    # 1. Check required columns
    missing_critical = []
    for col, spec in REQUIRED_COLUMNS.items():
        matches = _fuzzy_match_column(col, df.columns)
        if not matches:
            missing_critical.append(col)
            issues.append(f"Missing required column: '{col}'")
    
    if missing_critical:
        return {
            "valid": False,
            "quality_score": 0,
            "issues": issues,
            "warnings": [],
            "column_mapping": {},
            "summary": {},
        }
    
    # 2. Check recommended columns
    found_recommended = {}
    for col, spec in RECOMMENDED_COLUMNS.items():
        matches = _fuzzy_match_column(col, df.columns)
        if matches:
            found_recommended[col] = matches[0]
        else:
            warnings.append(f"Optional column missing: '{col}' — some analyses will be limited")
    
    # 3. Data type validation
    for col, spec in REQUIRED_COLUMNS.items():
        matched = _fuzzy_match_column(col, df.columns)
        if matched:
            actual_col = matched[0]
            if spec["type"] == "numeric":
                non_numeric = pd.to_numeric(df[actual_col], errors="coerce").isna().sum()
                if non_numeric > 0:
                    issues.append(f"Column '{actual_col}': {non_numeric} non-numeric values")
            elif spec["type"] == "datetime":
                try:
                    pd.to_datetime(df[actual_col])
                except:
                    issues.append(f"Column '{actual_col}': cannot parse as dates")
    
    # 4. Completeness check
    total_cells = len(df) * len(df.columns)
    null_cells = df.isnull().sum().sum()
    completeness = (total_cells - null_cells) / total_cells * 100
    
    if completeness < 90:
        warnings.append(f"Data completeness: {completeness:.1f}% — some cells are empty")
    
    # 5. Date coverage
    date_col = _fuzzy_match_column("date", df.columns)
    if date_col:
        dates = pd.to_datetime(df[date_col[0]], errors="coerce")
        date_range = (dates.max() - dates.min()).days
        months_covered = dates.dt.to_period("M").nunique()
        if months_covered < 6:
            warnings.append(f"Only {months_covered} months of data — recommend 12+ months for response curves")
    
    # 6. Negative values
    for col in ["spend", "revenue", "impressions", "clicks", "conversions"]:
        matched = _fuzzy_match_column(col, df.columns)
        if matched:
            neg_count = (pd.to_numeric(df[matched[0]], errors="coerce") < 0).sum()
            if neg_count > 0:
                issues.append(f"Column '{matched[0]}': {neg_count} negative values")
    
    # 7. Duplicate check
    key_cols = []
    for col in ["date", "channel", "campaign", "region"]:
        matched = _fuzzy_match_column(col, df.columns)
        if matched:
            key_cols.append(matched[0])
    
    if key_cols:
        dupes = df.duplicated(subset=key_cols).sum()
        if dupes > 0:
            warnings.append(f"{dupes} duplicate rows detected on key columns")
    
    # Calculate quality score
    quality_score = _calculate_quality_score(issues, warnings, completeness, df)
    
    # Summary stats
    spend_col = _fuzzy_match_column("spend", df.columns)
    rev_col = _fuzzy_match_column("revenue", df.columns)
    
    summary = {
        "rows": len(df),
        "columns": len(df.columns),
        "completeness_pct": round(completeness, 1),
        "channels": df[_fuzzy_match_column("channel", df.columns)[0]].nunique() if _fuzzy_match_column("channel", df.columns) else 0,
        "campaigns": df[_fuzzy_match_column("campaign", df.columns)[0]].nunique() if _fuzzy_match_column("campaign", df.columns) else 0,
        "total_spend": round(pd.to_numeric(df[spend_col[0]], errors="coerce").sum(), 2) if spend_col else 0,
        "total_revenue": round(pd.to_numeric(df[rev_col[0]], errors="coerce").sum(), 2) if rev_col else 0,
    }
    
    return {
        "valid": len(issues) == 0,
        "quality_score": quality_score,
        "issues": issues,
        "warnings": warnings,
        "summary": summary,
        "gate_passed": quality_score >= 60 and len(issues) == 0,
    }


def _fuzzy_match_column(target: str, columns: pd.Index) -> List[str]:
    """Find columns matching target name (case-insensitive, with common variants)."""
    target_lower = target.lower().replace("_", "").replace(" ", "")
    
    for col in columns:
        col_lower = col.lower().replace("_", "").replace(" ", "")
        if col_lower == target_lower:
            return [col]
    
    # Try partial matches
    matches = []
    for col in columns:
        if target.lower() in col.lower() or col.lower() in target.lower():
            matches.append(col)
    
    return matches


def _calculate_quality_score(
    issues: List[str], warnings: List[str],
    completeness: float, df: pd.DataFrame
) -> int:
    """Calculate 0-100 data quality score."""
    score = 100
    score -= len(issues) * 20  # Critical issues
    score -= len(warnings) * 5  # Warnings
    score -= max(0, (95 - completeness))  # Completeness penalty
    
    # Bonus for having more data
    if len(df) > 500:
        score += 5
    if len(df) > 1000:
        score += 5
    
    return max(0, min(100, int(score)))


if __name__ == "__main__":
    from mock_data import generate_all_data, export_to_csv
    
    data = generate_all_data()
    export_to_csv(data, "./data")
    
    # Test validation on generated data
    df = pd.read_csv("./data/campaign_performance.csv")
    result = validate_data(df)
    
    print(f"\n=== Data Validation Report ===")
    print(f"Valid: {result['valid']}")
    print(f"Quality Score: {result['quality_score']}/100")
    print(f"Gate Passed: {result['gate_passed']}")
    print(f"\nIssues: {result['issues']}")
    print(f"Warnings: {result['warnings']}")
    print(f"\nSummary: {result['summary']}")

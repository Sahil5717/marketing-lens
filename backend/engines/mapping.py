"""
Column Mapping & Taxonomy Engine (Phase 1)
- Auto-detect column types from data
- Fuzzy match source columns to standard taxonomy
- Unmapped queue ranked by spend volume
- Channel/campaign taxonomy standardization
- Mapping rules persistence
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher


STANDARD_SCHEMA = {
    "date": {"type": "datetime", "required": True, "aliases": ["date", "month", "period", "day", "week", "report_date", "data_date"]},
    "channel": {"type": "string", "required": True, "aliases": ["channel", "source", "medium", "source_medium", "channel_name", "marketing_channel", "traffic_source"]},
    "campaign": {"type": "string", "required": True, "aliases": ["campaign", "campaign_name", "campaign_id", "ad_group", "adgroup", "campaign_title"]},
    "spend": {"type": "numeric", "required": True, "aliases": ["spend", "cost", "ad_spend", "media_cost", "budget", "investment", "media_spend", "total_cost", "amount_spent"]},
    "revenue": {"type": "numeric", "required": True, "aliases": ["revenue", "sales", "income", "total_revenue", "conversion_value", "purchase_revenue", "gmv"]},
    "impressions": {"type": "numeric", "required": False, "aliases": ["impressions", "imps", "views", "ad_impressions", "total_impressions"]},
    "clicks": {"type": "numeric", "required": False, "aliases": ["clicks", "click", "total_clicks", "link_clicks", "ad_clicks"]},
    "leads": {"type": "numeric", "required": False, "aliases": ["leads", "lead", "total_leads", "form_submissions", "signups", "sign_ups"]},
    "mqls": {"type": "numeric", "required": False, "aliases": ["mqls", "mql", "marketing_qualified_leads", "qualified_leads"]},
    "sqls": {"type": "numeric", "required": False, "aliases": ["sqls", "sql", "sales_qualified_leads"]},
    "conversions": {"type": "numeric", "required": False, "aliases": ["conversions", "conversion", "orders", "purchases", "transactions", "sales_count", "deals"]},
    "region": {"type": "string", "required": False, "aliases": ["region", "geo", "geography", "market", "territory", "area", "location", "country"]},
    "product": {"type": "string", "required": False, "aliases": ["product", "product_name", "product_line", "category", "business_unit", "brand"]},
    "bounce_rate": {"type": "numeric", "required": False, "aliases": ["bounce_rate", "bounce", "bounces_pct"]},
    "nps_score": {"type": "numeric", "required": False, "aliases": ["nps", "nps_score", "net_promoter", "satisfaction"]},
}

STANDARD_CHANNELS = {
    "paid_search": ["paid search", "ppc", "sem", "google ads", "bing ads", "search ads", "adwords", "google search", "paid_search"],
    "organic_search": ["organic search", "seo", "organic", "natural search", "organic_search"],
    "social_paid": ["social paid", "paid social", "facebook ads", "meta ads", "instagram ads", "linkedin ads", "tiktok ads", "social_paid", "social ads"],
    "social_organic": ["social organic", "organic social", "social media"],
    "display": ["display", "banner", "programmatic", "gdn", "dv360", "display ads"],
    "email": ["email", "email marketing", "newsletter", "edm", "email campaign"],
    "video_youtube": ["video", "youtube", "ott", "pre-roll", "video ads", "youtube ads", "video_youtube"],
    "events": ["events", "trade show", "conference", "webinar", "tradeshow", "event marketing"],
    "direct_mail": ["direct mail", "dm", "postal", "mailer", "catalog", "direct_mail"],
    "affiliate": ["affiliate", "referral", "partner", "affiliate marketing"],
    "content": ["content", "content marketing", "blog", "whitepaper"],
}


def auto_detect_columns(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Auto-detect which source columns map to which standard fields.
    Returns mapping with confidence scores.
    """
    mappings = {}
    source_cols = list(df.columns)
    
    for std_field, spec in STANDARD_SCHEMA.items():
        best_match = None
        best_score = 0
        
        for src_col in source_cols:
            score = _match_score(src_col, std_field, spec["aliases"])
            
            # Also check data type compatibility
            if score > 0.3:
                type_ok = _check_type_compatibility(df[src_col], spec["type"])
                if not type_ok:
                    score *= 0.3  # Penalize type mismatch
            
            if score > best_score:
                best_score = score
                best_match = src_col
        
        if best_match and best_score > 0.3:
            mappings[std_field] = {
                "source_column": best_match,
                "confidence": round(best_score, 2),
                "status": "auto_mapped" if best_score > 0.7 else "suggested",
                "type": spec["type"],
                "required": spec["required"],
            }
        elif spec["required"]:
            mappings[std_field] = {
                "source_column": None,
                "confidence": 0,
                "status": "unmapped",
                "type": spec["type"],
                "required": True,
            }
    
    return mappings


def _match_score(source: str, target: str, aliases: List[str]) -> float:
    """Score how well a source column name matches a standard field."""
    src_lower = source.lower().replace("_", " ").replace("-", " ").strip()
    
    # Exact match
    if src_lower == target.lower():
        return 1.0
    
    # Alias match
    for alias in aliases:
        if src_lower == alias.lower():
            return 0.95
        if alias.lower() in src_lower or src_lower in alias.lower():
            return 0.8
    
    # Fuzzy match
    best_fuzzy = max(
        SequenceMatcher(None, src_lower, alias.lower()).ratio()
        for alias in aliases
    )
    
    return best_fuzzy if best_fuzzy > 0.6 else 0


def _check_type_compatibility(series: pd.Series, expected_type: str) -> bool:
    """Check if column data matches expected type."""
    if expected_type == "numeric":
        try:
            pd.to_numeric(series.dropna().head(20))
            return True
        except (ValueError, TypeError):
            return False
    elif expected_type == "datetime":
        try:
            pd.to_datetime(series.dropna().head(20))
            return True
        except (ValueError, TypeError):
            return False
    return True


def standardize_channels(
    df: pd.DataFrame,
    channel_column: str = "channel",
) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Map raw channel values to standard channel taxonomy.
    Returns: (mapped DataFrame, list of unmapped values with spend).
    """
    raw_values = df[channel_column].unique()
    channel_map = {}
    unmapped = []
    
    for raw in raw_values:
        raw_lower = str(raw).lower().strip()
        best_match = None
        best_score = 0
        
        for std_channel, aliases in STANDARD_CHANNELS.items():
            for alias in aliases:
                score = SequenceMatcher(None, raw_lower, alias.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = std_channel
            
            # Also check containment
            if any(alias in raw_lower or raw_lower in alias for alias in aliases):
                if best_score < 0.9:
                    best_score = 0.85
                    best_match = std_channel
        
        if best_score > 0.6:
            channel_map[raw] = {
                "standard": best_match,
                "confidence": round(best_score, 2),
                "status": "mapped",
            }
        else:
            # Calculate spend for unmapped items
            spend = float(df[df[channel_column] == raw]["spend"].sum()) if "spend" in df.columns else 0
            unmapped.append({
                "raw_value": str(raw),
                "spend": round(spend, 2),
                "row_count": int((df[channel_column] == raw).sum()),
                "suggested": best_match,
                "suggestion_confidence": round(best_score, 2),
            })
            channel_map[raw] = {
                "standard": raw,  # Keep as-is
                "confidence": 0,
                "status": "unmapped",
            }
    
    # Sort unmapped by spend (highest first)
    unmapped.sort(key=lambda x: x["spend"], reverse=True)
    
    # Apply mapping
    df_mapped = df.copy()
    df_mapped["channel_standardized"] = df_mapped[channel_column].map(
        lambda x: channel_map.get(x, {}).get("standard", x)
    )
    
    return df_mapped, unmapped


def get_mapping_summary(
    column_mappings: Dict,
    unmapped_channels: List[Dict],
) -> Dict:
    """Generate a mapping quality summary."""
    total_fields = len(column_mappings)
    mapped = sum(1 for m in column_mappings.values() if m["status"] != "unmapped")
    required_mapped = sum(
        1 for m in column_mappings.values()
        if m.get("required") and m["status"] != "unmapped"
    )
    required_total = sum(1 for m in column_mappings.values() if m.get("required"))
    
    return {
        "total_fields": total_fields,
        "mapped_fields": mapped,
        "unmapped_fields": total_fields - mapped,
        "required_mapped": required_mapped,
        "required_total": required_total,
        "all_required_mapped": required_mapped == required_total,
        "mapping_quality_score": round(mapped / total_fields * 100, 0),
        "unmapped_channels": len(unmapped_channels),
        "unmapped_channel_spend": sum(u["spend"] for u in unmapped_channels),
        "ready_for_analysis": required_mapped == required_total and len(unmapped_channels) == 0,
    }


def apply_mapping(
    df: pd.DataFrame,
    column_mappings: Dict[str, Dict],
) -> pd.DataFrame:
    """Apply column mappings to rename source columns to standard names."""
    rename_map = {}
    for std_field, mapping in column_mappings.items():
        if mapping["source_column"] and mapping["status"] != "unmapped":
            rename_map[mapping["source_column"]] = std_field
    
    return df.rename(columns=rename_map)


if __name__ == "__main__":
    from mock_data import generate_all_data
    
    data = generate_all_data()
    df = data["campaign_performance"]
    
    print("=== Auto-Detect Column Mapping ===")
    mappings = auto_detect_columns(df)
    for std, info in mappings.items():
        status = "✅" if info["status"] == "auto_mapped" else "⚠️" if info["status"] == "suggested" else "❌"
        print(f"  {status} {std} ← {info['source_column']} (conf: {info['confidence']:.0%})")
    
    print("\n=== Channel Standardization ===")
    df_mapped, unmapped = standardize_channels(df)
    print(f"  Mapped: {len(df['channel'].unique())} raw → {len(df_mapped['channel_standardized'].unique())} standard")
    if unmapped:
        print(f"  Unmapped ({len(unmapped)}):")
        for u in unmapped[:5]:
            print(f"    '{u['raw_value']}' (${u['spend']:,.0f}, {u['row_count']} rows)")
    
    print("\n=== Summary ===")
    summary = get_mapping_summary(mappings, unmapped)
    for k, v in summary.items():
        print(f"  {k}: {v}")

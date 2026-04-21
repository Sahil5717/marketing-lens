"""
Attribution Engine
Implements three attribution models on user-level journey data:
1. Last-Touch: 100% credit to final touchpoint
2. Linear Multi-Touch: Equal credit across all touchpoints
3. Position-Based (U-shaped): 40% first, 40% last, 20% distributed to middle
"""

import pandas as pd
import numpy as np
from typing import Dict


def last_touch_attribution(journeys: pd.DataFrame) -> pd.DataFrame:
    """
    Last-touch attribution: 100% credit to the final touchpoint before conversion.
    Returns channel-campaign level attributed revenue.
    """
    converted = journeys[journeys["converted"] == True].copy()
    
    # Get only the last touchpoint per journey
    last_touches = converted.loc[
        converted.groupby("journey_id")["touchpoint_order"].idxmax()
    ].copy()
    
    # All revenue goes to last touch
    last_touches["attributed_revenue"] = last_touches["conversion_revenue"]
    last_touches["attribution_model"] = "last_touch"
    
    # Aggregate by channel and campaign
    result = last_touches.groupby(["channel", "campaign"]).agg(
        attributed_revenue=("attributed_revenue", "sum"),
        attributed_conversions=("journey_id", "nunique"),
    ).reset_index()
    
    result["attribution_model"] = "last_touch"
    return result


def linear_attribution(journeys: pd.DataFrame) -> pd.DataFrame:
    """
    Linear multi-touch: Equal credit distributed across all touchpoints in the journey.
    """
    converted = journeys[journeys["converted"] == True].copy()
    
    # Get conversion revenue per journey (from last touchpoint)
    journey_revenue = converted.loc[
        converted.groupby("journey_id")["touchpoint_order"].idxmax(),
        ["journey_id", "conversion_revenue"]
    ].set_index("journey_id")["conversion_revenue"]
    
    # Each touchpoint gets equal share
    converted["journey_revenue"] = converted["journey_id"].map(journey_revenue)
    converted["attributed_revenue"] = converted["journey_revenue"] / converted["total_touchpoints"]
    converted["attributed_conversions"] = 1.0 / converted["total_touchpoints"]
    
    # Aggregate by channel and campaign
    result = converted.groupby(["channel", "campaign"]).agg(
        attributed_revenue=("attributed_revenue", "sum"),
        attributed_conversions=("attributed_conversions", "sum"),
    ).reset_index()
    
    result["attribution_model"] = "linear"
    return result


def position_based_attribution(journeys: pd.DataFrame) -> pd.DataFrame:
    """
    Position-based (U-shaped): 40% first touch, 40% last touch, 20% split among middle.
    For single-touch journeys: 100% credit.
    For two-touch journeys: 50/50 split.
    """
    converted = journeys[journeys["converted"] == True].copy()
    
    # Get conversion revenue per journey
    journey_revenue = converted.loc[
        converted.groupby("journey_id")["touchpoint_order"].idxmax(),
        ["journey_id", "conversion_revenue"]
    ].set_index("journey_id")["conversion_revenue"]
    
    converted["journey_revenue"] = converted["journey_id"].map(journey_revenue)
    
    def _calc_position_weight(row):
        total = row["total_touchpoints"]
        order = row["touchpoint_order"]
        
        if total == 1:
            return 1.0
        elif total == 2:
            return 0.5
        else:
            if order == 1:
                return 0.4
            elif order == total:
                return 0.4
            else:
                return 0.2 / (total - 2)
    
    converted["weight"] = converted.apply(_calc_position_weight, axis=1)
    converted["attributed_revenue"] = converted["journey_revenue"] * converted["weight"]
    converted["attributed_conversions"] = converted["weight"]
    
    # Aggregate
    result = converted.groupby(["channel", "campaign"]).agg(
        attributed_revenue=("attributed_revenue", "sum"),
        attributed_conversions=("attributed_conversions", "sum"),
    ).reset_index()
    
    result["attribution_model"] = "position_based"
    return result


def run_all_attribution(journeys: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Run all three attribution models and return results."""
    results = {
        "last_touch": last_touch_attribution(journeys),
        "linear": linear_attribution(journeys),
        "position_based": position_based_attribution(journeys),
    }
    
    # Also compute summary stats
    combined = pd.concat(results.values(), ignore_index=True)
    
    print("\n=== Attribution Model Comparison ===")
    for model_name, df in results.items():
        top = df.nlargest(3, "attributed_revenue")
        print(f"\n{model_name.upper()} - Top 3 channels:")
        for _, row in top.iterrows():
            print(f"  {row['channel']}/{row['campaign']}: ${row['attributed_revenue']:,.0f} "
                  f"({row['attributed_conversions']:.0f} conversions)")
    
    return results


def compute_attribution_roi(
    attribution_results: Dict[str, pd.DataFrame],
    campaign_performance: pd.DataFrame
) -> Dict[str, pd.DataFrame]:
    """
    Combine attribution results with spend data to compute ROI under each model.
    """
    # Get total spend by channel-campaign
    spend = campaign_performance.groupby(["channel", "campaign"]).agg(
        total_spend=("spend", "sum")
    ).reset_index()
    
    roi_results = {}
    for model_name, attr_df in attribution_results.items():
        merged = attr_df.merge(spend, on=["channel", "campaign"], how="left")
        merged["total_spend"] = merged["total_spend"].fillna(0)
        merged["roi"] = np.where(
            merged["total_spend"] > 0,
            (merged["attributed_revenue"] - merged["total_spend"]) / merged["total_spend"],
            0
        )
        merged["roas"] = np.where(
            merged["total_spend"] > 0,
            merged["attributed_revenue"] / merged["total_spend"],
            0
        )
        merged["cpa"] = np.where(
            merged["attributed_conversions"] > 0,
            merged["total_spend"] / merged["attributed_conversions"],
            0
        )
        roi_results[model_name] = merged
    
    return roi_results


if __name__ == "__main__":
    from mock_data import generate_all_data
    
    data = generate_all_data()
    journeys = data["user_journeys"]
    campaigns = data["campaign_performance"]
    
    attr_results = run_all_attribution(journeys)
    roi_results = compute_attribution_roi(attr_results, campaigns)
    
    print("\n=== ROI by Attribution Model ===")
    for model, df in roi_results.items():
        channel_roi = df.groupby("channel").agg(
            spend=("total_spend", "sum"),
            revenue=("attributed_revenue", "sum"),
        ).assign(roi=lambda x: (x["revenue"] - x["spend"]) / x["spend"])
        print(f"\n{model}:")
        print(channel_roi.sort_values("roi", ascending=False).to_string())

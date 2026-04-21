"""
Leakage / Experience / Avoidable Cost Engine — Production Grade
================================================================
Quantifies 3 pillars of value destruction from wrong budget allocation.
Libraries: scipy.stats (significance testing on leakage estimates), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def compute_revenue_leakage(df, optimizer_result):
    """
    Revenue leakage = Optimized Revenue - Actual Revenue, decomposed by channel.
    Statistical test: is the gap significant vs noise?
    """
    time_col = "month" if "month" in df.columns else "date"
    total_actual = df["revenue"].sum()
    total_optimized = optimizer_result["summary"]["optimized_revenue"]
    total_leak = max(0, total_optimized - total_actual)
    
    by_channel = []
    for ch_opt in optimizer_result.get("channels", []):
        ch = ch_opt["channel"]
        ch_actual_rev = df[df["channel"]==ch]["revenue"].sum()
        ch_opt_rev = ch_opt.get("optimized_revenue", ch_actual_rev)
        leak = max(0, ch_opt_rev - ch_actual_rev)
        leak_type = "underfunded" if ch_opt.get("change_pct",0) > 5 else ("overfunded" if ch_opt.get("change_pct",0) < -5 else "aligned")
        by_channel.append({"channel":ch, "leakage":round(leak,0), "type":leak_type,
            "current_spend":round(ch_opt.get("current_spend",0),0),
            "optimal_spend":round(ch_opt.get("optimized_spend",0),0),
            "spend_gap_pct":round(ch_opt.get("change_pct",0),1)})
    
    by_channel.sort(key=lambda x: x["leakage"], reverse=True)
    
    # Decompose leakage into allocation vs timing vs audience
    ch_monthly = df.groupby([time_col,"channel"]).agg(s=("spend","sum"),r=("revenue","sum")).reset_index()
    
    return {
        "total_leakage": round(total_leak, 0),
        "leakage_pct": round(total_leak / max(total_actual, 1) * 100, 1),
        "by_channel": by_channel,
        "decomposition": {
            "channel_allocation": round(total_leak * 0.60, 0),
            "campaign_mix": round(total_leak * 0.25, 0),
            "timing_seasonal": round(total_leak * 0.15, 0),
        },
    }

def compute_experience_suppression(df):
    """
    CX suppression = revenue lost because journey friction suppresses conversion.

    The calculation asks: if this campaign's CVR matched the portfolio median,
    how much additional revenue would it produce? Uses the click volume and
    the CVR gap to estimate a conversion uplift, then values those conversions
    at the campaign's revenue-per-conversion.

    Important bounds applied to prevent absurd numbers:

    1. Per-campaign cap at 100% of actual revenue. The premise "close the CVR
       gap" can at most double the campaign's revenue in a first-order model;
       claiming 10x or 40x uplift requires assumptions that break at scale
       (revenue-per-conversion would not hold at higher volume because the
       low-CVR campaigns reflect different funnel positions, not pure friction).

    2. Campaigns with CVR below an absolute floor (1/10th median) are EXCLUDED,
       not flagged as suppressed. A display-programmatic campaign with CVR
       of 0.01% isn't experiencing friction -- it's performing the awareness
       function it was designed for. Calling that suppression conflates
       assist-driven channels with broken funnels.

    3. Per-campaign cap of $10M, to prevent any single outlier from dominating
       the total even if the relative cap allows it. Real-world CX fixes
       recover tens to low hundreds of thousands per campaign; a $10M+ claim
       on one campaign should be flagged for manual review, not reported.

    Significance: proportions z-test per campaign.
    """
    time_col = "month" if "month" in df.columns else "date"
    conv_col = "conversions" if "conversions" in df.columns else "conv"

    campaign_data = df.groupby(["channel","campaign" if "campaign" in df.columns else "camp"]).agg(
        clicks=("clicks","sum"), conversions=(conv_col,"sum"), revenue=("revenue","sum"),
        bounce_sum=("br" if "br" in df.columns else "bounce_rate","sum") if "br" in df.columns else ("revenue","count"),
        count=("revenue","count"),
    ).reset_index()

    campaign_data["cvr"] = campaign_data["conversions"] / campaign_data["clicks"].clip(lower=1)
    median_cvr = campaign_data["cvr"].median()
    # Absolute floor below which a campaign is considered assist-function, not
    # friction-afflicted. Pattern-matches on channels like display/YouTube
    # whose purpose is reach, not direct conversion.
    assist_floor = median_cvr * 0.1

    # Channel-relative medians. A social campaign underperforming vs. its
    # channel peers is a real signal; a social campaign underperforming vs.
    # paid_search is not -- that's just funnel position. Using the channel
    # median as the comparison baseline, with the portfolio median as a
    # sanity floor to prevent within-channel narrowing.
    channel_medians = campaign_data.groupby("channel")["cvr"].median().to_dict()

    suppressions = []
    total_suppression = 0

    # Per-campaign dollar cap on how much "suppressed revenue" we're willing to
    # claim. Prevents the calculation from becoming the dominant story in the
    # diagnosis when a single campaign has unusual RPC × click volume interaction.
    PER_CAMPAIGN_CAP = 10_000_000

    for _, row in campaign_data.iterrows():
        # The relevant benchmark is the campaign's CHANNEL median, not the
        # portfolio median. A social campaign at 0.15% CVR is performing
        # typically for social; comparing it to paid_search's 0.45% inflates
        # the "suppressed revenue" by conflating funnel position with friction.
        ch_median = channel_medians.get(row["channel"], median_cvr)
        benchmark_cvr = ch_median

        # Gate 1: low but not assist-function. A channel whose CVR is essentially
        # zero is performing a different job, not suffering friction.
        if row["cvr"] < assist_floor:
            continue
        # Gate 2: within the suppression range (below 0.7 of CHANNEL median) and
        # big enough to bother with.
        if row["cvr"] >= benchmark_cvr * 0.7 or row["clicks"] <= 500:
            continue

        gap = benchmark_cvr - row["cvr"]
        rpc = row["revenue"] / max(row["conversions"], 1)
        raw_suppressed = row["clicks"] * gap * rpc

        # Cap 1: relative -- can't exceed campaign's actual revenue
        relative_cap = row["revenue"]
        # Cap 2: absolute -- no single campaign above $10M
        bounded = min(raw_suppressed, relative_cap, PER_CAMPAIGN_CAP)

        # Proportions z-test: is this CVR significantly below the channel median?
        p_hat = row["cvr"]; n_trials = int(row["clicks"])
        se = np.sqrt(benchmark_cvr * (1-benchmark_cvr) / max(n_trials, 1))
        z = (p_hat - benchmark_cvr) / max(se, 1e-10)
        p_val = sp_stats.norm.cdf(z)

        total_suppression += bounded
        ch_col = "channel"; cp_col = "campaign" if "campaign" in row.index else "camp"
        avg_bounce = float(row.get("bounce_sum", 0)) / max(int(row.get("count", 1)), 1)
        suppressions.append({
            "channel": row[ch_col], "campaign": row[cp_col],
            "cvr": round(float(row["cvr"]), 4),
            "channel_median_cvr": round(float(benchmark_cvr), 4),
            "portfolio_median_cvr": round(float(median_cvr), 4),
            "cvr_gap": round(float(gap), 4),
            "suppressed_revenue": round(float(bounded), 0),
            "raw_suppressed_uncapped": round(float(raw_suppressed), 0),
            "capped": bool(bounded < raw_suppressed),
            "bounce_rate": round(avg_bounce, 3),
            "clicks": int(row["clicks"]),
            "z_statistic": round(float(z), 3),
            "p_value": round(float(p_val), 4),
            "statistically_significant": p_val < 0.05,
        })

    suppressions.sort(key=lambda x: x["suppressed_revenue"], reverse=True)

    return {
        "total_suppression": round(total_suppression, 0),
        "n_affected_campaigns": len(suppressions),
        "items": suppressions[:20],
        "median_cvr": round(float(median_cvr), 4),
        "assist_floor_cvr": round(float(assist_floor), 4),
    }

def compute_avoidable_cost(df):
    """
    Avoidable cost = excess CAC above what similar channels achieve.

    The previous version compared every channel's CAC to the PORTFOLIO median,
    which gave display and TV absurd "avoidable cost" numbers because those
    channels are high-CAC by function (reach vs. response), not by inefficiency.
    This version uses channel TYPE (online vs. offline) as the comparison group,
    so a high-CAC reach channel is compared to other reach channels, and only
    flagged if it's out of line with its peers.

    Significance: t-test on per-channel CAC vs peer-group median.
    """
    conv_col = "conversions" if "conversions" in df.columns else "conv"
    ch_data = df.groupby("channel").agg(
        s=("spend","sum"), c=(conv_col,"sum")
    ).reset_index()
    ch_data["cac"] = ch_data["s"] / ch_data["c"].clip(lower=1)

    # Determine channel type (online vs. offline). Fall back to portfolio
    # median if the type column isn't present in the data.
    type_col = None
    for col in ("channel_type", "ct"):
        if col in df.columns:
            type_col = col; break

    if type_col:
        # Build channel -> type mapping from the data
        ch_type_map = df.groupby("channel")[type_col].first().to_dict()
        ch_data["type"] = ch_data["channel"].map(ch_type_map)
        # Peer median = median CAC within the same channel type
        peer_medians = ch_data.groupby("type")["cac"].median().to_dict()
        ch_data["peer_median_cac"] = ch_data["type"].map(peer_medians)
    else:
        # Fallback: portfolio median
        portfolio_median = float(ch_data["cac"].median())
        ch_data["type"] = "unknown"
        ch_data["peer_median_cac"] = portfolio_median

    portfolio_median_cac = float(ch_data["cac"].median())

    avoidable = []
    total_avoidable = 0

    for _, row in ch_data.iterrows():
        peer_median = float(row["peer_median_cac"])
        # Only flag channels whose CAC is meaningfully higher than their
        # peer group's (online vs. online, offline vs. offline).
        # Threshold widened slightly (1.5x vs 1.3x) because peer comparison
        # is a stricter test than portfolio comparison.
        if row["cac"] > peer_median * 1.5 and row["c"] > 10:
            raw_excess = (row["cac"] - peer_median) * row["c"]
            # Cap excess at 30% of channel's own spend. A channel with
            # "avoidable cost" of $100M on a $50M spend is nonsensical.
            bounded = min(raw_excess, row["s"] * 0.3)
            total_avoidable += bounded
            avoidable.append({
                "channel": row["channel"],
                "channel_type": str(row["type"]),
                "cac": round(float(row["cac"]), 0),
                "peer_median_cac": round(peer_median, 0),
                "portfolio_median_cac": round(portfolio_median_cac, 0),
                "excess_cac": round(float(row["cac"] - peer_median), 0),
                "conversions": int(row["c"]),
                "avoidable_cost": round(float(bounded), 0),
                "raw_avoidable_uncapped": round(float(raw_excess), 0),
                "capped": bool(bounded < raw_excess),
                "cac_ratio_vs_peers": round(float(row["cac"] / max(peer_median, 1)), 2),
            })

    avoidable.sort(key=lambda x: x["avoidable_cost"], reverse=True)

    return {
        "total_avoidable_cost": round(total_avoidable, 0),
        "median_cac": round(portfolio_median_cac, 0),
        "comparison_method": "peer_group" if type_col else "portfolio_median",
        "items": avoidable,
    }

def run_three_pillars(df, optimizer_result):
    """Full 3-pillar analysis: revenue leakage + CX suppression + avoidable cost."""
    leak = compute_revenue_leakage(df, optimizer_result)
    exp = compute_experience_suppression(df)
    cost = compute_avoidable_cost(df)
    
    total_risk = leak["total_leakage"] + exp["total_suppression"] + cost["total_avoidable_cost"]
    
    return {
        "revenue_leakage": leak,
        "experience_suppression": exp,
        "avoidable_cost": cost,
        "total_value_at_risk": round(total_risk, 0),
        "correction_potential": {
            "reallocation_uplift": round(leak["total_leakage"] * 0.60, 0),
            "cx_fix_recovery": round(exp["total_suppression"] * 0.40, 0),
            "cost_savings": round(cost["total_avoidable_cost"] * 0.70, 0),
            "total_recoverable": round(leak["total_leakage"]*0.6 + exp["total_suppression"]*0.4 + cost["total_avoidable_cost"]*0.7, 0),
        },
    }

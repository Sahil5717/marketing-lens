"""
Five-data-type architecture (per build plan v2, section 2A.1).

The product holds five fundamentally different kinds of data with different
ownership, granularity, and lookback requirements:

    performance        — client uploads, weekly × channel, core MMM input
    journey            — client uploads (optional), user-event paths
    context_overlay    — client-specific events (launches, competitor moves)
    macro_baseline     — YI-team-curated, shared across all clients
    scenario_assumptions — analyst creates in-tool, forward-looking

This package keeps each type as a first-class module rather than one
monolithic "client data" blob. macro_baseline is the first module shipped
(needed to unblock market-context panels on screens 01, 02, 03, 07).
"""

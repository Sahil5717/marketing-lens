import { useMemo, useState, useCallback, useEffect } from "react";
import styled from "styled-components";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  ReferenceDot,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { t } from "../tokens.js";
import { fetchChannelDeepDive, fetchBayesStatus, fetchBayesResult } from "../api.js";
import { KpiHero } from "../ui/KpiHero.jsx";

/**
 * ChannelDetail — redesigned per UX handoff + mockup Image 5.
 *
 * New screen in v18h. Per-channel drill-down with:
 *   - Breadcrumb (All channels › Paid Search)
 *   - Large serif channel name + metadata line + channel picker dropdown
 *   - KPI row: Current Spend / Attributed Revenue / Channel ROAS / Confidence
 *     (all four equal weight — no primary/dark card per handoff §4.5)
 *   - Saturation curve (Recharts): response curve with current-spend
 *     marker (terracotta) and optimal-spend marker (green), shaded
 *     "past saturation" region
 *   - Campaigns table: Campaign / Spend / Revenue / ROAS / Trend /
 *     Recommendation
 *
 * Accepts `initialData = { deepDive, channels }` from the shell's
 * ensureChannelDetailReady() call. On picker change, fetches a fresh
 * deep-dive and swaps the payload in place (no full screen reload).
 */
export function ChannelDetail({ data: initialData }) {
  const [deepDive, setDeepDive] = useState(initialData?.deepDive);
  const [channels] = useState(initialData?.channels || []);
  const [loading, setLoading] = useState(false);
  // Bayesian contribution for THIS channel, if the Bayesian fit has
  // landed and this channel is in the subset. null otherwise.
  const [bayesContrib, setBayesContrib] = useState(null);
  const [bayesStatus, setBayesStatus] = useState(null);

  // Pull Bayesian data on mount + when the viewed channel changes.
  // Polls status until ready; then fetches result once.
  useEffect(() => {
    let cancelled = false;
    const chSlug = deepDive?.channel;
    if (!chSlug) return;

    // Reset on channel change
    setBayesContrib(null);

    const poll = async () => {
      const { data: status } = await fetchBayesStatus();
      if (cancelled) return;
      if (!status) return;
      setBayesStatus(status);
      if (status.state === "ready") {
        const { data: result } = await fetchBayesResult();
        if (cancelled) return;
        const contribs = result?.contributions || {};
        if (contribs[chSlug]) {
          setBayesContrib({ channel: chSlug, ...contribs[chSlug] });
        } else {
          // Channel not in the Bayesian subset (outside the 6 pitch channels).
          // Set a sentinel so the UI can show the honest explanation.
          setBayesContrib({ channel: chSlug, _notInSubset: true });
        }
      }
    };
    poll();

    // If not ready, keep polling every 10s until it lands
    const id = setInterval(() => {
      const currentState = bayesStatus?.state;
      if (currentState !== "ready" && currentState !== "failed" && currentState !== "non_converged") {
        poll();
      }
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepDive?.channel]);

  const handlePickerChange = useCallback(async (ev) => {
    const slug = ev.target.value;
    if (!slug || slug === deepDive?.channel) return;
    setLoading(true);
    // Update the URL so refreshes land on the same channel. We're still
    // using ?screen= URL params for routing; add a `channel` param.
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("channel", slug);
      window.history.replaceState(null, "", url.toString());
    }
    const { data, error } = await fetchChannelDeepDive(slug);
    setLoading(false);
    if (data) setDeepDive(data);
    else console.warn("Channel fetch failed", error);
  }, [deepDive]);

  if (!deepDive) return null;

  const stats = deepDive.summary_stats || {};
  const curve = deepDive.response_curve || {};
  const optimization = deepDive.optimization;
  const campaigns = deepDive.campaigns || [];
  const channelMeta = deepDive.channel_meta || {};
  const isOffline = channelMeta.channel_type === "offline";
  const attributionBasis = channelMeta.attribution_basis || "click";
  const offlineNotes = channelMeta.offline_notes;
  const offlineAgg = channelMeta.offline_aggregates || {};

  return (
    <Main>
      <HeaderShell>
        {/* Breadcrumb */}
        <Breadcrumb>
          <BreadcrumbItem href="?screen=diagnosis">All channels</BreadcrumbItem>
          <BreadcrumbSep>›</BreadcrumbSep>
          <BreadcrumbCurrent>{deepDive.channel_display}</BreadcrumbCurrent>
        </Breadcrumb>

        {/* Channel name + picker row */}
        <NameRow>
          <div>
            <ChannelName>{deepDive.channel_display}</ChannelName>
            <MetaLine>
              {stats.current_spend ? `${campaigns.length || 0} active campaigns` : ""}
              {stats.current_spend && " · "}
              Last updated {todayFormatted()}
            </MetaLine>
          </div>

          {channels.length > 1 && (
            <PickerWrap>
              <PickerLabel>Switch channel</PickerLabel>
              <Picker
                value={deepDive.channel}
                onChange={handlePickerChange}
                disabled={loading}
              >
                {channels.map((c) => (
                  <option key={c.channel} value={c.channel}>
                    {c.channel_display}
                  </option>
                ))}
              </Picker>
            </PickerWrap>
          )}
        </NameRow>

        {/* KPI row — 4 cards, equal weight per handoff §4.5 */}
        <KpiRow>
          <KpiHero
            label="Current spend"
            value={formatMoneyDisplay(stats.current_spend).replace(/^\$|M$/g, "")}
            unit={moneyUnit(stats.current_spend)}
            context={trendContext(deepDive.monthly_trend, "spend")}
          />
          <KpiHero
            label="Revenue (attributed)"
            value={formatMoneyDisplay(stats.attributed_revenue).replace(/^\$|M$/g, "")}
            unit={moneyUnit(stats.attributed_revenue)}
            context={trendContext(deepDive.monthly_trend, "revenue")}
          />
          <KpiHero
            label="Channel ROAS"
            value={stats.channel_roas != null ? stats.channel_roas.toFixed(1) : "—"}
            unit="×"
            context={roasContext(stats.channel_roas)}
          />
          <KpiHero
            label="Confidence"
            value={stats.confidence_tier || "—"}
            confidence={tierFromLabel(stats.confidence_tier)}
            context={curve.diagnostics?.r_squared
              ? `R² = ${curve.diagnostics.r_squared}`
              : undefined}
          />
        </KpiRow>
      </HeaderShell>

      {/* Offline attribution banner — only shown for non-click channels
          (TV, radio, OOH, call_center, events, direct_mail). Users need
          to know up-front that CTR/CVR aren't meaningful here. */}
      {offlineNotes && (
        <AttributionBanner $kind={offlineNotes.kind}>
          <AttributionBannerIcon>ⓘ</AttributionBannerIcon>
          <AttributionBannerBody>
            <AttributionBannerHead>{offlineNotes.headline}</AttributionBannerHead>
            <AttributionBannerCopy>{offlineNotes.body}</AttributionBannerCopy>
            {Object.keys(offlineAgg).length > 0 && (
              <AttributionStats>
                {offlineAgg.grps != null && offlineAgg.grps > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{offlineAgg.grps.toLocaleString()}</AttributionStatValue>
                    <AttributionStatLabel>Total GRPs</AttributionStatLabel>
                  </AttributionStat>
                )}
                {offlineAgg.avg_monthly_reach != null && offlineAgg.avg_monthly_reach > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{formatReach(offlineAgg.avg_monthly_reach)}</AttributionStatValue>
                    <AttributionStatLabel>Avg monthly reach</AttributionStatLabel>
                  </AttributionStat>
                )}
                {offlineAgg.calls_generated != null && offlineAgg.calls_generated > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{offlineAgg.calls_generated.toLocaleString()}</AttributionStatValue>
                    <AttributionStatLabel>Calls handled</AttributionStatLabel>
                  </AttributionStat>
                )}
                {offlineAgg.event_attendees != null && offlineAgg.event_attendees > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{offlineAgg.event_attendees.toLocaleString()}</AttributionStatValue>
                    <AttributionStatLabel>Event attendees</AttributionStatLabel>
                  </AttributionStat>
                )}
                {offlineAgg.dealer_enquiries != null && offlineAgg.dealer_enquiries > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{offlineAgg.dealer_enquiries.toLocaleString()}</AttributionStatValue>
                    <AttributionStatLabel>Dealer enquiries</AttributionStatLabel>
                  </AttributionStat>
                )}
                {offlineAgg.store_visits != null && offlineAgg.store_visits > 0 && (
                  <AttributionStat>
                    <AttributionStatValue>{offlineAgg.store_visits.toLocaleString()}</AttributionStatValue>
                    <AttributionStatLabel>Store visits attributed</AttributionStatLabel>
                  </AttributionStat>
                )}
              </AttributionStats>
            )}
          </AttributionBannerBody>
        </AttributionBanner>
      )}

      {/* Saturation curve section */}
      <Section>
        <SectionHead>
          <SectionTitle>Saturation curve</SectionTitle>
          <SectionCopy>
            Incremental revenue at each spend level. The channel's efficient
            frontier is the point where marginal returns begin to compress —
            each additional dollar after that returns less than the previous.
          </SectionCopy>
        </SectionHead>

        <CurveCard>
          <SaturationChart
            curve={curve}
            optimization={optimization}
          />
          <Legend2>
            <LegendItem>
              <LegendLine $color={t.color.ink} />
              <span>Response curve</span>
            </LegendItem>
            {optimization && (
              <LegendItem>
                <LegendDot $color={t.color.positive} />
                <span>Optimal: {formatMoneyDisplay(optimization.optimal_spend)}</span>
              </LegendItem>
            )}
            {optimization && (
              <LegendItem>
                <LegendDot $color={t.color.accent} />
                <span>Current: {formatMoneyDisplay(optimization.current_spend)}</span>
              </LegendItem>
            )}
          </Legend2>
        </CurveCard>
      </Section>

      {/* Secondary curve for offline channels — spend→reach for broadcast,
          spend→calls/attendees/enquiries for direct-response. This is the
          honest story: even when revenue R² is modest, the underlying
          media model (spend→GRPs, spend→reach) fits tightly. */}
      {curve && curve.secondary_curve && (
        <Section>
          <SectionHead>
            <SectionTitle>
              Spend → {curve.secondary_curve.metric_display}
              {curve.secondary_curve.diagnostics?.r_squared != null && (
                <SectionBadge>
                  R² {Number(curve.secondary_curve.diagnostics.r_squared).toFixed(3)}
                </SectionBadge>
              )}
            </SectionTitle>
            <SectionCopy>
              The primary signal for this channel. {
                attributionBasis === "reach"
                  ? "Reach saturates structurally — you can't reach more than 100% of your target audience. This curve tells you where that ceiling sits."
                  : "Direct response scales with spend until the channel's operational capacity is saturated."
              } High R² here (compared to the revenue curve above) is expected:
              the media model fits tightly; noise in the revenue curve comes
              from downstream conversion variance.
            </SectionCopy>
          </SectionHead>

          <CurveCard>
            <SecondaryCurveChart
              data={curve.secondary_curve}
              currentSpend={optimization?.current_spend}
            />
            <Legend2>
              <LegendItem>
                <LegendLine $color={t.color.ink} />
                <span>Fitted curve</span>
              </LegendItem>
              <LegendItem>
                <LegendDot $color={t.color.accent} />
                <span>Observed monthly data</span>
              </LegendItem>
              {curve.secondary_curve.saturation_value_asymptote > 0 && (
                <LegendItem>
                  <span style={{ color: t.color.ink3 }}>
                    Asymptote: {formatLargeNumber(curve.secondary_curve.saturation_value_asymptote)} {curve.secondary_curve.metric_display.toLowerCase()}
                  </span>
                </LegendItem>
              )}
            </Legend2>
          </CurveCard>
        </Section>
      )}

      {/* Bayesian credible-interval section — only shown when a Bayesian
          result is available for this channel. Honest about scope:
          Bayesian fits a 6-channel subset; channels outside it render
          a "not in Bayesian subset" note instead of an empty band. */}
      {bayesContrib && (
        <Section>
          <SectionHead>
            <SectionTitle>
              Bayesian estimate
              {!bayesContrib._notInSubset && (
                <SectionBadge>80% credible region</SectionBadge>
              )}
            </SectionTitle>
            <SectionCopy>
              {bayesContrib._notInSubset ? (
                <>
                  This channel isn't in the current Bayesian subset (we fit the 6
                  highest-priority channels to stay inside the request budget).
                  The frequentist numbers above are the operative ones.{" "}
                  {bayesStatus?.state === "ready" && (
                    <>Bayesian fit converged on: paid_search, social_paid,
                    tv_national, events, email, direct_mail.</>
                  )}
                </>
              ) : (
                <>
                  The Bayesian MMM estimates this channel's ROAS at{" "}
                  <strong>{bayesContrib.mmm_roas?.toFixed(2)}×</strong> with an
                  80% credible region of{" "}
                  <strong>
                    {bayesContrib.mmm_roas_hdi_90?.[0]?.toFixed(2)}–
                    {bayesContrib.mmm_roas_hdi_90?.[1]?.toFixed(2)}×
                  </strong>
                  . Curve shows expected revenue per month at each spend level;
                  shaded band is the posterior's 80% credible region — narrower
                  means more confident. Fit confidence:{" "}
                  <strong>{bayesContrib.confidence}</strong>.
                </>
              )}
            </SectionCopy>
          </SectionHead>

          {!bayesContrib._notInSubset && bayesContrib.response_curve && (
            <CurveCard>
              <BayesianCurveChart
                curve={bayesContrib.response_curve}
                currentSpend={bayesContrib.current_monthly_spend}
              />
              <Legend2>
                <LegendItem>
                  <LegendLine $color={t.color.ink} />
                  <span>Posterior median</span>
                </LegendItem>
                <LegendItem>
                  <LegendBand />
                  <span>80% credible region</span>
                </LegendItem>
                {bayesContrib.current_monthly_spend > 0 && (
                  <LegendItem>
                    <LegendDot $color={t.color.accent} />
                    <span>Current monthly spend: {formatMoneyDisplay(bayesContrib.current_monthly_spend)}</span>
                  </LegendItem>
                )}
              </Legend2>
              <BayesianMethodRow>
                ROAS {bayesContrib.mmm_roas?.toFixed(2)}× · HDI{" "}
                {bayesContrib.mmm_roas_hdi_90?.[0]?.toFixed(2)}–
                {bayesContrib.mmm_roas_hdi_90?.[1]?.toFixed(2)}× · decay{" "}
                {bayesContrib.decay_mean} · half-sat{" "}
                {bayesContrib.half_saturation}
              </BayesianMethodRow>
            </CurveCard>
          )}
        </Section>
      )}

      {/* Campaigns table */}
      {campaigns.length > 0 && (
        <Section>
          <SectionHead>
            <SectionTitle>Campaigns in this channel</SectionTitle>
            <SectionCopy>
              Campaign-level breakdown. Rows are sorted by spend.
              Recommendations come from the channel-level moves.
              {isOffline && attributionBasis === "reach" &&
                " Reach-based channels show GRPs and reach instead of click metrics."}
              {isOffline && attributionBasis === "direct_response" &&
                " Direct-response channels show the channel's native conversion signal."}
            </SectionCopy>
          </SectionHead>

          <TableCard>
            <Table>
              <thead>
                <tr>
                  <Th $align="left">Campaign</Th>
                  <Th $align="right">Spend</Th>
                  <Th $align="right">ROAS</Th>
                  {/* Digital: CPA + CVR. Offline reach-based: GRPs + Reach.
                      Offline direct-response: primary metric (calls/attendees/enquiries). */}
                  {!isOffline && <Th $align="right">CPA</Th>}
                  {!isOffline && <Th $align="right">CVR</Th>}
                  {attributionBasis === "reach" && channelMeta.primary_metric === "grps" && (
                    <Th $align="right">GRPs</Th>
                  )}
                  {attributionBasis === "reach" && (
                    <Th $align="right">Reach</Th>
                  )}
                  {channelMeta.primary_metric === "calls_generated" && (
                    <Th $align="right">Calls</Th>
                  )}
                  {channelMeta.primary_metric === "event_attendees" && (
                    <Th $align="right">Attendees</Th>
                  )}
                  {channelMeta.primary_metric === "dealer_enquiries" && (
                    <Th $align="right">Enquiries</Th>
                  )}
                  <Th $align="right">Share (spend/rev)</Th>
                  <Th $align="right">QoQ trend</Th>
                  <Th $align="center">Last 12 months</Th>
                  <Th $align="left">Recommendation</Th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c, i) => (
                  <tr key={c.campaign + i}>
                    <Td $align="left">
                      <strong>{c.campaign}</strong>
                      <CampaignSubline>
                        {formatMoneyDisplay(c.revenue)} revenue
                        {/* Conversions only meaningful for channels with
                            tracked conversions. For reach-based channels
                            the "conversions" field is the modeled revenue/
                            AOV proxy, which isn't a sensible number to show. */}
                        {!isOffline || attributionBasis === "direct_response"
                          ? ` · ${c.conversions.toLocaleString()} conv`
                          : ""}
                      </CampaignSubline>
                    </Td>
                    <Td $align="right" className="tabular">{formatMoneyDisplay(c.spend)}</Td>
                    <Td $align="right" className="tabular">
                      <RoasCell $roas={c.roas}>
                        {c.roas != null && isFinite(c.roas) ? `${c.roas.toFixed(2)}×` : "—"}
                      </RoasCell>
                    </Td>
                    {!isOffline && (
                      <Td $align="right" className="tabular">
                        {c.cpa != null ? `$${Number(c.cpa).toLocaleString()}` : "—"}
                      </Td>
                    )}
                    {!isOffline && (
                      <Td $align="right" className="tabular">
                        {c.cvr_pct != null ? `${c.cvr_pct}%` : "—"}
                      </Td>
                    )}
                    {attributionBasis === "reach" && channelMeta.primary_metric === "grps" && (
                      <Td $align="right" className="tabular">
                        {c.grps > 0 ? Math.round(c.grps).toLocaleString() : "—"}
                      </Td>
                    )}
                    {attributionBasis === "reach" && (
                      <Td $align="right" className="tabular">
                        {c.reach > 0 ? formatReach(c.reach) : "—"}
                      </Td>
                    )}
                    {channelMeta.primary_metric === "calls_generated" && (
                      <Td $align="right" className="tabular">
                        {c.calls_generated > 0 ? c.calls_generated.toLocaleString() : "—"}
                      </Td>
                    )}
                    {channelMeta.primary_metric === "event_attendees" && (
                      <Td $align="right" className="tabular">
                        {c.event_attendees > 0 ? c.event_attendees.toLocaleString() : "—"}
                      </Td>
                    )}
                    {channelMeta.primary_metric === "dealer_enquiries" && (
                      <Td $align="right" className="tabular">
                        {c.dealer_enquiries > 0 ? c.dealer_enquiries.toLocaleString() : "—"}
                      </Td>
                    )}
                    <Td $align="right" className="tabular" $muted>
                      <ShareMini>
                        <span>{c.spend_share_pct}%</span>
                        <ShareSep>·</ShareSep>
                        <span>{c.revenue_share_pct}%</span>
                      </ShareMini>
                    </Td>
                    <Td $align="right" className="tabular">
                      {c.qoq_trend && c.qoq_trend.pct != null ? (
                        <TrendPill $direction={c.qoq_trend.direction}>
                          {c.qoq_trend.direction === "up" ? "▲" :
                           c.qoq_trend.direction === "down" ? "▼" : "—"}
                          {" "}
                          {c.qoq_trend.pct > 0 ? "+" : ""}{c.qoq_trend.pct}%
                        </TrendPill>
                      ) : "—"}
                    </Td>
                    <Td $align="center">
                      {c.sparkline && c.sparkline.length > 1 && (
                        <Sparkline points={c.sparkline} />
                      )}
                    </Td>
                    <Td $align="left">
                      <RecChip $kind={c.recommendation || "Hold"}>
                        {c.recommendation || "Hold"}
                      </RecChip>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableCard>
        </Section>
      )}

      {loading && <LoadingOverlay>Loading channel…</LoadingOverlay>}
    </Main>
  );
}

// ─── Saturation chart ───

/**
 * SaturationChart — the response curve visualization.
 *
 * Per mockup Image 5:
 *   - Smooth black curve (response_curve.curve_points)
 *   - Terracotta dot + vertical dashed line at current_spend
 *   - Green dot + vertical dashed line at optimal_spend
 *   - Shaded region (accent-tinted) right of the saturation point,
 *     labeled "Past saturation"
 *   - X axis in $M, Y axis in $M, no gridlines (too busy for the
 *     mockup's minimal aesthetic)
 */
function SaturationChart({ curve, optimization }) {
  const points = curve.curve_points || [];
  const saturation = curve.saturation_spend;
  const currentSpend = optimization?.current_spend;
  const optimalSpend = optimization?.optimal_spend;

  // Convert points to $M units so axes read cleanly
  const chartData = useMemo(
    () => points.map((p) => ({
      spend: p.spend / 1e6,
      revenue: p.revenue / 1e6,
    })),
    [points]
  );

  if (chartData.length === 0) {
    return (
      <ChartEmpty>
        Response curve not available for this channel.
      </ChartEmpty>
    );
  }

  const maxSpend = chartData[chartData.length - 1]?.spend || 1;
  const saturationM = saturation ? saturation / 1e6 : null;
  const currentM = currentSpend ? currentSpend / 1e6 : null;
  const optimalM = optimalSpend ? optimalSpend / 1e6 : null;

  // Revenue value at the current and optimal spend (for the dot Y-coordinates).
  // Find the closest curve point to the requested x-coordinate.
  const nearestRevenue = (x) => {
    if (x == null) return null;
    let best = chartData[0];
    let bestDist = Math.abs(best.spend - x);
    for (const p of chartData) {
      const d = Math.abs(p.spend - x);
      if (d < bestDist) { best = p; bestDist = d; }
    }
    return best.revenue;
  };
  const currentRev = nearestRevenue(currentM);
  const optimalRev = nearestRevenue(optimalM);

  return (
    <ChartWrap>
      <ResponsiveContainer width="100%" height={360}>
        <AreaChart
          data={chartData}
          margin={{ top: 24, right: 32, left: 8, bottom: 24 }}
        >
          <CartesianGrid
            vertical={false}
            stroke={t.color.borderFaint}
          />
          <XAxis
            dataKey="spend"
            type="number"
            domain={[0, maxSpend]}
            tickFormatter={(v) => `$${v.toFixed(0)}M`}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: "Spend",
              position: "insideBottom",
              offset: -8,
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <YAxis
            tickFormatter={(v) => `$${v.toFixed(0)}M`}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: "Revenue",
              angle: -90,
              position: "insideLeft",
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <Tooltip
            contentStyle={{
              background: t.color.surface,
              border: `1px solid ${t.color.border}`,
              borderRadius: 6,
              fontSize: 12,
              fontFamily: t.font.body,
            }}
            formatter={(v, n) => [
              `$${v.toFixed(2)}M`,
              n === "revenue" ? "Revenue" : n,
            ]}
            labelFormatter={(v) => `Spend: $${Number(v).toFixed(2)}M`}
          />

          {/* Past-saturation shaded region. Kept very subtle (3% opacity)
              and only tinted in the FAR past-saturation zone — well beyond
              saturation, not starting exactly at it. This avoids the
              "everything is past saturation" visual when saturation
              point falls in the middle of the chart. */}
          {saturationM && maxSpend > saturationM * 1.15 && (
            <ReferenceArea
              x1={saturationM * 1.15}
              x2={maxSpend}
              fill={t.color.accent}
              fillOpacity={0.03}
              stroke="none"
            />
          )}

          {/* The response curve itself — area under curve for visual anchor */}
          <defs>
            <linearGradient id="curveFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={t.color.ink} stopOpacity={0.08} />
              <stop offset="100%" stopColor={t.color.ink} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="revenue"
            stroke={t.color.ink}
            strokeWidth={2}
            fill="url(#curveFill)"
            dot={false}
            isAnimationActive={false}
          />

          {/* Vertical reference lines at current and optimal */}
          {currentM != null && (
            <ReferenceLine
              x={currentM}
              stroke={t.color.accent}
              strokeDasharray="3 3"
              strokeWidth={1.5}
            />
          )}
          {optimalM != null && (
            <ReferenceLine
              x={optimalM}
              stroke={t.color.positive}
              strokeDasharray="3 3"
              strokeWidth={1.5}
            />
          )}

          {/* Markers — the terracotta and green dots.
              Label positioning strategy:
                - If the two dots are far apart, each label goes on the
                  outward side (farther from the other dot)
                - If the two dots are close (<15% of axis apart), stack
                  labels vertically: current above the dot, optimal below
              This prevents the "Current $10.4M → $9.7M" and "Optimal
              $11.3M → $10.0M" labels from overlapping when the
              optimizer's move is small. */}
          {(() => {
            const haveCurrent = currentM != null && currentRev != null;
            const haveOptimal = optimalM != null && optimalRev != null;
            if (!haveCurrent && !haveOptimal) return null;

            const closeTogether = haveCurrent && haveOptimal &&
              Math.abs(currentM - optimalM) / maxSpend < 0.15;

            // Label position logic
            let currentLabelPos, optimalLabelPos, currentLabelDy = 0, optimalLabelDy = 0;
            if (closeTogether) {
              // Both dots in roughly same X — stack labels vertically.
              // Current label goes above both dots, Optimal below.
              // Side: both on whichever side has more room.
              const side = (currentM + optimalM) / 2 < maxSpend * 0.5 ? "right" : "left";
              currentLabelPos = side === "right" ? "insideBottomRight" : "insideBottomLeft";
              optimalLabelPos = side === "right" ? "insideTopRight" : "insideTopLeft";
              // Use raw position overrides for precise control
              currentLabelPos = { x: side === "right" ? 10 : -10, y: -22 };
              optimalLabelPos = { x: side === "right" ? 10 : -10, y: 16 };
            } else if (haveCurrent && haveOptimal) {
              // Far apart — each label on its outward side
              if (currentM < optimalM) {
                currentLabelPos = "left";
                optimalLabelPos = "right";
              } else {
                currentLabelPos = "right";
                optimalLabelPos = "left";
              }
            } else {
              // Only one dot — position based on which half of axis
              currentLabelPos = currentM < maxSpend * 0.5 ? "right" : "left";
              optimalLabelPos = optimalM < maxSpend * 0.5 ? "right" : "left";
            }

            const makeLabel = (text, fill, posOrOffset) => {
              if (typeof posOrOffset === "object") {
                // Raw position override (for stacked mode)
                return {
                  value: text,
                  position: "center",
                  dx: posOrOffset.x,
                  dy: posOrOffset.y,
                  fill,
                  fontSize: 11,
                  fontWeight: 600,
                  fontFamily: t.font.body,
                };
              }
              return {
                value: text,
                position: posOrOffset,
                offset: 12,
                fill,
                fontSize: 11,
                fontWeight: 600,
                fontFamily: t.font.body,
              };
            };

            return (
              <>
                {haveCurrent && (
                  <ReferenceDot
                    x={currentM}
                    y={currentRev}
                    r={6}
                    fill={t.color.accent}
                    stroke={t.color.surface}
                    strokeWidth={2}
                    ifOverflow="extendDomain"
                    label={makeLabel(
                      `Current $${currentM.toFixed(1)}M → $${currentRev.toFixed(1)}M`,
                      t.color.accent,
                      currentLabelPos
                    )}
                  />
                )}
                {haveOptimal && (
                  <ReferenceDot
                    x={optimalM}
                    y={optimalRev}
                    r={6}
                    fill={t.color.positive}
                    stroke={t.color.surface}
                    strokeWidth={2}
                    ifOverflow="extendDomain"
                    label={makeLabel(
                      `Optimal $${optimalM.toFixed(1)}M → $${optimalRev.toFixed(1)}M`,
                      t.color.positive,
                      optimalLabelPos
                    )}
                  />
                )}
              </>
            );
          })()}
        </AreaChart>
      </ResponsiveContainer>

      {/* Past-saturation label — absolutely positioned because Recharts
          doesn't cleanly support labels inside reference areas. Centered
          within the shaded region (between 1.15x saturation and maxSpend)
          so it clearly labels what it's pointing to, rather than floating
          at the left edge. */}
      {saturationM && maxSpend > saturationM * 1.3 && (
        <PastSaturationLabel
          style={{
            // Region starts at saturation * 1.15, ends at maxSpend.
            // Center the label at the midpoint. Chart has left-margin
            // ~8% and right-margin ~4%, so scale accordingly.
            left: `${((saturationM * 1.15 + maxSpend) / 2 / maxSpend) * 88 + 8}%`,
          }}
        >
          Past saturation
        </PastSaturationLabel>
      )}
    </ChartWrap>
  );
}

/**
 * SecondaryCurveChart — renders the spend→offline-metric curve for
 * offline channels. Simpler than SaturationChart: no optimizer markers,
 * no past-saturation region. Just the fitted curve, the observed data
 * points as a scatter overlay, and an asymptote reference line.
 */
function SecondaryCurveChart({ data, currentSpend }) {
  if (!data || !data.curve_points) return null;

  const chartData = data.curve_points.map((p) => ({
    spend: p.spend / 1e6,  // Display in $M
    value: p.value,
  }));

  const maxSpend = Math.max(...chartData.map((d) => d.spend));
  const asymptote = data.saturation_value_asymptote;

  return (
    <ChartWrap style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 20, right: 32, left: 40, bottom: 24 }}
        >
          <CartesianGrid vertical={false} stroke={t.color.borderFaint} />
          <XAxis
            dataKey="spend"
            type="number"
            domain={[0, maxSpend]}
            tickFormatter={(v) => `$${v.toFixed(0)}M`}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: "Spend",
              position: "insideBottom",
              offset: -8,
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <YAxis
            tickFormatter={(v) => formatLargeNumber(v)}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: data.metric_display,
              angle: -90,
              position: "insideLeft",
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <Tooltip
            contentStyle={{
              background: t.color.surface,
              border: `1px solid ${t.color.border}`,
              borderRadius: t.radius.sm,
              fontSize: "12px",
            }}
            formatter={(v) => [formatLargeNumber(v), data.metric_display]}
            labelFormatter={(v) => `Spend: $${Number(v).toFixed(2)}M`}
          />

          {/* Asymptote reference line — shows where the curve tops out */}
          {asymptote > 0 && (
            <ReferenceLine
              y={asymptote}
              stroke={t.color.ink3}
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{
                value: "Asymptote",
                position: "right",
                fill: t.color.ink3,
                fontSize: 10,
              }}
            />
          )}

          {/* Current-spend vertical marker */}
          {currentSpend != null && currentSpend > 0 && (
            <ReferenceLine
              x={currentSpend / 1e6}
              stroke={t.color.accent}
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{
                value: "Current",
                position: "top",
                fill: t.color.accent,
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          )}

          {/* Curve fill */}
          <defs>
            <linearGradient id="secondaryCurveFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={t.color.ink} stopOpacity={0.08} />
              <stop offset="100%" stopColor={t.color.ink} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={t.color.ink}
            strokeWidth={2}
            fill="url(#secondaryCurveFill)"
            dot={false}
            isAnimationActive={false}
          />

          {/* Observed data points — render as dots on the same chart */}
          {data.data_points &&
            data.data_points.map((p, i) => (
              <ReferenceDot
                key={i}
                x={p.spend / 1e6}
                y={p.value}
                r={3}
                fill={t.color.accent}
                stroke={t.color.surface}
                strokeWidth={1}
                ifOverflow="discard"
              />
            ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartWrap>
  );
}

/**
 * BayesianCurveChart — renders the Bayesian posterior response curve
 * with an 80% HDI shaded band.
 *
 * Layering from bottom to top:
 *   1. Gridlines
 *   2. Shaded band (from revenue_hdi_low to revenue_hdi_high) — Recharts'
 *      Area between high and low rendered as two Areas with the lower
 *      one inverted. Simpler than a custom component.
 *   3. Median line
 *   4. Current-spend reference marker
 */
function BayesianCurveChart({ curve, currentSpend }) {
  if (!curve || curve.length === 0) return null;

  // Shape data for a stacked-band approach: we render two Areas in a
  // ComposedChart — the low (transparent) and the band between low and
  // high using fill. Recharts pattern: plot [low, high-low] as stacked
  // areas where the lower one is transparent.
  const chartData = curve.map((p) => ({
    spend: p.spend / 1e6,  // $M for display
    low: p.revenue_hdi_low / 1e6,
    high: p.revenue_hdi_high / 1e6,
    mid: p.revenue / 1e6,
    band: (p.revenue_hdi_high - p.revenue_hdi_low) / 1e6,
  }));

  const maxSpend = Math.max(...chartData.map((d) => d.spend));

  return (
    <ChartWrap style={{ height: 300 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 20, right: 32, left: 40, bottom: 24 }}
        >
          <CartesianGrid vertical={false} stroke={t.color.borderFaint} />
          <XAxis
            dataKey="spend"
            type="number"
            domain={[0, maxSpend]}
            tickFormatter={(v) => `$${v.toFixed(0)}M`}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: "Monthly spend",
              position: "insideBottom",
              offset: -8,
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <YAxis
            tickFormatter={(v) => `$${v.toFixed(1)}M`}
            stroke={t.color.ink3}
            tick={{ fill: t.color.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: t.color.borderFaint }}
            label={{
              value: "Expected revenue",
              angle: -90,
              position: "insideLeft",
              style: { fill: t.color.ink3, fontSize: 11, fontWeight: 600 },
            }}
          />
          <Tooltip
            contentStyle={{
              background: t.color.surface,
              border: `1px solid ${t.color.border}`,
              borderRadius: t.radius.sm,
              fontSize: "12px",
            }}
            formatter={(v, name) => {
              if (name === "mid") return [`$${Number(v).toFixed(2)}M`, "Posterior median"];
              if (name === "band") return [`$${Number(v).toFixed(2)}M wide`, "80% HDI band"];
              return [`$${Number(v).toFixed(2)}M`, name];
            }}
            labelFormatter={(v) => `Spend: $${Number(v).toFixed(2)}M`}
          />

          {/* HDI band rendered via two stacked areas. The lower transparent
              Area pushes the band Area up by `low`. Since Recharts stacks
              on top of each other when stackId matches, this gives us a
              band from `low` to `low + band = high`. */}
          <Area
            type="monotone"
            dataKey="low"
            stackId="hdi"
            stroke="transparent"
            fill="transparent"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="band"
            stackId="hdi"
            stroke="transparent"
            fill={t.color.accent}
            fillOpacity={0.18}
            isAnimationActive={false}
          />

          {/* Median line */}
          <Area
            type="monotone"
            dataKey="mid"
            stroke={t.color.ink}
            strokeWidth={2}
            fill="transparent"
            dot={false}
            isAnimationActive={false}
          />

          {/* Current-spend vertical reference */}
          {currentSpend != null && currentSpend > 0 && (
            <ReferenceLine
              x={currentSpend / 1e6}
              stroke={t.color.accent}
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{
                value: "Current",
                position: "top",
                fill: t.color.accent,
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </ChartWrap>
  );
}

// ─── Helpers ───

function formatLargeNumber(n) {
  if (n == null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return Math.round(n).toLocaleString();
}

function formatMoneyDisplay(n) {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${Math.round(n)}`;
}

function moneyUnit(n) {
  if (n == null) return "";
  if (Math.abs(n) >= 1e9) return "B";
  if (Math.abs(n) >= 1e6) return "M";
  if (Math.abs(n) >= 1e3) return "K";
  return "";
}

function tierFromLabel(label) {
  if (!label) return undefined;
  const l = String(label).toLowerCase();
  if (l.startsWith("high")) return "high";
  if (l.startsWith("inconclusive") || l.startsWith("low")) return "inconclusive";
  // "Medium" from backend maps to the mid tier. Default for anything
  // else is directional (safe fallback).
  if (l.startsWith("medium") || l.startsWith("mid")) return "directional";
  return "directional";
}

function trendContext(monthlyTrend, field) {
  // Compute last-year vs prior-year delta for the KPI context line.
  // Rough and cheerful — we don't need exact YoY semantics, just
  // directional.
  if (!monthlyTrend || monthlyTrend.length < 24) return "Last 12 months";
  const recent = monthlyTrend.slice(-12).reduce((s, r) => s + (r[field] || 0), 0);
  const prior = monthlyTrend.slice(-24, -12).reduce((s, r) => s + (r[field] || 0), 0);
  if (prior === 0) return "Last 12 months";
  const pct = ((recent - prior) / prior) * 100;
  if (Math.abs(pct) < 1) return "Flat vs last year";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}% vs last year`;
}

function roasContext(roas) {
  if (roas == null) return "";
  // Context against rough benchmarks — retail ~2.5x, B2B ~3.0x
  if (roas >= 3.5) return "Above portfolio median";
  if (roas >= 2.0) return "Within typical range";
  return "Below portfolio median";
}

function todayFormatted() {
  const d = new Date();
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
  position: relative;
`;

const HeaderShell = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[8]} ${t.layout.pad.wide} ${t.space[6]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[5]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const Breadcrumb = styled.nav`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
`;

const BreadcrumbItem = styled.a`
  color: ${t.color.ink3};
  text-decoration: none;

  &:hover {
    color: ${t.color.accent};
  }
`;

const BreadcrumbSep = styled.span`
  color: ${t.color.ink4};
`;

const BreadcrumbCurrent = styled.span`
  color: ${t.color.ink};
  font-weight: ${t.weight.medium};
`;

const NameRow = styled.div`
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: ${t.space[6]};
  flex-wrap: wrap;
`;

const ChannelName = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(36px, 4.5vw, 56px);
  font-weight: ${t.weight.regular};
  line-height: 1.05;
  letter-spacing: ${t.tracking.tightest};
  color: ${t.color.ink};
  margin: 0;
`;

const MetaLine = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  margin: ${t.space[1]} 0 0 0;
`;

const PickerWrap = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[1]};
  min-width: 200px;
`;

const PickerLabel = styled.label`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;

const Picker = styled.select`
  padding: ${t.space[2]} ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  cursor: pointer;

  &:focus {
    border-color: ${t.color.accent};
    outline: none;
  }

  &:disabled {
    opacity: 0.6;
    cursor: wait;
  }
`;

const KpiRow = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: ${t.space[3]};

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
  }
`;

const Section = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide} ${t.space[10]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const SectionHead = styled.header`
  margin-bottom: ${t.space[4]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
`;

const SectionTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: ${t.space[3]};
  flex-wrap: wrap;
`;

const SectionBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[2]};
  border-radius: ${t.radius.sm};
  background: ${t.color.positiveBg};
  color: ${t.color.positive};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
`;

const SectionCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
  margin: 0;
  max-width: 680px;
`;

const CurveCard = styled.div`
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.lg};
  padding: ${t.space[6]} ${t.space[5]} ${t.space[4]};
  box-shadow: ${t.shadow.card};
`;

const ChartWrap = styled.div`
  position: relative;
  width: 100%;
`;

const ChartEmpty = styled.div`
  padding: ${t.space[16]} ${t.space[6]};
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const PastSaturationLabel = styled.span`
  position: absolute;
  top: ${t.space[5]};
  font-family: ${t.font.serif};
  font-style: italic;
  font-size: ${t.size.md};
  color: ${t.color.accent};
  opacity: 0.7;
  pointer-events: none;
`;

const Legend2 = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${t.space[5]};
  margin-top: ${t.space[3]};
  padding-top: ${t.space[3]};
  border-top: 1px solid ${t.color.borderFaint};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink2};
`;

const LegendItem = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
`;

const LegendLine = styled.span`
  width: 18px;
  height: 2px;
  background: ${({ $color }) => $color};
  border-radius: 1px;
`;

const LegendDot = styled.span`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
`;

const LegendBand = styled.span`
  width: 18px;
  height: 10px;
  border-radius: 2px;
  background: ${t.color.accent};
  opacity: 0.18;
`;

const BayesianMethodRow = styled.div`
  padding-top: ${t.space[3]};
  margin-top: ${t.space[3]};
  border-top: 1px dashed ${t.color.borderFaint};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-variant-numeric: tabular-nums;
  letter-spacing: ${t.tracking.wider};
`;

const TableCard = styled.div`
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  overflow: hidden;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const Th = styled.th`
  text-align: ${({ $align }) => $align || "left"};
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.sunken};
  border-bottom: 1px solid ${t.color.border};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const Td = styled.td`
  text-align: ${({ $align }) => $align || "left"};
  padding: ${t.space[3]} ${t.space[4]};
  border-bottom: 1px solid ${t.color.borderFaint};
  color: ${({ $muted }) => ($muted ? t.color.ink2 : t.color.ink)};

  tbody tr:last-child & {
    border-bottom: none;
  }

  strong {
    font-weight: ${t.weight.semibold};
  }
`;

const RoasCell = styled.span`
  font-weight: ${t.weight.semibold};
  color: ${({ $roas }) =>
    $roas >= 3 ? t.color.positive :
    $roas >= 2 ? t.color.ink :
    t.color.warning};
`;

const LoadingOverlay = styled.div`
  position: fixed;
  top: calc(${t.layout.headerHeight} + ${t.space[4]});
  right: ${t.space[4]};
  padding: ${t.space[2]} ${t.space[4]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  box-shadow: ${t.shadow.raised};
  z-index: ${t.z.sticky + 5};
`;

// ─── Campaigns table sub-components ───

/**
 * Sparkline — inline 12-month revenue trend for a campaign.
 * Drawn as a tiny SVG polyline. Width/height sized to fit comfortably
 * in a table cell without overwhelming the row.
 */
function Sparkline({ points }) {
  if (!points || points.length < 2) return null;
  const W = 90;
  const H = 26;
  const PAD = 2;
  const values = points.map(p => p.revenue);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const toX = (i) => PAD + (i / (points.length - 1)) * (W - PAD * 2);
  const toY = (v) => H - PAD - ((v - min) / range) * (H - PAD * 2);

  const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`).join(" ");
  const lastValue = values[values.length - 1];
  const firstValue = values[0];
  const strokeColor = lastValue >= firstValue ? t.color.positive : t.color.negative;

  return (
    <SparkWrap>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
        <path d={path} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={toX(values.length - 1)} cy={toY(lastValue)} r="2" fill={strokeColor} />
      </svg>
    </SparkWrap>
  );
}

const SparkWrap = styled.span`
  display: inline-block;
  vertical-align: middle;
`;

const CampaignSubline = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-top: 2px;
  font-weight: ${t.weight.regular};
`;

const ShareMini = styled.span`
  display: inline-flex;
  align-items: baseline;
  gap: ${t.space[1]};
  font-variant-numeric: tabular-nums;
`;

const ShareSep = styled.span`
  color: ${t.color.ink4};
`;

const TrendPill = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  white-space: nowrap;
  background: ${({ $direction }) =>
    $direction === "up" ? t.color.positiveBg :
    $direction === "down" ? t.color.negativeBg :
    t.color.sunken};
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink3};
`;

const RecChip = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  white-space: nowrap;
  ${({ $kind }) => {
    switch ($kind) {
      case "Scale":
        return `background: ${t.color.positiveBg}; color: ${t.color.positive};`;
      case "Increase share":
        return `background: ${t.color.positiveBg}; color: ${t.color.positive};`;
      case "Reduce":
      case "Rebalance down":
        return `background: ${t.color.negativeBg}; color: ${t.color.negative};`;
      case "Investigate drop":
      case "Review landing page":
        return `background: ${t.color.accentSub}; color: ${t.color.accentInk};`;
      default:
        return `background: ${t.color.sunken}; color: ${t.color.ink3};`;
    }
  }}
`;

// ─── Offline attribution banner ───

const AttributionBanner = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto ${t.space[6]} auto;
  padding: ${t.space[5]} ${t.layout.pad.wide};
  display: flex;
  gap: ${t.space[4]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const AttributionBannerIcon = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: ${({ $kind }) =>
    // Kind comes from parent via inheritance of the kind prop — but we
    // apply a default color here; the parent band overrides via styled()
    t.color.accentSub};
  color: ${t.color.accentInk};
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  flex-shrink: 0;
`;

const AttributionBannerBody = styled.div`
  flex: 1;
  min-width: 0;
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.accentSub};
  border-left: 3px solid ${t.color.accent};
  border-radius: 0 ${t.radius.md} ${t.radius.md} 0;
`;

const AttributionBannerHead = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accentInk};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const AttributionBannerCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[4]} 0;

  &:last-child {
    margin-bottom: 0;
  }
`;

const AttributionStats = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${t.space[6]};
  padding-top: ${t.space[3]};
  border-top: 1px solid ${t.color.borderFaint};
`;

const AttributionStat = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const AttributionStatValue = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.lg};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  font-variant-numeric: tabular-nums;
`;

const AttributionStatLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  font-weight: ${t.weight.semibold};
`;

function formatReach(n) {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return Math.round(n).toLocaleString();
}
"""
build_dashboard.py
--------------------
Reads the curated SQL extracts + the advanced-analytics engagement scores
and renders dashboards/executive_summary.html — a self-contained,
dependency-free HTML executive dashboard (the same story the Tableau
"Executive Summary" dashboard and Power BI report page tell, built here as
a static, shareable artifact from the real generated data).

No templating engine — a single f-string template with an embedded JSON
data blob and hand-written vanilla-JS/SVG chart renderers, so the output
file has zero external dependencies and opens directly in a browser.
"""
from __future__ import annotations

import json
import os

import pandas as pd

BASE = os.path.dirname(__file__)
PROCESSED = os.path.join(BASE, "..", "data", "processed")
OUT_PATH = os.path.join(BASE, "..", "dashboards", "executive_summary.html")

exec_summary = pd.read_csv(os.path.join(PROCESSED, "08_executive_summary_view.csv"))
participation = pd.read_csv(os.path.join(PROCESSED, "02_patient_participation_rate.csv"))
dept = pd.read_csv(os.path.join(PROCESSED, "03_engagement_by_department.csv"))
cohort = pd.read_csv(os.path.join(PROCESSED, "04_cohort_retention.csv"))
campaigns = pd.read_csv(os.path.join(PROCESSED, "06_campaign_effectiveness.csv"))
nps_csat = pd.read_csv(os.path.join(PROCESSED, "07_nps_csat_trends.csv"))
scores = pd.read_csv(os.path.join(PROCESSED, "patient_engagement_scores.csv"))

latest = exec_summary.iloc[-1]
prior = exec_summary.iloc[-2]
latest_part = participation.iloc[-1]
prior_part = participation.iloc[-2]


def pct_delta(cur, prev):
    if prev in (0, None) or pd.isna(prev):
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


tiles = [
    {
        "label": "Monthly active users",
        "value": int(latest["active_users"]),
        "value_fmt": f"{int(latest['active_users']):,}",
        "delta_pct": pct_delta(latest["active_users"], prior["active_users"]),
        "sparkline": exec_summary["active_users"].tail(12).round(0).tolist(),
        "good_direction": "up",
    },
    {
        "label": "Patient participation rate",
        "value": float(latest_part["participation_rate_pct"]),
        "value_fmt": f"{latest_part['participation_rate_pct']:.1f}%",
        "delta_pct": pct_delta(latest_part["participation_rate_pct"], prior_part["participation_rate_pct"]),
        "sparkline": participation["participation_rate_pct"].tail(12).round(1).tolist(),
        "good_direction": "up",
    },
    {
        "label": "Net Promoter Score",
        "value": float(latest["nps_score"]),
        "value_fmt": f"{latest['nps_score']:.0f}",
        "delta_pct": pct_delta(latest["nps_score"], prior["nps_score"]),
        "sparkline": exec_summary["nps_score"].tail(12).round(1).tolist(),
        "good_direction": "up",
    },
    {
        "label": "Telehealth adoption",
        "value": float(latest["telehealth_adoption_pct"]),
        "value_fmt": f"{latest['telehealth_adoption_pct']:.1f}%",
        "delta_pct": pct_delta(latest["telehealth_adoption_pct"], prior["telehealth_adoption_pct"]),
        "sparkline": exec_summary["telehealth_adoption_pct"].tail(12).round(1).tolist(),
        "good_direction": "up",
    },
    {
        "label": "Average CSAT (of 5)",
        "value": float(latest["avg_csat"]),
        "value_fmt": f"{latest['avg_csat']:.2f}",
        "delta_pct": pct_delta(latest["avg_csat"], prior["avg_csat"]),
        "sparkline": exec_summary["avg_csat"].tail(12).round(2).tolist(),
        "good_direction": "up",
    },
    {
        "label": "Appointment no-show rate",
        "value": float(latest["no_show_rate_pct"]),
        "value_fmt": f"{latest['no_show_rate_pct']:.1f}%",
        "delta_pct": pct_delta(latest["no_show_rate_pct"], prior["no_show_rate_pct"]),
        "sparkline": exec_summary["no_show_rate_pct"].tail(12).round(1).tolist(),
        "good_direction": "down",
    },
]

mau_series = {
    "labels": exec_summary["year_month"].tolist(),
    "values": exec_summary["active_users"].tolist(),
}

nps_series = {
    "labels": nps_csat["year_month"].tolist(),
    "values": nps_csat["nps_score"].round(1).tolist(),
}
csat_series = {
    "labels": nps_csat["year_month"].tolist(),
    "values": nps_csat["avg_csat"].round(2).tolist(),
}

latest_month = dept["year_month"].max()
dept_latest = (
    dept[dept["year_month"] == latest_month]
    .sort_values("total_events", ascending=False)
)
dept_chart = {
    "labels": dept_latest["department_name"].tolist(),
    "values": dept_latest["total_events"].tolist(),
    "month": latest_month,
}

# Cohort heatmap: most recent 10 cohorts with enough history, months 0-9
cohort_pivot = cohort.pivot(index="cohort_month", columns="months_since_signup", values="retention_pct")
cohort_pivot = cohort_pivot.sort_index().tail(10)
month_cols = [c for c in range(0, 10) if c in cohort_pivot.columns]
cohort_chart = {
    "cohorts": cohort_pivot.index.tolist(),
    "months": month_cols,
    "matrix": [[
        None if pd.isna(cohort_pivot.loc[c, m]) else round(float(cohort_pivot.loc[c, m]), 1)
        for m in month_cols
    ] for c in cohort_pivot.index],
}

campaigns_sorted = campaigns.sort_values("avg_engagement_lift", ascending=False)
campaign_chart = {
    "labels": campaigns_sorted["campaign_id"].tolist(),
    "names": campaigns_sorted["campaign_name"].tolist(),
    "values": campaigns_sorted["avg_engagement_lift"].round(2).tolist(),
    "engagement_rate": campaigns_sorted["campaign_engagement_rate_pct"].round(1).tolist(),
}

tier_order = ["Inactive", "Low", "Medium", "High"]
tier_counts = scores["engagement_tier"].value_counts().reindex(tier_order).fillna(0).astype(int)
tier_chart = {
    "labels": tier_order,
    "values": tier_counts.tolist(),
    "total": int(tier_counts.sum()),
}

data_blob = {
    "generated_note": "Synthetic data, Jan 2024–Aug 2026 · python/generate_data.py (seed=42)",
    "tiles": tiles,
    "mau_series": mau_series,
    "nps_series": nps_series,
    "csat_series": csat_series,
    "dept_chart": dept_chart,
    "cohort_chart": cohort_chart,
    "campaign_chart": campaign_chart,
    "tier_chart": tier_chart,
}

DATA_JSON = json.dumps(data_blob)

# ---------------------------------------------------------------------
# HTML / CSS / JS template
# ---------------------------------------------------------------------
HTML = r"""<title>Health Record Portal — Executive Summary</title>
<style>
  :root, .viz-root {
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page:           #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --grid:           #e1e0d9;
    --axis:           #c3c2b7;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6;   /* blue */
    --series-1-wash:  rgba(42,120,214,0.10);
    --series-2:       #eb6834;   /* orange */
    --series-3:       #1baf7a;   /* aqua */
    --series-4:       #eda100;   /* yellow */
    --good:           #006300;
    --bad:            #d03b3b;
    --seq-100: #cde2fb; --seq-200: #9ec5f4; --seq-300: #6da7ec;
    --seq-400: #3987e5; --seq-500: #256abf; --seq-600: #184f95; --seq-700: #0d366b;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --surface-1:      #1a1a19;
      --page:           #0d0d0d;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --grid:           #2c2c2a;
      --axis:           #383835;
      --border:         rgba(255,255,255,0.10);
      --series-1:       #3987e5;
      --series-1-wash:  rgba(57,135,229,0.14);
      --series-2:       #d95926;
      --series-3:       #199e70;
      --series-4:       #c98500;
      --good:           #0ca30c;
      --bad:            #e66767;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page:           #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --grid:           #2c2c2a;
    --axis:           #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --series-1-wash:  rgba(57,135,229,0.14);
    --series-2:       #d95926;
    --series-3:       #199e70;
    --series-4:       #c98500;
    --good:           #0ca30c;
    --bad:            #e66767;
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 64px; }

  header.top { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }
  header.top h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
  header.top p.sub { margin: 0; color: var(--text-secondary); font-size: 13.5px; }
  header.top .meta { text-align: right; color: var(--text-muted); font-size: 12px; max-width: 320px; }

  .card {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 18px 14px;
  }
  .section-title { font-size: 14px; font-weight: 700; margin: 0 0 2px; }
  .section-sub { font-size: 12px; color: var(--text-muted); margin: 0 0 14px; }

  .tiles { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px; }
  @media (max-width: 980px) { .tiles { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 620px) { .tiles { grid-template-columns: repeat(2, 1fr); } }
  .tile { padding: 14px 14px 10px; display: flex; flex-direction: column; gap: 6px; }
  .tile .label { font-size: 11.5px; color: var(--text-secondary); font-weight: 600; letter-spacing: 0.01em; }
  .tile .value { font-size: 25px; font-weight: 700; line-height: 1.1; font-variant-numeric: proportional-nums; }
  .tile .delta { font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 4px; }
  .tile .delta.up { color: var(--good); }
  .tile .delta.down { color: var(--bad); }
  .tile .delta.flat { color: var(--text-muted); }
  .tile svg.spark { width: 100%; height: 26px; display: block; margin-top: 2px; }

  .row { display: grid; gap: 16px; margin-bottom: 16px; }
  .row.cols-2 { grid-template-columns: 2fr 1fr; }
  .row.cols-2b { grid-template-columns: 1fr 1fr; }
  .row.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
  @media (max-width: 900px) { .row.cols-2, .row.cols-2b, .row.cols-3 { grid-template-columns: 1fr; } }

  svg text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  .axis-label { fill: var(--text-muted); font-size: 10.5px; }
  .grid-line { stroke: var(--grid); stroke-width: 1; }
  .baseline { stroke: var(--axis); stroke-width: 1; }

  .tooltip {
    position: absolute;
    pointer-events: none;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    opacity: 0;
    transition: opacity 80ms ease;
    z-index: 5;
    white-space: nowrap;
  }
  .tooltip .tt-title { color: var(--text-muted); font-size: 11px; margin-bottom: 3px; }
  .tooltip .tt-row { display: flex; align-items: center; gap: 6px; }
  .tooltip .tt-key { width: 10px; height: 2px; background: var(--series-1); border-radius: 1px; display: inline-block; }
  .tooltip .tt-val { font-weight: 700; }

  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font-size: 11.5px; color: var(--text-secondary); }
  .legend .item { display: flex; align-items: center; gap: 6px; }
  .legend .swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

  footer.note { margin-top: 28px; color: var(--text-muted); font-size: 11.5px; text-align: center; }
  footer.note a { color: inherit; }

  .chart-shell { position: relative; }
  .bar-label { font-size: 11px; fill: var(--text-secondary); }
  .bar-value { font-size: 11px; fill: var(--text-primary); font-weight: 600; }
  rect.mark, path.mark { cursor: pointer; }
  rect.mark:hover, path.mark:hover { filter: brightness(1.06); }
</style>

<div class="wrap">
  <header class="top">
    <div>
      <h1>Health Record Portal — Executive Summary</h1>
      <p class="sub">Active user engagement &amp; patient participation · Jan 2024 – Aug 2026</p>
    </div>
    <div class="meta" id="meta-note"></div>
  </header>

  <div class="tiles" id="tiles"></div>

  <div class="row cols-2">
    <div class="card">
      <div class="section-title">Monthly active portal users</div>
      <div class="section-sub">Distinct patients with at least one portal event in the month</div>
      <div class="chart-shell"><svg id="chart-mau" viewBox="0 0 640 260" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
    <div class="card">
      <div class="section-title">Engagement tiers</div>
      <div class="section-sub">Composite engagement score, enrolled patients</div>
      <div class="chart-shell"><svg id="chart-tiers" viewBox="0 0 340 260" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
  </div>

  <div class="row cols-2b">
    <div class="card">
      <div class="section-title">Net Promoter Score trend</div>
      <div class="section-sub">Promoters minus detractors, monthly</div>
      <div class="chart-shell"><svg id="chart-nps" viewBox="0 0 560 200" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
    <div class="card">
      <div class="section-title">Average CSAT trend</div>
      <div class="section-sub">Post-interaction satisfaction, 1–5 scale</div>
      <div class="chart-shell"><svg id="chart-csat" viewBox="0 0 560 200" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
  </div>

  <div class="row cols-2b">
    <div class="card">
      <div class="section-title">Department engagement</div>
      <div class="section-sub" id="dept-sub"></div>
      <div class="chart-shell"><svg id="chart-dept" viewBox="0 0 640 260" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
    <div class="card">
      <div class="section-title">Outreach campaign lift</div>
      <div class="section-sub">Avg. portal events/patient, 30d after response vs. before</div>
      <div class="chart-shell"><svg id="chart-campaign" viewBox="0 0 640 260" preserveAspectRatio="xMidYMid meet"></svg></div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-1)"></span>Positive lift</span>
        <span class="item"><span class="swatch" style="background:var(--bad)"></span>No lift / negative</span>
      </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <div class="section-title">Portal retention by signup cohort</div>
    <div class="section-sub">% of each monthly signup cohort still active, by months since signup</div>
    <div class="chart-shell"><svg id="chart-cohort" viewBox="0 0 760 300" preserveAspectRatio="xMidYMid meet"></svg></div>
  </div>

  <footer class="note">
    Built from a synthetic, seeded dataset (2,418 portal-enrolled patients across 5,000 patients, 139K engagement events) —
    see <code>python/generate_data.py</code>, <code>sql/queries/</code>, and <code>python/advanced_analytics.py</code> for the full pipeline.
  </footer>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA_JSON__;
const svgNS = "http://www.w3.org/2000/svg";
function el(tag, attrs) {
  const n = document.createElementNS(svgNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  return n;
}
function fmtMonth(ym) {
  const [y, m] = ym.split("-");
  const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return names[parseInt(m,10)-1] + " '" + y.slice(2);
}
const tooltip = document.getElementById("tooltip");
function showTooltip(x, y, html) {
  tooltip.innerHTML = html;
  tooltip.style.left = (x + 14) + "px";
  tooltip.style.top = (y + 10) + "px";
  tooltip.style.opacity = 1;
}
function hideTooltip() { tooltip.style.opacity = 0; }

// ---------------------------------------------------------------- tiles
function renderTiles() {
  const root = document.getElementById("tiles");
  DATA.tiles.forEach(t => {
    const card = document.createElement("div");
    card.className = "card tile";
    const dir = t.delta_pct == null ? "flat" : (t.delta_pct === 0 ? "flat" : (
      (t.good_direction === "up") === (t.delta_pct > 0) ? "up" : "down"
    ));
    const arrow = t.delta_pct == null ? "" : (t.delta_pct > 0 ? "↑" : (t.delta_pct < 0 ? "↓" : "→"));
    const deltaTxt = t.delta_pct == null ? "n/a vs. prior month" : (Math.abs(t.delta_pct).toFixed(1) + "% vs. prior month");
    card.innerHTML =
      '<div class="label"></div>' +
      '<div class="value"></div>' +
      '<div class="delta ' + dir + '"><span></span></div>' +
      '<svg class="spark" viewBox="0 0 120 26" preserveAspectRatio="none"></svg>';
    card.querySelector(".label").textContent = t.label;
    card.querySelector(".value").textContent = t.value_fmt;
    card.querySelector(".delta span").textContent = arrow + " " + deltaTxt;
    root.appendChild(card);

    const spark = card.querySelector("svg.spark");
    const vals = t.sparkline;
    if (vals && vals.length > 1) {
      const min = Math.min(...vals), max = Math.max(...vals);
      const span = (max - min) || 1;
      const stepX = 120 / (vals.length - 1);
      const pts = vals.map((v, i) => [i * stepX, 24 - ((v - min) / span) * 20 - 2]);
      const d = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      spark.appendChild(el("path", { d, fill: "none", stroke: "var(--series-1)", "stroke-width": 1.6, "stroke-linecap": "round", "stroke-linejoin": "round" }));
      const last = pts[pts.length - 1];
      spark.appendChild(el("circle", { cx: last[0], cy: last[1], r: 2.2, fill: "var(--series-1)" }));
    }
  });
  document.getElementById("meta-note").textContent = DATA.generated_note;
}

// ---------------------------------------------------------------- line chart w/ crosshair
function renderLineChart(svgId, labels, values, opts) {
  opts = opts || {};
  const svg = document.getElementById(svgId);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const padL = 44, padR = 14, padT = 14, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const min = Math.min(...values), max = Math.max(...values);
  const lo = min - (max - min) * 0.12 - (max === min ? 1 : 0);
  const hi = max + (max - min) * 0.12 + (max === min ? 1 : 0);
  const x = i => padL + (i / (values.length - 1)) * plotW;
  const y = v => padT + plotH - ((v - lo) / (hi - lo)) * plotH;

  // gridlines (4 horizontal)
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const gy = padT + (plotH / ticks) * i;
    svg.appendChild(el("line", { x1: padL, x2: W - padR, y1: gy, y2: gy, class: "grid-line" }));
    const val = hi - ((hi - lo) / ticks) * i;
    const label = el("text", { x: padL - 8, y: gy + 3, class: "axis-label", "text-anchor": "end" });
    label.textContent = opts.valueFmt ? opts.valueFmt(val) : Math.round(val).toLocaleString();
    svg.appendChild(label);
  }
  svg.appendChild(el("line", { x1: padL, x2: W - padR, y1: padT + plotH, y2: padT + plotH, class: "baseline" }));

  // x labels (sparse: first, evenly spaced, last — never two ticks closer
  // than half a step, so the final label never collides with its neighbor)
  const xLabelEvery = Math.ceil(labels.length / 7);
  const lastIdxLbl = labels.length - 1;
  labels.forEach((lab, i) => {
    const isRegularTick = i % xLabelEvery === 0;
    const tooCloseToLast = i !== lastIdxLbl && (lastIdxLbl - i) < xLabelEvery / 2;
    if ((!isRegularTick && i !== lastIdxLbl) || tooCloseToLast) return;
    // Anchor the rightmost label to its own right edge (not centered) so it
    // never overflows the SVG's clipped viewBox on the right.
    const anchor = i === lastIdxLbl ? "end" : "middle";
    const t = el("text", { x: x(i), y: H - 6, class: "axis-label", "text-anchor": anchor });
    t.textContent = fmtMonth(lab);
    svg.appendChild(t);
  });

  // area wash
  const areaD = "M" + x(0) + "," + (padT + plotH) + " " +
    values.map((v, i) => "L" + x(i) + "," + y(v)).join(" ") +
    " L" + x(values.length - 1) + "," + (padT + plotH) + " Z";
  svg.appendChild(el("path", { d: areaD, fill: "var(--series-1-wash)", stroke: "none" }));

  // line
  const lineD = values.map((v, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(v)).join(" ");
  svg.appendChild(el("path", { d: lineD, fill: "none", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", class: "mark" }));

  // end marker + label
  const lastIdx = values.length - 1;
  svg.appendChild(el("circle", { cx: x(lastIdx), cy: y(values[lastIdx]), r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", "stroke-width": 2 }));

  // crosshair hit layer
  const hit = el("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" });
  const crosshair = el("line", { x1: 0, x2: 0, y1: padT, y2: padT + plotH, class: "grid-line", style: "display:none" });
  svg.appendChild(crosshair);
  const dot = el("circle", { r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", "stroke-width": 2, style: "display:none" });
  svg.appendChild(dot);
  svg.appendChild(hit);

  function onMove(evt) {
    const rect = svg.getBoundingClientRect();
    const scaleX = W / rect.width;
    const px = (evt.clientX - rect.left) * scaleX;
    let idx = Math.round(((px - padL) / plotW) * (values.length - 1));
    idx = Math.max(0, Math.min(values.length - 1, idx));
    crosshair.setAttribute("x1", x(idx)); crosshair.setAttribute("x2", x(idx));
    crosshair.style.display = "block";
    dot.setAttribute("cx", x(idx)); dot.setAttribute("cy", y(values[idx]));
    dot.style.display = "block";
    const val = opts.valueFmt ? opts.valueFmt(values[idx]) : values[idx].toLocaleString();
    showTooltip(evt.clientX, evt.clientY, '<div class="tt-title">' + fmtMonth(labels[idx]) + '</div>' +
      '<div class="tt-row"><span class="tt-key"></span><span class="tt-val">' + val + '</span></div>');
  }
  hit.addEventListener("pointermove", onMove);
  hit.addEventListener("pointerleave", () => { crosshair.style.display = "none"; dot.style.display = "none"; hideTooltip(); });
}

// ---------------------------------------------------------------- horizontal bar chart
function renderBarChart(svgId, labels, values, opts) {
  opts = opts || {};
  const svg = document.getElementById(svgId);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const padL = opts.padL || 150, padR = 50, padT = 10, padB = 10;
  const plotW = W - padL - padR;
  const n = labels.length;
  const bandH = (H - padT - padB) / n;
  const barH = Math.min(22, bandH * 0.6);
  const max = Math.max(...values, 0.0001);

  labels.forEach((lab, i) => {
    const cy = padT + bandH * i + bandH / 2;
    const w = (values[i] / max) * plotW;
    const barColor = opts.color || "var(--series-1)";
    const bar = el("rect", {
      x: padL, y: cy - barH / 2, width: Math.max(w, 1), height: barH,
      rx: 4, fill: values[i] < 0 ? "var(--bad)" : barColor, class: "mark"
    });
    svg.appendChild(bar);
    const lblText = el("text", { x: padL - 8, y: cy + 4, class: "bar-label", "text-anchor": "end" });
    lblText.textContent = lab;
    svg.appendChild(lblText);
    const valText = el("text", { x: padL + w + 6, y: cy + 4, class: "bar-value" });
    valText.textContent = opts.valueFmt ? opts.valueFmt(values[i]) : values[i];
    svg.appendChild(valText);

    bar.addEventListener("pointermove", (evt) => {
      const titleTxt = (opts.tooltipLabels && opts.tooltipLabels[i]) || lab;
      const titleEl = document.createElement("div");
      titleEl.className = "tt-title";
      titleEl.textContent = titleTxt;
      const valTxt = opts.valueFmt ? opts.valueFmt(values[i]) : values[i];
      showTooltip(evt.clientX, evt.clientY, titleEl.outerHTML +
        '<div class="tt-row"><span class="tt-key"></span><span class="tt-val">' + valTxt + '</span></div>');
    });
    bar.addEventListener("pointerleave", hideTooltip);
  });
}

// ---------------------------------------------------------------- diverging bar chart (zero baseline)
function renderDivergingBarChart(svgId, labels, values, opts) {
  opts = opts || {};
  const svg = document.getElementById(svgId);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const padL = opts.padL || 60, padR = 90, padT = 10, padB = 10;
  const plotW = W - padL - padR;
  const n = labels.length;
  const bandH = (H - padT - padB) / n;
  const barH = Math.min(20, bandH * 0.6);
  const maxAbs = Math.max(...values.map(v => Math.abs(v)), 0.0001);
  // Symmetric zero baseline centered in the plot so both signs have room.
  const zx = padL + plotW / 2;
  const scale = (plotW / 2) / maxAbs;

  svg.appendChild(el("line", { x1: zx, x2: zx, y1: padT, y2: H - padB, class: "grid-line" }));

  labels.forEach((lab, i) => {
    const cy = padT + bandH * i + bandH / 2;
    const v = values[i];
    const w = Math.abs(v) * scale;
    const positive = v >= 0;
    const barX = positive ? zx : zx - w;
    const color = positive ? "var(--series-1)" : "var(--bad)";
    const bar = el("rect", {
      x: barX, y: cy - barH / 2, width: Math.max(w, 1.5), height: barH,
      rx: 3, fill: color, class: "mark"
    });
    svg.appendChild(bar);
    const lblText = el("text", { x: padL - 8, y: cy + 4, class: "bar-label", "text-anchor": "end" });
    lblText.textContent = lab;
    svg.appendChild(lblText);
    const valX = positive ? zx + w + 6 : zx - w - 6;
    const valText = el("text", { x: valX, y: cy + 4, class: "bar-value", "text-anchor": positive ? "start" : "end" });
    valText.textContent = opts.valueFmt ? opts.valueFmt(v) : v;
    svg.appendChild(valText);

    bar.addEventListener("pointermove", (evt) => {
      const titleTxt = (opts.tooltipLabels && opts.tooltipLabels[i]) || lab;
      const titleEl = document.createElement("div");
      titleEl.className = "tt-title";
      titleEl.textContent = titleTxt;
      showTooltip(evt.clientX, evt.clientY, titleEl.outerHTML +
        '<div class="tt-row"><span class="tt-key" style="background:' + color + '"></span><span class="tt-val">' +
        (opts.valueFmt ? opts.valueFmt(v) : v) + '</span></div>');
    });
    bar.addEventListener("pointerleave", hideTooltip);
  });
}

// ---------------------------------------------------------------- donut (engagement tiers)
function renderDonut(svgId, labels, values) {
  const svg = document.getElementById(svgId);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const cx = 90, cy = H / 2, r = 70, thickness = 26;
  const colors = ["var(--text-muted)", "var(--series-4)", "var(--series-3)", "var(--series-1)"];
  const total = values.reduce((a, b) => a + b, 0);
  let angle = -Math.PI / 2;

  labels.forEach((lab, i) => {
    const frac = values[i] / total;
    const a0 = angle, a1 = angle + frac * Math.PI * 2;
    angle = a1;
    const large = (a1 - a0) > Math.PI ? 1 : 0;
    const x0 = cx + Math.cos(a0) * r, y0 = cy + Math.sin(a0) * r;
    const x1 = cx + Math.cos(a1) * r, y1 = cy + Math.sin(a1) * r;
    const xi0 = cx + Math.cos(a0) * (r - thickness), yi0 = cy + Math.sin(a0) * (r - thickness);
    const xi1 = cx + Math.cos(a1) * (r - thickness), yi1 = cy + Math.sin(a1) * (r - thickness);
    const d = [
      "M", x0, y0, "A", r, r, 0, large, 1, x1, y1,
      "L", xi1, yi1, "A", r - thickness, r - thickness, 0, large, 0, xi0, yi0, "Z"
    ].join(" ");
    const path = el("path", { d, fill: colors[i % colors.length], stroke: "var(--surface-1)", "stroke-width": 2, class: "mark" });
    svg.appendChild(path);
    path.addEventListener("pointermove", (evt) => {
      const pct = (frac * 100).toFixed(1);
      showTooltip(evt.clientX, evt.clientY, '<div class="tt-title">' + lab + '</div>' +
        '<div class="tt-row"><span class="tt-key" style="background:' + colors[i % colors.length] + '"></span>' +
        '<span class="tt-val">' + values[i].toLocaleString() + ' (' + pct + '%)</span></div>');
    });
    path.addEventListener("pointerleave", hideTooltip);
  });

  const centerVal = el("text", { x: cx, y: cy - 2, "text-anchor": "middle", class: "bar-value", style: "font-size:20px" });
  centerVal.textContent = total.toLocaleString();
  svg.appendChild(centerVal);
  const centerLbl = el("text", { x: cx, y: cy + 16, "text-anchor": "middle", class: "axis-label" });
  centerLbl.textContent = "enrolled";
  svg.appendChild(centerLbl);

  // legend
  const legendX = 190, legendY0 = H / 2 - labels.length * 11;
  labels.forEach((lab, i) => {
    const gy = legendY0 + i * 22;
    svg.appendChild(el("rect", { x: legendX, y: gy, width: 10, height: 10, rx: 2, fill: colors[i % colors.length] }));
    const t = el("text", { x: legendX + 16, y: gy + 9, class: "bar-label" });
    t.textContent = lab + " (" + values[i].toLocaleString() + ")";
    svg.appendChild(t);
  });
}

// ---------------------------------------------------------------- heatmap (cohort retention)
function renderHeatmap(svgId, cohorts, months, matrix) {
  const svg = document.getElementById(svgId);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const padL = 90, padT = 20, padR = 20, padB = 10;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const cellW = plotW / months.length, cellH = plotH / cohorts.length;
  const seqSteps = ["var(--seq-100)", "var(--seq-200)", "var(--seq-300)", "var(--seq-400)", "var(--seq-500)", "var(--seq-600)", "var(--seq-700)"];

  months.forEach((m, i) => {
    const t = el("text", { x: padL + cellW * i + cellW / 2, y: padT - 6, class: "axis-label", "text-anchor": "middle" });
    t.textContent = "M" + m;
    svg.appendChild(t);
  });
  cohorts.forEach((c, j) => {
    const t = el("text", { x: padL - 8, y: padT + cellH * j + cellH / 2 + 3, class: "axis-label", "text-anchor": "end" });
    t.textContent = fmtMonth(c);
    svg.appendChild(t);
  });

  cohorts.forEach((c, j) => {
    months.forEach((m, i) => {
      const v = matrix[j][i];
      if (v === null || v === undefined) return;
      const step = Math.min(6, Math.max(0, Math.round((v / 100) * 6)));
      const rect = el("rect", {
        x: padL + cellW * i + 1, y: padT + cellH * j + 1,
        width: cellW - 2, height: cellH - 2, rx: 3,
        fill: seqSteps[step], class: "mark"
      });
      svg.appendChild(rect);
      rect.addEventListener("pointermove", (evt) => {
        showTooltip(evt.clientX, evt.clientY,
          '<div class="tt-title">' + fmtMonth(c) + ' cohort · month ' + m + '</div>' +
          '<div class="tt-row"><span class="tt-key" style="background:' + seqSteps[step] + '"></span><span class="tt-val">' + v + '% active</span></div>');
      });
      rect.addEventListener("pointerleave", hideTooltip);
    });
  });
}

renderTiles();
renderLineChart("chart-mau", DATA.mau_series.labels, DATA.mau_series.values, { valueFmt: v => Math.round(v).toLocaleString() });
renderLineChart("chart-nps", DATA.nps_series.labels, DATA.nps_series.values, { valueFmt: v => v.toFixed(0) });
renderLineChart("chart-csat", DATA.csat_series.labels, DATA.csat_series.values, { valueFmt: v => v.toFixed(2) });
renderBarChart("chart-dept", DATA.dept_chart.labels, DATA.dept_chart.values, { valueFmt: v => v.toLocaleString() });
document.getElementById("dept-sub").textContent = "Portal events by patient's primary department — " + fmtMonth(DATA.dept_chart.month);
renderDivergingBarChart("chart-campaign", DATA.campaign_chart.labels, DATA.campaign_chart.values, { padL: 60, tooltipLabels: DATA.campaign_chart.names, valueFmt: v => (v > 0 ? "+" : "") + v.toFixed(2) + " events" });
renderDonut("chart-tiers", DATA.tier_chart.labels, DATA.tier_chart.values);
renderHeatmap("chart-cohort", DATA.cohort_chart.cohorts, DATA.cohort_chart.months, DATA.cohort_chart.matrix);
</script>
"""

HTML = HTML.replace("__DATA_JSON__", DATA_JSON)

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Dashboard written to: {os.path.abspath(OUT_PATH)}")

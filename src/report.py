"""
HTML report rendering (D2). Produces one self-contained HTML file: inline
CSS (from templates/report.html.j2), plotly via include_plotlyjs='cdn'.
"""
import os
import subprocess

import jinja2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import config

TEMPLATE_DIR = os.path.join(config.ROOT_DIR, "templates")
ACCENT = "#185FA5"


def _git_commit_hash():
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT_DIR,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def heatmap_html(grid, max_show=5, div_id=None):
    """Score-grid heatmap: home goals on y, away goals on x, 0..max_show."""
    sub = grid[: max_show + 1, : max_show + 1]
    fig = go.Figure(data=go.Heatmap(
        z=sub, x=list(range(max_show + 1)), y=list(range(max_show + 1)),
        colorscale=[[0, "#ffffff"], [1, ACCENT]],
        text=[["{0:.1%}".format(v) for v in row] for row in sub],
        texttemplate="%{text}", showscale=False,
        hovertemplate="Home %{y} - Away %{x}: %{z:.1%}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Away goals", yaxis_title="Home goals",
        margin=dict(l=40, r=10, t=10, b=40), height=320,
        yaxis=dict(autorange="reversed", dtick=1), xaxis=dict(dtick=1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False, div_id=div_id)


BUNDESLIGA_MATCHES_PER_MATCHDAY = 9

_TRACKER_COLS = [
    ("model_points", "Model", ACCENT),
    ("always21_points", "Always 2-1", "#9aa5b1"),
    ("market_ev_points", "Market EV", "#e07b39"),
]


def matchday_points(season_points_df):
    """
    Collapse the per-MATCH season_points rows into per-MATCHDAY point
    totals. season_points.csv holds one row per scored match; a Bundesliga
    matchday is 9 of them. Rows are ordered by kickoff (falling back to
    file order) and grouped 9-at-a-time, so an in-progress final matchday
    just yields a smaller last group.

    Returns a DataFrame indexed 1..N (matchday number) with one summed
    column per metric present in the input, plus 'exact_hit' / 'gd_hit'
    counts when available. Empty in -> empty out.
    """
    if season_points_df is None or len(season_points_df) == 0:
        return pd.DataFrame()

    df = season_points_df.copy()
    if "datetime" in df.columns:
        df = df.sort_values("datetime", kind="stable")
    df = df.reset_index(drop=True)
    df["_matchday"] = df.index // BUNDESLIGA_MATCHES_PER_MATCHDAY + 1

    sum_cols = [c for c, _, _ in _TRACKER_COLS if c in df.columns]
    for c in ("exact_hit", "gd_hit"):
        if c in df.columns:
            sum_cols.append(c)

    grouped = df.groupby("_matchday")[sum_cols].apply(
        lambda g: g.fillna(0).sum()
    )
    grouped.index.name = "matchday"
    return grouped


def season_summary_stats(season_points_df):
    """Headline numbers for the report's Season tracker table, computed
    on a per-MATCHDAY basis (not per match)."""
    md = matchday_points(season_points_df)
    n_md = len(md)
    total_model = float(md["model_points"].sum()) if "model_points" in md.columns else 0.0
    return {
        "matchdays": n_md,
        "points_per_matchday": (total_model / n_md) if n_md else 0.0,
        "exact_hits": int(md["exact_hit"].sum()) if "exact_hit" in md.columns else 0,
        "gd_hits": int(md["gd_hit"].sum()) if "gd_hit" in md.columns else 0,
    }


def season_tracker_html(season_points_df, div_id=None):
    """Cumulative points line chart, model vs baselines -- one point per
    matchday (x-axis), not per match."""
    md = matchday_points(season_points_df)
    fig = go.Figure()
    for col, label, color in _TRACKER_COLS:
        if col in md.columns:
            cum = md[col].cumsum()
            fig.add_trace(go.Scatter(
                x=list(md.index), y=cum, mode="lines+markers",
                name=label, line=dict(color=color, width=2),
            ))
    fig.update_layout(
        xaxis_title="Matchday", yaxis_title="Cumulative points",
        margin=dict(l=40, r=10, t=10, b=40), height=320,
        legend=dict(orientation="h", y=-0.2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    if len(md):
        fig.update_xaxes(dtick=1)
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False, div_id=div_id)


def render_report(context, out_path):
    """
    context: dict matching the template's expected variables:
        matchday_number, generated_at, latest_understat_date,
        odds_file_date, warnings (list[str]), matches (list[dict]),
        season_tracker_div (html str), season_stats (dict),
        tuned_params (dict), git_commit_hash (auto-filled if absent).
    """
    context = dict(context)
    context.setdefault("git_commit_hash", _git_commit_hash())

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")
    html = template.render(**context)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html)
    return html


def build_match_context(fixture_row, model_rec, lam_market, lam_xg, lam_dc,
                         mkt_probs=None):
    """
    Assemble one match's template context dict from prediction outputs.
    model_rec: output of optimizer.recommend_tip.
    """
    top5 = model_rec["top5"]
    max_ev = max(ev for _, ev in top5) if top5 else 1.0
    top5_ctx = [
        {"h": t[0][0], "a": t[0][1], "ev": t[1],
         "bar_pct": (t[1] / max_ev * 100) if max_ev > 0 else 0}
        for t in top5
    ]

    runner_up = model_rec.get("runner_up")

    ctx = {
        "home_team": fixture_row["home_team"], "away_team": fixture_row["away_team"],
        "kickoff_cet": fixture_row["kickoff_cet"],
        "tip_h": model_rec["tip"][0], "tip_a": model_rec["tip"][1],
        "ev": model_rec["ev"], "close_call": model_rec["close_call"],
        "runner_up_h": runner_up[0][0] if runner_up else None,
        "runner_up_a": runner_up[0][1] if runner_up else None,
        "runner_up_ev": runner_up[1] if runner_up else None,
        "p_home": model_rec["p_home"], "p_draw": model_rec["p_draw"], "p_away": model_rec["p_away"],
        "lam_market_h": lam_market[0] if not np.isnan(lam_market[0]) else 0.0,
        "lam_market_a": lam_market[1] if not np.isnan(lam_market[1]) else 0.0,
        "lam_xg_h": lam_xg[0], "lam_xg_a": lam_xg[1],
        "lam_dc_h": lam_dc[0], "lam_dc_a": lam_dc[1],
        "mkt_p_home": mkt_probs[0] if mkt_probs else None,
        "mkt_p_draw": mkt_probs[1] if mkt_probs else None,
        "mkt_p_away": mkt_probs[2] if mkt_probs else None,
        "top5": top5_ctx,
    }
    return ctx

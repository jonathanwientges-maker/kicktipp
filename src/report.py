"""
HTML report rendering (D2). Produces one self-contained HTML file: inline
CSS (from templates/report.html.j2), plotly via include_plotlyjs='cdn'.
"""
import os
import subprocess

import jinja2
import numpy as np
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


def season_tracker_html(season_points_df, div_id=None):
    """Cumulative points line chart, model vs baselines."""
    fig = go.Figure()
    cols = [
        ("model_points", "Model", ACCENT),
        ("always21_points", "Always 2-1", "#9aa5b1"),
        ("market_ev_points", "Market EV", "#e07b39"),
    ]
    for col, label, color in cols:
        if col in season_points_df.columns:
            cum = season_points_df[col].fillna(0).cumsum()
            fig.add_trace(go.Scatter(
                x=list(range(1, len(cum) + 1)), y=cum, mode="lines+markers",
                name=label, line=dict(color=color, width=2),
            ))
    fig.update_layout(
        xaxis_title="Matchday", yaxis_title="Cumulative points",
        margin=dict(l=40, r=10, t=10, b=40), height=320,
        legend=dict(orientation="h", y=-0.2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
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

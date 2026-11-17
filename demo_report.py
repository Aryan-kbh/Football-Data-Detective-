"""Standalone, data-driven HTML evidence report; works without Streamlit.

Default fixtures are deliberately synthetic and labelled as such. When a real
StatsBomb or Metrica source is supplied, provenance labels change accordingly.
Never combines the two providers into a single imagined match.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

from fdd.analytics import pass_progression, passing_network
from fdd.tactics import goal_distance_progression
from fdd.plots import shot_map, network_map, pass_map, tracking_pitch
from fdd.service import analyze_statsbomb, analyze_metrica, Analysis
from fdd.sources import get_statsbomb_events, get_metrica_files
from fdd.tracking import tracking_snapshot

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"


def _p(fig, first=False) -> str:
    fig.update_layout(font=dict(color="#dce8e6", family="Arial"), paper_bgcolor="#101d25",
                      plot_bgcolor="#123a31", title_font=dict(size=18, color="#f4f9f8"),
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    return pio.to_html(fig, full_html=False, include_plotlyjs=True if first else False,
                       config={"responsive": True, "displayModeBar": True, "displaylogo": False})


def _table(data: pd.DataFrame, rows: int=65) -> str:
    return data.head(rows).to_html(index=False, escape=True, classes="gridtable", border=0)


def _card(value, label: str) -> str:
    return (f'<div class="metric"><small>{escape(label)}</small>'
            f'<strong>{escape(str(value))}</strong></div>')


def _load_stats(json_file: str | Path | None, match_id: int | None) -> tuple[Analysis,str]:
    if json_file and match_id:
        raise ValueError("Choose either a StatsBomb local JSON or a public match ID")
    if json_file:
        path = Path(json_file)
        return analyze_statsbomb(get_statsbomb_events(path=path), path.stem), "USER-SUPPLIED STATSBOMB-FORMAT FILE"
    if match_id is not None:
        return analyze_statsbomb(get_statsbomb_events(match_id), match_id), "STATSBOMB PUBLIC MATCH"
    return analyze_statsbomb(get_statsbomb_events(path=EXAMPLES/"statsbomb_demo.json")), "SYNTHETIC STATSBOMB-STYLE FIXTURE"


def _load_metrica(game: int | None) -> tuple[Analysis,str]:
    if game is None:
        files={key:(EXAMPLES/f"metrica_demo_{key}.csv").read_bytes() for key in ("events","home","away")}
        return analyze_metrica(files, "offline_demo"), "SYNTHETIC METRICA-STYLE FIXTURE"
    return analyze_metrica(get_metrica_files(game), game), "METRICA PUBLIC SAMPLE GAME"


def build_html_report(out: str | Path, *, statsbomb_json: str | Path | None = None,
                      statsbomb_match_id: int | None = None,
                      metrica_game: int | None = None) -> Path:
    stats, stats_label = _load_stats(statsbomb_json, statsbomb_match_id)
    tracks, tracking_label = _load_metrica(metrica_game)
    is_synthetic_stats = statsbomb_json is None and statsbomb_match_id is None
    is_synthetic_tracking = metrica_game is None
    both_synthetic = is_synthetic_stats and is_synthetic_tracking

    shot = stats.tables["shots"]
    plot_xg = px.line(shot, x="minute", y="cumulative_xg", color="team", markers=True,
                      title="Provided xG by team · cumulative") if not shot.empty else shot_map(shot)
    summary = stats.tables["team_summary"]
    team = str(summary.iloc[0].team) if not summary.empty else ""
    net = passing_network(stats.tables["events"],team) if team else pd.DataFrame()
    progressive = goal_distance_progression(stats.tables["events"],team) if team else pd.DataFrame()
    comparisons = tracks.tables["reconciliation"]
    candidates = comparisons.loc[comparisons.status.eq("review")]
    if candidates.empty:
        candidates = comparisons.loc[comparisons.status.eq("consistent")]
    selected = candidates.iloc[0] if not candidates.empty else None
    snapshot = (tracking_snapshot(tracks.home,tracks.away,int(selected.frame),
                                  period=int(selected.period) if pd.notna(selected.period) else None)
                if selected is not None else pd.DataFrame())
    plots = [
        _p(shot_map(shot), first=True),
        _p(plot_xg),
        _p(network_map(net)),
        _p(pass_map(progressive)),
        _p(tracking_pitch(snapshot,selected)),
    ]
    quality = stats.tables["quality_flags"]
    q = stats.tables["investigation_queue"]
    trackq = tracks.tables["investigation_queue"]
    mt_metrics=tracks.tables["dataset_metrics"]
    coverage=mt_metrics.loc[mt_metrics.metric.eq("comparison_coverage"),"value"]
    coverage_label=f"{float(coverage.iloc[0]):.1%}" if len(coverage) else "N/A"
    review_n=int(comparisons.status.eq("review").sum()) if not comparisons.empty else 0
    card_html="".join([
        _card(f"{len(stats.tables['events']):,}","STATSBOMB EVENTS"),
        _card(f"{len(quality):,}","STATSBOMB QA FLAGS"),
        _card(coverage_label,"SPATIAL VERIFICATION COVERAGE"),
        _card(f"{review_n:,}","METRICA REVIEW CANDIDATES"),
    ])
    label = "SYNTHETIC DATA ONLY" if both_synthetic else "SOURCE DISCLOSURE"
    notice = ("Both input matches are built-in synthetic fixtures. Findings do not represent real provider errors. "
              if both_synthetic else
              "Provider inputs are independent matches and must not be interpreted as synchronized with one another. ")
    notice += f"Events: {stats_label}. Tracking: {tracking_label}. No video is available or reviewed."
    quality_rules=(quality.groupby("rule").size().reset_index(name="flags") if not quality.empty else
                   pd.DataFrame(columns=["rule","flags"]))
    rule_graph = _p(px.bar(quality_rules, x="rule", y="flags", title="Rule frequency (not confirmed errors)"))
    comparison_view = (comparisons.loc[comparisons.status.ne("consistent"),[
        "event_row","frame","player","check","status","distance_m","clock_delta_s","reason"]]
        if not comparisons.empty else comparisons)
    metric_table = pd.concat([
        stats.tables["dataset_metrics"].assign(provider="StatsBomb"),
        tracks.tables["dataset_metrics"].assign(provider="Metrica")
    ],ignore_index=True)[["provider","metric","value","unit","definition"]]

    html=f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Football Data Detective · Quality evidence report</title>
<style>
:root{{--bg:#071218;--panel:#111f27;--line:#284049;--text:#e7f2f0;--muted:#a0b4bb;--green:#49d7a7;--amber:#ffd68e}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1250px;margin:auto;padding:38px 27px}}header{{padding-bottom:27px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:12px;letter-spacing:.16em;color:var(--green);font-weight:750}}h1{{font-size:43px;letter-spacing:-.045em;margin:10px 0 8px}}
h2{{font-size:26px;letter-spacing:-.02em;margin:42px 0 13px}}h3{{font-size:16px;margin:10px 0}}
p{{color:var(--muted);line-height:1.6;max-width:960px}}
.notice{{border:1px solid #9b7545;background:#392c1e;color:#ffe5b9;padding:14px 18px;border-radius:10px;margin:20px 0;font-size:14px;line-height:1.5}}
nav{{display:flex;gap:18px;flex-wrap:wrap;margin:22px 0}}nav a{{color:#b6d1ce;text-decoration:none;font-size:14px}}nav a:hover{{color:var(--green)}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:23px}}
.metric{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:19px}}
.metric small{{display:block;font-size:10px;color:var(--muted);letter-spacing:.08em;font-weight:700}}
.metric strong{{display:block;font-size:28px;margin-top:7px;line-height:1.15}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 17px;margin:13px 0;overflow-x:auto}}
.two{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
.gridtable{{font-size:12px;width:100%;border-collapse:collapse;text-align:left}}
.gridtable th{{background:#1d333b;color:#d2e7e5;font-weight:650}}
.gridtable th,.gridtable td{{padding:8px 10px;border-bottom:1px solid #2a444d;white-space:nowrap}}
footer{{color:var(--muted);font-size:12px;margin:54px 0 0;border-top:1px solid var(--line);padding-top:22px}}
@media(max-width:820px){{.metrics,.two{{grid-template-columns:1fr 1fr}}main{{padding:19px}}}}
@media(max-width:540px){{.metrics,.two{{grid-template-columns:1fr}}h1{{font-size:32px}}}}
</style></head><body><main>
<header><div class="eyebrow">FOOTBALL / EVENT QUALITY / SYNCHRONIZED TRACKING</div>
<h1>Football Data Detective</h1>
<p>Auditable football-data checks, tactical context, synchronized event-to-tracking reconciliation and reproducible data products.</p>
<div class="notice"><strong>{escape(label)}:</strong> {escape(notice)}</div>
<nav><a href="#overview">Overview</a><a href="#analytics">Football analytics</a><a href="#quality">QA investigation</a><a href="#tracking">Tracking reconciliation</a><a href="#method">Method & limitations</a></nav>
<div class="metrics">{card_html}</div></header>
<section id="overview"><h2>01 / Match overview</h2><p>Event feed: {escape(stats_label)}. The team metrics are calculated from the supplied event records, with provider-provided xG rather than a newly trained model.</p>
<div class="card">{_table(summary)}</div><div class="card">{plots[0]}</div><div class="card">{plots[1]}</div></section>
<section id="analytics"><h2>02 / Football analytics</h2><p>Passing network for {escape(team or 'no team available')} and a transparent alternative progression heuristic: at least 10 StatsBomb grid units of reduced distance to opposition goal. These metrics describe events, not automatically inferred formations.</p>
<div class="card">{plots[2]}</div><div class="card">{plots[3]}</div>
<h3>Possession outcomes (provider IDs)</h3><div class="card">{_table(stats.tables["possession_outcomes"], 50)}</div></section>
<section id="quality"><h2>03 / Data quality investigation</h2><p>A ranked, explainable review queue. Flags are <b>candidates</b>; they are not labels of true provider errors, and prioritization is not a probability.</p>
<div class="card">{rule_graph}</div><div class="card">{_table(q[["priority","rule","severity","team","player","reason","observed","expected"]],70)}</div></section>
<section id="tracking"><h2>04 / Event-to-tracking reconciliation</h2><p>Tracking source: {escape(tracking_label)}. Matching uses period plus frame and checks player position, ball location, receiving-player endpoint, and event-vs-frame clock. Metrica positions are normalized and converted to 105×68 metre pitch distances.</p>
<div class="card">{plots[4]}</div><div class="card">{_table(comparison_view,70)}</div>
<h3>Additional tracking-quality candidates</h3><div class="card">{_table(trackq[["priority","source_type","rule","team","period","player","reason"]],50)}</div>
<h3>Tracking detection continuity</h3><div class="card">{_table(tracks.tables["tracking_observation_completeness"],50)}</div></section>
<section id="method"><h2>05 / Verification and limitations</h2><p>Measured data quality is presented as transparent counts and coverages. It is not an accuracy score.</p>
<div class="card">{_table(metric_table,50)}</div>
<div class="two"><div class="card"><h3>Reproducibility</h3><p>Source hashes, per-match SQL storage, CSV tables, deterministic validation rules, automated tests and persistent human review decisions are included in the source project.</p></div>
<div class="card"><h3>What cannot be claimed</h3><p>No video validation, real-world labelled precision, or production-scale performance. Thresholds are heuristic. External public file downloads and the full Streamlit UI must be verified on an internet-connected machine.</p></div></div>
<p>StatsBomb Open Data: <a style="color:#55dcb4" href="https://github.com/hudl/open-data">source</a>. Metrica Sports Sample Data: <a style="color:#55dcb4" href="https://github.com/metrica-sports/sample-data">source</a>. Public data providers are not affiliated with this independent student project.</p></section>
<footer>Football Data Detective v6 · Values calculated dynamically from the loaded inputs · No AI-generated synthetic statistics represented as real match observations.</footer>
</main></body></html>'''
    target=Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html,encoding="utf-8")
    return target


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Make an interactive, offline HTML football QA evidence report")
    parser.add_argument("--out",default="demo_report.html")
    parser.add_argument("--statsbomb-json",default=None,help="Use a local StatsBomb events JSON file")
    parser.add_argument("--statsbomb-match-id",type=int,default=None,help="Download a real public StatsBomb events JSON")
    parser.add_argument("--metrica-game",type=int,choices=[1,2],default=None,help="Download public Metrica sample data")
    args=parser.parse_args()
    print(build_html_report(args.out, statsbomb_json=args.statsbomb_json,
                            statsbomb_match_id=args.statsbomb_match_id, metrica_game=args.metrica_game))

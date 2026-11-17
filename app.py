"""Football Data Detective · interactive public-data quality investigation app.

No match video is available or represented as if reviewed. Everything in the
synthetic fixtures is clearly labelled. Real samples require internet access.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from fdd.analytics import passing_network, pass_progression
from fdd.tactics import goal_distance_progression
from fdd.evaluation import evaluate_injection
from fdd.plots import shot_map, pass_map, network_map, tracking_pitch
from fdd.service import analyze_statsbomb, analyze_metrica, persist
from fdd.sources import get_metrica_files, get_statsbomb_events
from fdd.storage import read_reviews, save_review, read_table, tables_in_database
from fdd.tracking import tracking_snapshot, team_shape
from fdd.triage import reviewed_queue

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
EXAMPLES = ROOT / "examples"

st.set_page_config(page_title="Football Data Detective", page_icon="⚽", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
:root { --border:#d5dae1; }
.block-container {max-width: 1440px; padding-top: 1.2rem; padding-bottom:3rem;}
h1,h2,h3 {letter-spacing:-.025em;}
[data-testid="stMetric"] {border:1px solid rgba(140,145,155,.24);padding:14px 16px;border-radius:14px;}
[data-testid="stSidebar"] {border-right:1px solid rgba(140,145,155,.15);}
section[data-testid="stSidebar"] .block-container {padding-top:1rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Processing football match…", ttl=3600)
def statsbomb_analysis(kind: str, match_id: int, upload_bytes: bytes | None):
    if kind == "offline":
        events = get_statsbomb_events(path=EXAMPLES/"statsbomb_demo.json")
        return analyze_statsbomb(events,"offline_demo")
    if upload_bytes is not None:
        events = json.loads(upload_bytes.decode("utf-8-sig"))
        # Different uploads must not accidentally inherit each other's SQL reviews.
        upload_key = "uploaded_" + str(match_id) + "_" + hashlib.sha256(upload_bytes).hexdigest()[:10]
        return analyze_statsbomb(events, upload_key)
    return analyze_statsbomb(get_statsbomb_events(int(match_id)),int(match_id))

@st.cache_data(show_spinner="Importing synchronized event and tracking frames…", ttl=3600)
def metrica_analysis(kind: str, game: int):
    if kind == "offline":
        files = {k:(EXAMPLES/f"metrica_demo_{name}.csv").read_bytes() for k,name in
                 [("events","events"),("home","home"),("away","away")]}
        return analyze_metrica(files,"offline_demo")
    return analyze_metrica(get_metrica_files(game),game)


def metric_row(values):
    cols = st.columns(len(values))
    for col,(label,value,desc) in zip(cols,values):
        col.metric(label,value,help=desc)


def download_csv(df: pd.DataFrame, label: str, filename: str):
    st.download_button(label,df.to_csv(index=False).encode("utf-8"),file_name=filename,
                       mime="text/csv",key=f"download_{filename}")


def review_ui(db: Path, event_key: str, label: str):
    if not db.exists():
        st.info("Enable the reviewer workspace to save decisions in a match-specific SQL database.")
        if st.button("Enable persistent reviews and create SQL outputs", key="prepare_"+event_key):
            try:
                persist(analysis, OUTPUT)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create reviewer workspace: {exc}")
        return
    reviews = read_reviews(db)
    existing = reviews.loc[reviews.event_key.eq(event_key)]
    saved_status = str(existing.iloc[0].status) if not existing.empty else "unreviewed"
    saved_notes = str(existing.iloc[0].notes) if not existing.empty else ""
    st.subheader("Analyst decision")
    options = ["unreviewed", "confirmed_issue", "false_positive", "uncertain"]
    key = "review_"+event_key
    st.selectbox("Decision",options,index=options.index(saved_status),key=key+"_status")
    st.text_area("Notes and evidence",value=saved_notes,key=key+"_notes",
                 help="Explain the underlying football event and why the data is or isn't suspicious")
    if st.button("Save decision to SQL",type="primary",key=key+"_submit"):
        save_review(db,event_key,st.session_state[key+"_status"],st.session_state[key+"_notes"])
        st.success(f"Review saved for {label}.")


with st.sidebar:
    st.header("⚽ Football Data Detective")
    st.caption("Match intelligence / explainable data QA")
    dataset = st.selectbox("Dataset",[
        "StatsBomb · offline demo", "StatsBomb · public match", "Metrica · offline demo", "Metrica · public match"
    ])
    statsbomb_mode=dataset.startswith("StatsBomb")
    is_demo="offline" in dataset
    if statsbomb_mode:
        match_id=st.number_input("StatsBomb match ID",min_value=1,max_value=99_999_999,value=3788741,step=1,
                                 disabled=is_demo)
        upload=st.file_uploader("Optional events JSON",type="json",disabled=is_demo)
    else:
        game=st.selectbox("Metrica sample game",[1,2],disabled=is_demo)
    st.divider()
    st.caption("**Offline fixtures are synthetic.** Public matches download from StatsBomb or Metrica Sports and are cached locally.")
    st.caption("No synchronized match video is included. Flags are review candidates, never confirmed provider defects.")
    st.markdown("[StatsBomb data](https://github.com/statsbomb/open-data) · [Metrica data](https://github.com/metrica-sports/sample-data)")

st.title("Football Data Detective")
st.caption("Validate event feeds, reconcile synchronized tracking, investigate the football context, and export SQL data products.")
try:
    if statsbomb_mode:
        analysis=statsbomb_analysis("offline" if is_demo else "public",int(match_id),
                                    upload.getvalue() if not is_demo and upload else None)
    else:
        analysis=metrica_analysis("offline" if is_demo else "public",int(game))
except Exception as exc:
    st.error(f"Could not load the selected match: {exc}")
    st.info("Select an offline demo in the sidebar. It runs without internet and exercises the same processing pipeline.")
    st.stop()

if is_demo:
    st.warning("SYNTHETIC DEMONSTRATION DATA: includes deliberately injected anomalies; do not treat these as real match findings.",icon="🧪")
else:
    st.info(f"Public dataset: {analysis.provider}. Heuristic flags require human confirmation.",icon="ℹ️")

DB=OUTPUT/analysis.match_key/"football.sqlite"
queue = analysis.tables.get("investigation_queue", pd.DataFrame())
queue = reviewed_queue(queue, read_reviews(DB)) if DB.exists() else queue
with st.sidebar:
    st.divider()
    st.subheader("Review workload")
    if len(queue):
        reviewed_n = int(queue.review_state.ne("unreviewed").sum())
        st.metric("Reviewed candidates", f"{reviewed_n}/{len(queue)}")
        st.caption("A review candidate is not a proven data error. Priority is not a probability.")
    else:
        st.caption("No review candidates under the active rules.")

def pipeline_tab():
    st.subheader("Reproducible data products")
    metric_row([("Tables",len(analysis.tables),"SQL/CSV datasets"),
                ("Records",sum(len(v) for v in analysis.tables.values()),"Total across tables"),
                ("Local SQL","SQLite","Standard library; portable and testable")])
    if st.button("Build SQL data products",type="primary"):
        try:
            db=persist(analysis,OUTPUT)
            st.success(f"Created database, CSV exports and provenance manifest: {db}")
        except Exception as exc:
            st.error(f"Export failed: {exc}")
    if DB.exists():
        st.caption(f"Saved SQL database: `{DB}`")
        tablename=st.selectbox("Explore SQL table",tables_in_database(DB))
        try:
            st.dataframe(read_table(DB,tablename,limit=100),use_container_width=True,hide_index=True)
        except Exception as exc:
            st.error(str(exc))
        st.download_button("Download provenance manifest",(DB.parent/"manifest.json").read_bytes(),
                           file_name=f"{analysis.match_key}_manifest.json",mime="application/json")
    st.subheader("Dataset health diagnostics")
    st.caption("Coverage and flag counts are observations, not estimated ground-truth accuracy.")
    st.dataframe(analysis.tables["dataset_metrics"], use_container_width=True, hide_index=True)
    st.subheader("Tables available")
    st.dataframe(pd.DataFrame([{"table":n,"rows":len(v)} for n,v in analysis.tables.items()]),
                 hide_index=True,use_container_width=True)
    target=st.selectbox("Export CSV",list(analysis.tables))
    download_csv(analysis.tables[target],"Download selected table",f"{analysis.match_key}_{target}.csv")
    if analysis.raw_events is not None:
        st.subheader("Mutation-based quality check")
        if st.button("Run controlled synthetic corruption benchmark"):
            benchmark=evaluate_injection(analysis.raw_events)
            metric_row([("Injected",benchmark["injected"],"Targeted mutations"),
                        ("Exact detections",benchmark["detected_expected_rule"],"Expected new rule must fire"),
                        ("Synthetic recall",f"{benchmark['expected_rule_recall']:.1%}" if benchmark["expected_rule_recall"] is not None else "N/A","Does not prove real-world recall")])
            st.json(benchmark)

if statsbomb_mode:
    event_df=analysis.tables["events"]
    flags=analysis.tables["quality_flags"]
    summary=analysis.tables["team_summary"]
    metric_row([("Events",f"{len(event_df):,}","All provider events"),
                ("Passes",f"{event_df.type.eq('Pass').sum():,}","Attempts"),
                ("Shots",f"{event_df.type.eq('Shot').sum():,}","Shots with provider xG if available"),
                ("Review flags",f"{len(flags):,}","Flags, not validated errors")])
    tab1,tab2,tab3,tab4,tab5=st.tabs(["Match overview","Football analytics","Data quality","Event investigator","Pipeline & exports"])
    with tab1:
        st.subheader("Team performance")
        st.dataframe(summary,hide_index=True,use_container_width=True)
        st.plotly_chart(shot_map(analysis.tables["shots"]),use_container_width=True)
        shots=analysis.tables["shots"]
        if not shots.empty:
            fig=px.line(shots,x="minute",y="cumulative_xg",color="team",markers=True,
                        title="Provider xG accumulation by minute")
            st.plotly_chart(fig,use_container_width=True)
        st.caption("xG is StatsBomb's provided value, not a model trained here. StatsBomb locations use 120×80 coordinates.")
    with tab2:
        if summary.empty:
            st.info("No team analytics available")
        else:
            team=st.selectbox("Analyse team",summary.team.tolist())
            n=passing_network(event_df,team)
            st.plotly_chart(network_map(n),use_container_width=True)
            st.caption("Passing network: completed passes only; links show average origins/destinations. Not a full tactical model.")
            progressive=pass_progression(event_df,team)
            by_goal = goal_distance_progression(event_df, team)
            metric_row([("X-axis progression",len(progressive),"Completed passes advancing ≥10 StatsBomb x-units"),
                        ("Goal-distance progression",len(by_goal),"Completed passes reducing goal-centre distance by ≥10 grid units")])
            st.caption("These are TWO explicit heuristics, not an official classification or trained model. They can disagree.")
            st.plotly_chart(pass_map(by_goal),use_container_width=True)
            st.subheader("Provider-defined possession outcomes")
            poss=analysis.tables["possession_outcomes"]
            st.dataframe(poss.loc[poss.team.eq(team)].head(150),use_container_width=True,hide_index=True)
            st.caption("Final-third entries count completed passes crossing x=80. Event-span duration is NOT possession-control time.")
    with tab3:
        st.subheader("Automated data checks")
        st.caption("High severity means strong structural inconsistency; it does not prove match footage is wrong.")
        st.subheader("Ranked human review queue")
        st.caption("Priority is a transparent sorting heuristic, NOT a model confidence score.")
        if not queue.empty:
            q_status = st.multiselect("Review decisions", ["unreviewed", "confirmed_issue", "false_positive", "uncertain"], default=["unreviewed"], key="sb_qstatus")
            q = queue.loc[queue.review_state.isin(q_status)]
            st.dataframe(q, use_container_width=True, hide_index=True)
            download_csv(q, "Download triage queue", f"{analysis.match_key}_review_queue.csv")
        st.subheader("Rule-level findings")
        if flags.empty:
            st.success("No flags from current checks. This does not guarantee correct data.")
        else:
            st.bar_chart(flags.rule.value_counts())
            options=sorted(flags.rule.dropna().unique())
            rules=st.multiselect("Filter rules",options,default=options)
            severity=st.multiselect("Severity",["high","medium","low"],default=["high","medium","low"])
            subset=flags.loc[flags.rule.isin(rules)&flags.severity.isin(severity)]
            st.dataframe(subset,use_container_width=True,hide_index=True)
            download_csv(subset,"Download validation report",f"{analysis.match_key}_issues.csv")
    with tab4:
        st.subheader("Investigate an event")
        st.caption("A flag is a hypothesis. Review the position, nearby events, and source values before deciding.")
        if flags.empty:
            st.info("No flagged events in this match")
        else:
            ids=flags.row_id.dropna().astype(int).unique().tolist()
            selected=st.selectbox("Flagged event",ids,format_func=lambda i: f"Row {i} · {str(event_df.loc[event_df.row_id.eq(i),'type'].iloc[0])}")
            row=event_df.loc[event_df.row_id.eq(selected)].iloc[0]
            subset=flags.loc[flags.row_id.eq(selected)]
            st.dataframe(subset,hide_index=True,use_container_width=True)
            context=event_df.iloc[max(0,selected-6):min(len(event_df),selected+7)]
            st.plotly_chart(pass_map(context,row),use_container_width=True)
            st.subheader("Nearby events")
            st.dataframe(context[["row_id","minute","second","team","player","type","x","y","end_x","end_y"]],
                         hide_index=True,use_container_width=True)
            matching = queue.loc[queue.event_row.eq(selected)]
            if matching.empty:
                st.error("No source-versioned review identity available; review disabled.")
            else:
                review_ui(DB, str(matching.iloc[0].event_key), f"event {selected}")
    with tab5:
        pipeline_tab()
else:
    events=analysis.tables["events"]
    comp=analysis.tables["reconciliation"]
    tflags=analysis.tables["quality_flags"]
    verified=comp.status.isin(["consistent","review"]).sum() if not comp.empty else 0
    metric_row([("Events",f"{len(events):,}","Metrica annotated events"),
                ("Aligned checks",f"{verified:,}","Resolvable player/ball-frame comparisons"),
                ("Review cases",f"{comp.status.eq('review').sum():,}","Location discrepancy checks"),
                ("Unavailable",f"{comp.status.eq('unverifiable').sum():,}","Missing player/frame/ball tracking")])
    tab1,tab2,tab3,tab4,tab5=st.tabs(["Reconciliation","Tracking QA","Tactical spacing","Investigation","Pipeline & exports"])
    with tab1:
        st.subheader("Event ↔ tracking reconciliation")
        st.caption("Metrica events and tracking share frames. The reconciler also checks period and event-to-frame timestamp alignment.")
        st.subheader("Ranked investigation queue")
        st.caption("Missing tracking is marked unverifiable, not automatically wrong; priority is not probability.")
        if not queue.empty:
            q_status = st.multiselect("Review decisions", ["unreviewed", "confirmed_issue", "false_positive", "uncertain"], default=["unreviewed"], key="mt_qstatus")
            q = queue.loc[queue.review_state.isin(q_status)]
            st.dataframe(q.head(800), use_container_width=True, hide_index=True)
            download_csv(q, "Export investigation queue", f"{analysis.match_key}_review_queue.csv")
        st.subheader("Comparison coverage")
        if comp.empty:
            st.info("No spatial event comparisons")
        else:
            left,right=st.columns(2)
            left.bar_chart(comp.status.value_counts())
            right.bar_chart(comp.check.value_counts())
            statuses=st.multiselect("Status",["review","consistent","unverifiable"],default=["review","unverifiable"])
            st.dataframe(comp.loc[comp.status.isin(statuses)].head(1200),use_container_width=True,hide_index=True)
            metrics = analysis.tables.get("dataset_metrics", pd.DataFrame())
            if not metrics.empty:
                metric_lookup = metrics.set_index("metric")["value"]
                st.caption(f"Spatial verification coverage: {float(metric_lookup.get('spatial_coverage', 0)):.1%}; "
                           f"temporal alignment coverage: {float(metric_lookup.get('temporal_coverage', 0)):.1%}. "
                           "Unverifiable means missing or ambiguous evidence, not a confirmed error.")
    with tab2:
        st.subheader("Tracking quality")
        st.caption("Human speed and ball speed have distinct thresholds. Speed checks require consecutive frames.")
        completeness = analysis.tables.get("tracking_observation_completeness", pd.DataFrame())
        if not completeness.empty:
            st.subheader("Tracking detection continuity")
            st.caption("Completeness between an entity's first and last detection per period, NOT ground-truth player availability.")
            st.dataframe(completeness, use_container_width=True, hide_index=True)
        if tflags.empty:
            st.success("No violations in the rules applied to tracking frames.")
        else:
            st.bar_chart(tflags.rule.value_counts())
            st.dataframe(tflags.head(1000),use_container_width=True,hide_index=True)
    with tab3:
        shape=analysis.tables["team_shape"]
        st.subheader("Bounding-box team shape proxies")
        st.caption("Width and depth from tracked players. Sample fixtures contain only three players per team; no formations or pressing labels are inferred.")
        if shape.empty:
            st.info("Insufficient positions to compute spacing")
        else:
            fig=px.line(shape,x="frame",y="width_m",color="team",title="Tracked team width (m)")
            st.plotly_chart(fig,use_container_width=True)
            fig=px.line(shape,x="frame",y="depth_m",color="team",title="Tracked team depth (m)")
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(shape.head(150),use_container_width=True,hide_index=True)
    with tab4:
        st.subheader("Investigate every QA issue")
        st.caption("Includes unverified spatial comparisons and tracking-only findings. Every item can receive a review decision.")
        if queue.empty:
            st.info("No candidate issues currently identified")
        else:
            choices = queue.reset_index(drop=True)
            issue_idx = st.selectbox("Review candidate", list(choices.index), format_func=lambda i:
                    f"{choices.iloc[i].severity} · {choices.iloc[i].rule} · {choices.iloc[i].frame_or_minute} · {choices.iloc[i].review_state}")
            issue = choices.iloc[issue_idx]
            st.dataframe(choices.iloc[[issue_idx]], use_container_width=True, hide_index=True)
            frame_val = pd.to_numeric(issue.frame_or_minute, errors="coerce")
            frame = int(frame_val) if pd.notna(frame_val) else None
            comparison = None
            if issue.source_type == "event_tracking_comparison":
                # Keep issue identity stable across source versions; never infer a status from a row index alone.
                key = str(issue.event_key)
                match = __import__('re').match(r"^comparison_(\d+)_(.+)_[0-9a-f]{20}$", key)
                if match:
                    row_num = int(match.group(1))
                    name = str(issue.rule).rsplit("_", 1)[0]
                    candidates = comp.loc[comp.event_row.eq(row_num) & comp.check.eq(name)]
                    if not candidates.empty:
                        comparison = candidates.iloc[0]
            if frame is not None:
                period_val = comparison.period if comparison is not None else issue.get("period")
                period_numeric = pd.to_numeric(period_val, errors="coerce")
                period = int(period_numeric) if pd.notna(period_numeric) else None
                if period is None:
                    st.warning("Period not specified: ambiguous tracking frame. Snapshot suppressed to avoid showing the wrong half.")
                else:
                    snap = tracking_snapshot(analysis.home, analysis.away, frame, period=period)
                    if snap.empty:
                        st.warning("No unambiguous tracking snapshot for this period/frame (missing or duplicate data).")
                    else:
                        st.plotly_chart(tracking_pitch(snap, comparison), use_container_width=True)
                        st.caption(f"Tracking snapshot: period {period}, frame {frame}.")
                        st.dataframe(team_shape(snap), use_container_width=True, hide_index=True)
            else:
                st.info("No frame was provided for this issue. Inspect the raw report before deciding.")
            review_ui(DB, str(issue.event_key), str(issue.rule))
    with tab5:
        pipeline_tab()

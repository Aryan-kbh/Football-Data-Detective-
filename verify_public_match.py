"""OPTIONAL full public Metrica match audit on an internet-connected computer.

This command cannot establish ground truth: it records matching coverage and
provides explicit review candidates for a human to inspect. It does not
calculate a fake 'model accuracy' or pretend to inspect unavailable video.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

import pandas as pd

from fdd.service import analyze_metrica, persist
from fdd.sources import get_metrica_files


def run_public_match(*, game: int = 1, out: str = "real_match_output",
                     refresh: bool = False, local: dict[str, str] | None = None) -> Path:
    if local is not None:
        if set(local) != {"events", "home", "away"}:
            raise ValueError("Local input needs events, home and away files")
        files = {name: Path(path).read_bytes() for name, path in local.items()}
        source_label = "user-provided Metrica-format files (authenticity not independently established)"
        key = f"local_{game}"
    else:
        files = get_metrica_files(game=game, refresh=refresh)
        source_label = f"Metrica public Sample_Game_{game} downloaded from GitHub"
        key = game
    analysis = analyze_metrica(files, key)
    dest = persist(analysis, out)
    metrics = analysis.tables["dataset_metrics"].set_index("metric")["value"].to_dict()
    q = analysis.tables["investigation_queue"]
    recon = analysis.tables["reconciliation"]
    time = datetime.now(timezone.utc).isoformat()
    payload = {
        "source":source_label, "executed_at_utc":time,
        "python_version":sys.version.split()[0], "platform":platform.platform(),
        "event_count":len(analysis.tables["events"]),
        "reconciliation_checks":len(recon), "candidate_checks":int(recon.status.eq("review").sum()),
        "unverifiable_checks":int(recon.status.eq("unverifiable").sum()),
        "spatial_verification_coverage":metrics.get("spatial_coverage"),
        "temporal_alignment_coverage":metrics.get("temporal_coverage"),
        "source_sha256":analysis.manifest.get("sha256_sources"),
        "reviewed_match_video":False, "real_world_precision":None, "real_world_recall":None,
        "limitations":"Unreviewed discrepancy candidates cannot be called provider errors",
    }
    report = dest.parent/"PUBLIC_MATCH_VERIFICATION.md"
    lines = [f"# Public match verification: {source_label}",
             "", f"Executed: {time}", "", "## Measured output (not error accuracy)", "",
             "| Measurement | Value |", "|---|---:|"]
    for k, v in payload.items():
        if k in {"source_sha256", "limitations"}:
            continue
        lines.append(f"| {k.replace('_',' ')} | {v} |")
    lines += ["", "## Sources (SHA-256)", "", "```json",
              json.dumps(payload["source_sha256"], indent=2), "```", "",
              "## Highest-priority candidates (unconfirmed)", "",
              "| Period | Frame | Check | Team | Player | Reason |", "|---|---|---|---|---|---|"]
    for r in q.head(20).itertuples():
        cells = [str(getattr(r, c, "")) for c in ("period","frame_or_minute","rule","team","player","reason")]
        lines.append("| " + " | ".join(v.replace("|", "/").replace("\n", " ") for v in cells) + " |")
    lines += ["", "## Manual review checklist", "",
              "- [ ] Inspect at least ten flagged observations using independent evidence where available",
              "- [ ] Inspect a sample of unflagged observations before discussing false positives",
              "- [ ] Check substitutions, partial visibility, identity switches, and period boundaries",
              "- [ ] Record observations, unresolved cases and threshold justification in review notes",
              "", "**Do not report precision/recall without independently labelled errors.**"]
    report.write_text("\n".join(lines)+"\n", encoding="utf-8")
    (dest.parent/"public_verification.json").write_text(json.dumps(payload, indent=2, default=str),encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit a complete public Metrica game using full source files")
    parser.add_argument("--game", type=int, choices=[1,2], default=1)
    parser.add_argument("--out", default="real_match_output")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--events-file", default=None)
    parser.add_argument("--home-file", default=None)
    parser.add_argument("--away-file", default=None)
    args = parser.parse_args()
    paths = [args.events_file,args.home_file,args.away_file]
    if any(paths) and not all(paths):
        parser.error("Provide all three local files together or none to download the public sample")
    local = dict(zip(("events","home","away"), paths)) if all(paths) else None
    print("PUBLIC MATCH REPORT:",run_public_match(game=args.game, out=args.out,refresh=args.refresh, local=local))

"""Reproducible CLI for football match QA and SQL exports.

Examples:
  python pipeline.py statsbomb --demo
  python pipeline.py statsbomb --match-id 3788741
  python pipeline.py metrica --demo
  python pipeline.py metrica --game 1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fdd.service import analyze_statsbomb, analyze_metrica, persist
from fdd.sources import get_statsbomb_events, get_metrica_files

EXAMPLES = Path(__file__).resolve().parent / "examples"


def run_statsbomb(*, demo: bool = False, match_id: int = 3788741,
                  json_file: str | None = None, out: str = "output") -> dict:
    if demo:
        events = get_statsbomb_events(path=EXAMPLES / "statsbomb_demo.json")
        identifier = "offline_demo"
    else:
        events = get_statsbomb_events(match_id, path=json_file)
        identifier = Path(json_file).stem if json_file else match_id
    analysis = analyze_statsbomb(events, identifier)
    db = persist(analysis, out)
    return {**analysis.report, "database": str(db), "fixture": demo}


def run_metrica(*, demo: bool = False, game: int = 1, events_file: str | None = None,
                home_file: str | None = None, away_file: str | None = None,
                out: str = "output") -> dict:
    supplied = [events_file, home_file, away_file]
    if demo:
        files = {k: (EXAMPLES / f"metrica_demo_{name}.csv").read_bytes()
                 for k, name in [("events", "events"), ("home", "home"), ("away", "away")]}
        label = "offline_demo"
    elif all(supplied):
        files = {"events": Path(events_file).read_bytes(),
                 "home": Path(home_file).read_bytes(), "away": Path(away_file).read_bytes()}
        label = f"custom_{game}"
    elif any(supplied):
        raise ValueError("Provide all 3 local Metrica files, or none to download public samples")
    else:
        files = get_metrica_files(game)
        label = game
    analysis = analyze_metrica(files, label)
    db = persist(analysis, out)
    return {**analysis.report, "database": str(db), "fixture": demo,
            "comparison_coverage": analysis.manifest["comparison_coverage"]}


def main():
    parser = argparse.ArgumentParser(description="Football Data Detective: public football data QA")
    subs = parser.add_subparsers(dest="source")
    s = subs.add_parser("statsbomb", help="StatsBomb event pipeline")
    s.add_argument("--demo", action="store_true", help="Fully offline synthetic fixture")
    s.add_argument("--match-id", type=int, default=3788741)
    s.add_argument("--json", dest="json_file", help="Local real StatsBomb events JSON")
    s.add_argument("--out", default="output")
    m = subs.add_parser("metrica", help="Metrica synchronized event/tracking pipeline")
    m.add_argument("--demo", action="store_true", help="Fully offline synthetic fixture")
    m.add_argument("--game", type=int, default=1, choices=[1,2])
    m.add_argument("--events-file")
    m.add_argument("--home-file")
    m.add_argument("--away-file")
    m.add_argument("--out", default="output")
    args = parser.parse_args()
    if args.source is None:
        parser.print_help()
        return
    if args.source == "statsbomb":
        report = run_statsbomb(demo=args.demo, match_id=args.match_id, json_file=args.json_file, out=args.out)
    else:
        report = run_metrica(demo=args.demo, game=args.game, events_file=args.events_file,
                             home_file=args.home_file, away_file=args.away_file, out=args.out)
    print(json.dumps(report, indent=2, default=str))

if __name__ == "__main__":
    main()

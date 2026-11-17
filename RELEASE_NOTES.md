# Football Data Detective v6.1 | targeted CV-submission patch

Addresses the three remaining issues identified by an independent review of v6.

## Fixed

1. **Reversed frames:** explicit `out_of_order_tracking_frame` flags for decreasing frame numbers inside a period. Period transitions do not trigger a false alarm.
2. **Missing metadata:** `missing_tracking_frame_metadata`, `missing_tracking_time_metadata`, and (when period column exists) `missing_tracking_period_metadata` flag missing, malformed, or non-finite values.
3. **Cross-feed discrepancies:** vectorized `cross_feed_clock_mismatch` and `cross_feed_ball_mismatch` compare the unique shared `(period, frame)` observations in the two tracking feeds. Contradictory duplicate keys are excluded from comparison and remain reviewable through the existing duplicate-frame rule. An explicit `cross_feed_ball_tolerance_m` setting defaults to 2 m and is an uncalibrated review threshold.

## Verification

- 116 passing tests, 3 skipped (two optional internet tests and the Streamlit test).
- Offline release verification regenerates synthetic data products, checks database exports, and validates the mutation benchmark.
- These checks **do not prove** that complete public Metrica data or the Streamlit GUI work on the user's Windows machine.
- No real-world validation accuracy or precision/recall is claimed.

## Recommended next step for Veo

Run `python verify_public_match.py --game 1` on a connected machine, inspect real flagged cases, and publish a reproducible case study before asserting anything about authentic data performance. Submit the project as a tested, AI-assisted student prototype rather than a production-ready or trained AI system.

# Football Data Detective v6 | Second independent-audit response

This release repairs all six specifically reproduced defects from the independent v5.1 re-audit, expands football analytics, and adds independent hand-calculated regression cases.

## Correctness fixes

- Python 3.11-compatible source syntax and explicit grammar test.
- Detection of multi-frame tracking dropout runs instead of only isolated frames; guards against crossing periods or false claims about substitutions.
- Period preserved in tracking flags, review identities, and dashboard retrieval.
- Snapshot suppressed for duplicate or period-ambiguous frames.
- Start and end clock discrepancies displayed and prioritized in seconds.
- Shot xG unavailable shown as unknown, never zero.
- Metrica kickoff end-frame 0 treated as missing annotation, based on included public-format excerpt.

## Football analytics and evidence

- Goal-distance-reduction progressive-pass alternative, with manually computed reference tests.
- Possession outcomes with final-third pass entries, known/missing provider xG and event-span durations.
- Per-entity, per-period tracking observation continuity statistics.
- Optional public-data verification command with a source-provenance report.
- Wider adversarial test coverage, including exact period identity and ambiguous snapshots.

## Known limitations

Synthetic fixture and release checks are verified. Full public data imports, real-world QA accuracy, video verification and Streamlit end-to-end behavior have **not** been verified in this environment. The user can run `python verify_public_match.py --game 1` and `streamlit run app.py` on an internet-connected Windows computer to close part of this gap.

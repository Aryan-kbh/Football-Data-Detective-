# Football Data Detective ⚽

**Football event analysis and tracking-data quality checks in Python.**

Football Data Detective helps explore match statistics and investigate possible inconsistencies in football event and player-tracking data. It works with publicly available [StatsBomb Open Data](https://github.com/hudl/open-data) and [Metrica Sports sample data](https://github.com/metrica-sports/sample-data). The two providers' matches are processed **separately**: Metrica event records are compared only with tracking data from the corresponding Metrica match.

![Preview of the interactive synthetic-data report](docs/preview.png)

*Preview uses synthetic demo data, not observations from an actual match.*

## What it does

- **Football analytics:** shot maps, provider-supplied expected goals (xG), passing networks, progressive passes and event-based possession summaries.
- **Event-data checks:** missing IDs, incomplete locations, invalid coordinates, unusual time values and discrepancies in recorded pass measurements.
- **Tracking-data checks:** missing or out-of-order frames, unusual player movement, gaps in observations and differences between home/away ball-tracking feeds.
- **Event-to-tracking comparison:** aligns Metrica event annotations with tracking frames and checks player positions, ball positions and event timing when the required information is available.
- **Investigation dashboard:** displays flagged observations for review and saves analyst decisions and notes in SQLite.
- **Repeatable exports:** produces per-match SQLite databases, CSV tables and source manifests.

The checks are rule-based. A flag means **needs review**, not that a provider has made a confirmed error. Some observations are marked **unverifiable** when the necessary tracking evidence is missing or ambiguous.

## Datasets and example runs

| Dataset | Purpose |
|---|---|
| StatsBomb Open Data | Explore match events and run event-data quality checks |
| Metrica Sports sample data | Compare event annotations with synchronized player/ball tracking from the same sample match |

In local public-data demonstrations, the dashboard loaded **3,803 StatsBomb event records** from Italy vs Turkey and **1,745 Metrica event records** from a separate sample match. These figures describe records loaded, not the number of provider errors confirmed.

The repository also includes **synthetic offline examples** so the pipeline can be tested without downloading large public matches. The bundled HTML report and preview are based on synthetic data.

## Quick start

**Requirements:** Python 3.11 or newer and internet access to install Python packages.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, you can alternatively run `start_dashboard_windows.bat` from the project folder; it creates the virtual environment, installs dependencies and starts the app.

For a no-installation preview, download [`demo_report.html`](demo_report.html) and open it in a browser. This report uses synthetic example data.

### Run the offline pipelines

```bash
python pipeline.py statsbomb --demo --out output
python pipeline.py metrica --demo --out output
```

### Run pipelines with public datasets

```bash
# StatsBomb match events
python pipeline.py statsbomb --match-id 3788741 --out output

# Metrica synchronized event and tracking data (Game 1)
python pipeline.py metrica --game 1 --out output
```

These downloads need an internet connection. You can also provide local StatsBomb JSON and Metrica CSV files; see `python pipeline.py statsbomb --help` and `python pipeline.py metrica --help`.

## Testing

```bash
python -m pytest -q --cov=fdd --cov-report=term-missing
```

**Verified on Python 3.13.5:** 116 tests passed, 3 tests skipped, and **93% statement coverage** of the core `fdd` package. The skipped tests are two optional network integrations and one Streamlit smoke test in the environment used for verification. The test suite produced one non-failing pandas deprecation warning.

Coverage describes code exercised by tests. It is **not** a measure of football-data accuracy, and it does not include the complete Streamlit UI. Synthetic test cases do not establish real-world detection precision or recall.

## Project structure

| Path | Contents |
|---|---|
| `fdd/` | Parsing, analytics, validation, tracking, investigation and storage logic |
| `app.py` | Streamlit dashboard |
| `pipeline.py` | Command-line data processing |
| `tests/` | Automated regression and validation tests |
| `examples/` | Clearly labelled synthetic datasets and a small public-format excerpt |
| `sample_outputs/` | Example CSV and SQLite outputs generated from synthetic fixtures |
| `docs/` | Rule definitions, data dictionary, verification notes and case study |
| `demo_report.html` | Standalone interactive synthetic-data report |

More detail: [validation rules](docs/VALIDATION_RULES.md), [data dictionary](docs/DATA_DICTIONARY.md), [verification](docs/VERIFICATION.md), [case study](docs/CASE_STUDY.md), and [release notes](RELEASE_NOTES.md).

## Scope and limitations

- Metrica **event and tracking data are synchronized**; synchronized match **video is not included**. This tool does not check events against video footage.
- The thresholds are configurable review rules, not a trained anomaly detector. The project does not train its own xG model; it uses provider-supplied xG.
- Public-data runs demonstrate loading and processing, not independent confirmation of genuine annotation errors. A full expert-labelled evaluation would be needed to measure precision and recall.
- Team-shape and possession measures are descriptive approximations based on the available data, not validated tactical or formation predictions.

## Data credits and license

Football data is credited to [StatsBomb Open Data](https://github.com/hudl/open-data) and [Metrica Sports sample data](https://github.com/metrica-sports/sample-data), subject to their respective terms. Code in this repository is licensed under [MIT](LICENSE). The dataset providers have not endorsed this project.

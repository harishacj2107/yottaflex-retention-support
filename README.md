# YottaFlex supportive retention signals

A local, end-to-end demonstration for **prioritizing supportive retention conversations** from synthetic engagement, tenure, career, and workload signals. It generates a reproducible workforce cohort, validates its relational and temporal rules, evaluates an explainable prioritization heuristic on a held-out cohort, and serves a small local review dashboard.

This is a candidate project, not an employment decision system. Scores are supportive cues only. A manager or HR partner must review context and decide whether a voluntary check-in is appropriate. The demo contains no real employee records, protected attributes, or external datasets.

## Quick start (Windows PowerShell)

Requires Python 3.10 or newer. The application uses only the Python standard library; no hosted service or package download is needed.

```powershell
cd yottaflex-retention-support
python run.py generate --size starter
python run.py validate
python run.py serve
```

Open `http://127.0.0.1:8000` in a browser. Press Ctrl+C in the terminal to stop it.

Generate the requested 10,000-employee cohort with the fixed default seed:

```powershell
python run.py generate --size full --seed 20261022
```

To write it elsewhere, pass `--output path\to\folder`. Use `--count 1000` to choose any scale from 1 to 10,000; the starter and full modes use the same generator. Recreate all artifacts twice and compare their checksums with:

```powershell
python run.py repro-check --size full --seed 20261022
```

Run the dashboard against another generated output folder with `python run.py serve --input path\to\folder`.

## What the workflow does

1. Creates role, team, and compensation-band masters before employees and dependent records.
2. Generates 24 months of synthetic monthly workload history, quarterly tenure snapshots, engagement surveys (including explicit nonresponse), promotions, and internal transfers. Records stop after a simulated exit.
3. Scores each employee at **2026-06-30** using only records dated on or before that feature cutoff. Voluntary attrition is a separate synthetic label for **2026-07-01 through 2026-12-31**.
4. Creates intervention records only for the supportive conversation queue and appends explicit lifecycle events when a check-in moves from planned to completed. Simulated intervention outcomes illustrate workflow states and are not causal claims.
5. Writes independent CSV and JSON Lines files for each entity, a SQLite database with foreign-key and check constraints, SQL DDL, a feature manifest, separate ground truth, validation and temporal evaluation summaries, source manifest, and SHA-256 checksums.
6. Keeps four labelled negative scenarios in `edge_cases.csv` and `ground_truth.json`; these fixtures never enter scoring features.

## Actors

- Managers and HR partners review the prioritized queue and choose whether a supportive check-in is appropriate.
- Employees participate in voluntary conversations; the dashboard does not make decisions about them.
- IT/operations can run generation, validation, and the local server. A system administrator can review schema, checksums, and lifecycle reports.

## Scoring and safeguards

The baseline score begins at 25 and adds transparent rule points for low recent engagement, low manager support, low career-growth feedback, a decline in engagement, elevated or increasing overtime (benchmarked by role family), and long tenure without a recorded promotion. Thresholds create `priority` (60+), `monitor` (40–59), and `no_signal` (<40) bands. Scores are capped at 100.

Missing survey responses remain null. They add no negative points and reduce confidence. Each displayed row includes its factors, confidence, and a human-review requirement. The review queue fails closed and omits any score without an explanation, explicit human-review requirement, and safe-use guardrail. Future outcomes, interventions, and ground-truth labels are excluded from the feature set. The dashboard exposes no termination, compensation, or performance recommendation.

Outcomes are generated from a seeded propensity that combines latent engagement, workload, and career-progression drivers; a second seeded draw selects whether and when an exit occurs. The generated label is not independently assigned. Because labels are synthetic, observed predictive metrics are workflow checks only and do not establish real-world validity.

## Temporal evaluation

The generator reports ROC AUC, precision and recall among the highest-scored 20%, and lift over prevalence. The held-out cohort is the deterministic 20% of employee IDs whose numeric suffix is divisible by five. Features end on June 30, 2026; labels are observed only in the following six-month horizon. Evaluation is generated from synthetic labels and should not be interpreted as evidence that the heuristic is valid for real people.

## Output layout

`data/generated/` contains the default starter cohort. Full mode writes the same artifact set at 10,000 employees. Each entity has a `.csv` and `.jsonl` export. `yottaflex.sqlite` contains all generated entities; `schema.sql` has DDL. `ground_truth.json` and `edge_cases.csv` are separate from model inputs. `validation_summary.json`, `evaluation_metrics.json`, `feature_manifest.json`, `dataset_manifest.json`, `source_manifest.csv`, and `checksums.sha256` make provenance and checks reviewable.

See [`docs/data_dictionary.md`](docs/data_dictionary.md) for field definitions and [`docs/schema.md`](docs/schema.md) for keys, relationships, cardinality, effective dates, and lifecycle rules. See [`docs/ai_use.md`](docs/ai_use.md) for prompt-history and AI-use disclosure.

## Limits and next steps

- All records and outcomes are synthetic. They must not be merged with real employee data or used for employment decisions.
- This is a deterministic rule-based demonstration, not a trained or validated attrition model.
- Simulated intervention responses do not estimate treatment effects.
- The local dashboard is intended for a single-user review on the same machine; it has no authentication and should not be exposed to a network.
- A production evaluation would need lawful, consent-aware data governance, stakeholder review, privacy and fairness assessment, validation across time and groups, monitoring, and a human-led support process.

## Submission checklist

- [x] Working local code and clear setup/run/verification steps.
- [x] Fixed-seed generator and parameterized starter/full scale.
- [x] Normalized CSV/JSONL and SQLite seed data plus schema.
- [x] Separate anomaly ground truth and labelled negative scenarios.
- [x] Validation summary, temporal metrics, source manifest, and reproducibility check.
- [x] AI-use disclosure and prompt-history record.
- [ ] Publish this project in a dedicated **public GitHub repository** and submit that repository link through the candidate portal before the deadline. Keep it public and editable through the deadline. Do not commit secrets or unrelated personal information.

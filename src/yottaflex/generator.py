from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .model import TABLES, TABLE_SQL, write_rows, write_sqlite
from .scoring import evaluate, score_all
from .validation import validate

START_YEAR = 2025
FEATURE_CUTOFF = "2026-06-30"
HORIZON_END = "2026-12-31"
DEFAULT_SEED = 20261022

ROLE_FAMILIES = ["Engineering", "Operations", "Customer Success", "Product", "Finance"]
TEAM_FUNCTIONS = ["Platform", "Data", "Applications", "Service Delivery", "Customer Care", "Product", "People Operations", "Finance", "Security", "Sales", "Quality", "Research"]


def month_date(month_index: int, day: int = 1) -> date:
    year = START_YEAR + (month_index - 1) // 12
    month = (month_index - 1) % 12 + 1
    return date(year, month, day)


def end_of_month(month_index: int) -> date:
    year = START_YEAR + (month_index - 1) // 12
    month = (month_index - 1) % 12 + 1
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    from datetime import timedelta
    return next_month - timedelta(days=1)


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def generate(count: int = 250, seed: int = DEFAULT_SEED) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Generate a reproducible, synthetic two-year workforce cohort."""
    rng = random.Random(seed)
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLES}
    roles: list[dict[str, Any]] = []
    role_by_family_level: dict[tuple[str, int], str] = {}
    for family_index, family in enumerate(ROLE_FAMILIES, 1):
        for level in range(1, 6):
            role_id = f"ROL-{family_index:02d}-{level}"
            role_by_family_level[(family, level)] = role_id
            roles.append({"role_id": role_id, "role_name": f"{family} {['Associate','Specialist','Senior','Lead','Principal'][level-1]}", "job_family": family, "level": level, "active": 1})
    teams = [{"team_id": f"TEAM-{i:03d}", "team_name": f"{name} Team", "function": name, "active": 1} for i, name in enumerate(TEAM_FUNCTIONS, 1)]
    bands = [{"band_id": f"BAND-L{level}", "level": level, "currency": "USD", "min_annual": 42000 + (level - 1) * 18000, "max_annual": 65000 + (level - 1) * 24000, "effective_from": "2025-01-01", "effective_to": None} for level in range(1, 6)]
    tables["roles"], tables["teams"], tables["compensation_bands"] = roles, teams, bands

    employee_info: dict[str, dict[str, Any]] = {}
    raw_workload: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_surveys: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_promotions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_transfers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits: dict[str, int | None] = {}
    quality_cases: list[dict[str, Any]] = []
    survey_counter = 0
    promotion_counter = 0
    transfer_counter = 0

    for n in range(1, count + 1):
        employee_id = f"EMP-{n:06d}"
        family = ROLE_FAMILIES[(n - 1) % len(ROLE_FAMILIES)]
        initial_level = rng.choices([1, 2, 3, 4], weights=[35, 35, 23, 7])[0]
        role_id = role_by_family_level[(family, initial_level)]
        team_id = f"TEAM-{rng.randint(1, len(teams)):03d}"
        hire_month = rng.randint(1, 108)  # months before the 2025-01 cohort start
        hire_total_months = 2025 * 12 - hire_month
        hire_year, hire_month_zero = divmod(hire_total_months, 12)
        hire_date = date(hire_year, hire_month_zero + 1, rng.randint(1, 27))
        employee_info[employee_id] = {"role_id": role_id, "family": family, "level": initial_level, "hire_level": initial_level, "team_id": team_id, "hire_date": hire_date, "hire_month": hire_month}

        # A latent propensity is derived from work/career/engagement drivers. It
        # drives both observed pre-cutoff signals and the future outcome label.
        latent = rng.random()
        engagement_baseline = rng.choices([2, 3, 4, 5], weights=[8, 30, 47, 15])[0]
        workload_bias = rng.random()
        promotion_month = rng.randint(4, 16) if initial_level < 5 and rng.random() < 0.23 else None
        if promotion_month:
            promotion_counter += 1
            raw_promotions[employee_id].append({"promotion_id": f"PROM-{promotion_counter:06d}", "employee_id": employee_id, "effective_date": iso(end_of_month(promotion_month)), "from_level": initial_level, "to_level": initial_level + 1, "reason": "career_progression"})
            initial_level += 1
            role_id = role_by_family_level[(family, initial_level)]
            employee_info[employee_id]["role_id"] = role_id
            employee_info[employee_id]["level"] = initial_level

        # Pre-outcome monthly history. Some peaks are benign by construction.
        tenure = 0
        last_team = team_id
        for month in range(1, 25):
            month_end = end_of_month(month)
            tenure += 1
            benign_peak = int(rng.random() < 0.09)
            base_overtime = 1.5 + workload_bias * 10 + (latent - 0.5) * 3
            overtime = max(0.0, min(35.0, rng.gauss(base_overtime + (13 if benign_peak else 0), 3.5)))
            hours_noise = max(-15.0, min(15.0, rng.gauss(0, 5)))
            hours = round(160 + overtime + hours_noise, 1)
            utilization = max(35.0, min(145.0, round(rng.gauss(76 + workload_bias * 13 + (16 if benign_peak else 0), 8), 1)))
            raw_workload[employee_id].append({"workload_id": f"LOAD-{employee_id}-{month_date(month).strftime('%Y%m')}", "employee_id": employee_id, "snapshot_month": month_date(month).strftime("%Y-%m"), "hours_worked": hours, "overtime_hours": round(overtime, 1), "utilization_pct": utilization, "benign_peak": benign_peak})
            if month in (3, 6, 9, 12, 15, 18, 21, 24):
                quarter = f"{month_date(month).year}Q{(month_date(month).month - 1)//3 + 1}"
                survey_counter += 1
                missing = rng.random() < 0.12
                stress_adjust = int(workload_bias > 0.77 and month >= 9)
                engagement = max(1, min(5, engagement_baseline - stress_adjust - int(latent > .78 and month >= 12) + rng.choice([-1, 0, 0, 0, 1])))
                manager_support = max(1, min(5, rng.choices([1, 2, 3, 4, 5], [3, 9, 27, 43, 18])[0] - int(latent > .86)))
                career_growth = max(1, min(5, rng.choices([1, 2, 3, 4, 5], [5, 12, 31, 38, 14])[0] - int(promotion_month is None and month >= 15 and latent > .65)))
                raw_surveys[employee_id].append({"survey_id": f"SURV-{month_date(month).year}-{survey_counter:06d}", "employee_id": employee_id, "survey_date": iso(month_end), "quarter": quarter, "engagement_score": None if missing else engagement, "manager_support_score": None if missing else manager_support, "career_growth_score": None if missing else career_growth, "response_status": "missing" if missing else "responded"})
            if month in (7, 13, 19) and rng.random() < 0.045:
                new_team = f"TEAM-{rng.randint(1, len(teams)):03d}"
                if new_team == last_team:
                    new_team = f"TEAM-{int(last_team[-3:]) % len(teams) + 1:03d}"
                transfer_counter += 1
                raw_transfers[employee_id].append({"transfer_id": f"XFER-{transfer_counter:06d}", "employee_id": employee_id, "effective_date": iso(month_date(month)), "from_team_id": last_team, "to_team_id": new_team, "reason": "internal_transfer"})
                last_team = new_team
            # Stored later after exit month has been assigned; no row is made post-exit.
            raw_workload[employee_id][-1]["_month_index"] = month
        # Outcome probability is explicitly tied to the latent risk drivers; then
        # a deterministic seeded draw selects whether and when a voluntary exit occurs.
        propensity = min(.92, max(.05, .10 + .42 * latent + .20 * workload_bias + .14 * (engagement_baseline <= 3) - .10 * (promotion_month is not None)))
        p_exit = .025 + .105 * propensity  # 3%–12% over the six-month future horizon
        exit_month = None
        if rng.random() < p_exit:
            exit_month = rng.randint(19, 24)
        exits[employee_id] = exit_month

    # Build employee master rows after outcome generation so status is derived.
    for employee_id, info in employee_info.items():
        exit_month = exits[employee_id]
        final_team = raw_transfers[employee_id][-1]["to_team_id"] if raw_transfers[employee_id] else info["team_id"]
        tables["employees"].append({"employee_id": employee_id, "role_id": info["role_id"], "team_id": final_team, "hire_date": iso(info["hire_date"]), "initial_level": info["hire_level"], "status": "voluntarily_exited" if exit_month else "active", "synthetic": 1})
        tables["promotion_history"].extend(raw_promotions[employee_id])
        tables["team_transfers"].extend(raw_transfers[employee_id])
        for w in raw_workload[employee_id]:
            if exit_month is None or w["_month_index"] <= exit_month:
                row = dict(w); row.pop("_month_index", None)
                tables["workload_snapshots"].append(row)
        for s in raw_surveys[employee_id]:
            month = int(s["survey_date"][5:7]) + (int(s["survey_date"][:4]) - START_YEAR) * 12
            if exit_month is None or month <= exit_month:
                tables["engagement_surveys"].append(s)
        # Quarter-end snapshots (8 quarters, through exit quarter if needed).
        level = max(1, info["level"] - (1 if raw_promotions[employee_id] and info["level"] > 1 else 0))
        current_role = role_by_family_level[(info["family"], level)]
        current_team = info["team_id"]
        transfers = sorted(raw_transfers[employee_id], key=lambda t: t["effective_date"])
        promotion = raw_promotions[employee_id][0] if raw_promotions[employee_id] else None
        for month in (3, 6, 9, 12, 15, 18, 21, 24):
            if exit_month and month > exit_month:
                break
            if promotion and month >= int(promotion["effective_date"][5:7]) + (int(promotion["effective_date"][:4]) - START_YEAR) * 12:
                level = promotion["to_level"]
                current_role = role_by_family_level[(info["family"], level)]
            quarter_date = end_of_month(month)
            for transfer in transfers:
                if transfer["effective_date"] <= iso(quarter_date):
                    current_team = transfer["to_team_id"]
            tenure_months = (quarter_date.year - info["hire_date"].year) * 12 + quarter_date.month - info["hire_date"].month
            tables["tenure_snapshots"].append({"snapshot_id": f"SNAP-{employee_id}-{quarter_date.year}Q{(quarter_date.month-1)//3+1}", "employee_id": employee_id, "snapshot_quarter": f"{quarter_date.year}Q{(quarter_date.month-1)//3+1}", "snapshot_month": quarter_date.strftime("%Y-%m"), "tenure_months": tenure_months, "role_id": current_role, "team_id": current_team, "band_id": f"BAND-L{level}", "employment_status": "active"})
        exit_date = end_of_month(exit_month) if exit_month else None
        tables["attrition_outcomes"].append({"outcome_id": f"OUT-{employee_id}-2026", "employee_id": employee_id, "feature_cutoff": FEATURE_CUTOFF, "horizon_end": HORIZON_END, "voluntary_attrition": int(exit_month is not None), "termination_date": iso(exit_date), "label_rule": "voluntary_exit_draw_from_pre_cutoff_driver_propensity_v1"})

    tables["risk_scores"] = score_all(tables, FEATURE_CUTOFF)
    # Simulated supportive actions use only the prioritization list. Actions are
    # not employment decisions and outcomes are illustrative, not causal evidence.
    intervention_count = 0
    intervention_event_count = 0
    for score_row in sorted(tables["risk_scores"], key=lambda r: (-r["risk_score"], r["employee_id"])):
        if score_row["priority_band"] != "priority":
            continue
        intervention_count += 1
        employee_id = score_row["employee_id"]
        score_value = score_row["risk_score"]
        status = "completed" if score_value >= 78 else "planned"
        simulated = "supportive_response" if score_value >= 78 else "pending"
        intervention_id = f"INT-2026-{intervention_count:06d}"
        tables["interventions"].append({"intervention_id": intervention_id, "employee_id": employee_id, "created_date": "2026-07-01", "intervention_type": "manager_supportive_check_in", "priority_band": "priority", "status": status, "simulated_outcome": simulated, "closed_date": "2026-07-15" if status == "completed" else None})
        intervention_event_count += 1
        tables["intervention_events"].append({"intervention_event_id": f"IEVT-2026-{intervention_event_count:06d}", "intervention_id": intervention_id, "event_date": "2026-07-01", "from_status": None, "to_status": "planned", "simulated_outcome": "pending"})
        if status == "completed":
            intervention_event_count += 1
            tables["intervention_events"].append({"intervention_event_id": f"IEVT-2026-{intervention_event_count:06d}", "intervention_id": intervention_id, "event_date": "2026-07-15", "from_status": "planned", "to_status": "completed", "simulated_outcome": "supportive_response"})

    # Separate, labelled QA fixtures exercise specified exception pathways.
    sample = "EMP-000001" if count else "EMP-000000"
    quality_cases = [
        {"case_id": "CASE-001", "issue_type": "future_information_leak", "employee_id": sample, "fixture": {"feature_cutoff": FEATURE_CUTOFF, "leaked_field": "termination_date", "leaked_value": "2026-10-31"}, "expected_decision": "reject feature; scoring uses records dated on or before cutoff"},
        {"case_id": "CASE-002", "issue_type": "missing_survey_treated_as_negative", "employee_id": sample, "fixture": {"response_status": "missing", "engagement_score": None}, "expected_decision": "do not impute a low score; lower confidence and disclose missingness"},
        {"case_id": "CASE-003", "issue_type": "outcome_label_date_inconsistent", "employee_id": sample, "fixture": {"voluntary_attrition": 0, "termination_date": "2026-09-30"}, "expected_decision": "validation failure; label and termination date must reconcile"},
        {"case_id": "CASE-004", "issue_type": "individual_score_without_explanation_or_human_review", "employee_id": sample, "fixture": {"risk_score": 88, "explanation": "", "human_review_required": 0}, "expected_decision": "block display; require explanation and human review; no employment decision"},
    ]
    manifest = {
        "dataset_name": "YottaFlex synthetic supportive retention cohort",
        "generator_version": "1.0.0",
        "seed": seed,
        "employee_count": count,
        "start_month": "2025-01",
        "end_month": "2026-12",
        "feature_cutoff": FEATURE_CUTOFF,
        "outcome_horizon_end": HORIZON_END,
        "sensitive_attributes_included": False,
        "provenance": "Entirely synthetic records generated by this repository; no external employee data used.",
        "entity_row_counts": {name: len(rows) for name, rows in tables.items()},
    }
    return tables, {"manifest": manifest, "quality_cases": quality_cases}


def export(output: Path, count: int = 250, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    tables, supporting = generate(count, seed)
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output, tables)
    write_sqlite(output / "yottaflex.sqlite", tables)
    (output / "schema.sql").write_text("\n".join([f"CREATE TABLE {name} ({definition});" for name, definition in TABLE_SQL.items()]) + "\n", encoding="utf-8")
    (output / "dataset_manifest.json").write_text(json.dumps(supporting["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "ground_truth.json").write_text(json.dumps({"known_anomalies": supporting["quality_cases"], "outcome_rule": "Each voluntary exit is sampled from a propensity computed from pre-cutoff synthetic engagement, workload and career drivers; the target horizon is 2026-07 through 2026-12. This is a synthetic label, not observed employee truth."}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (output / "edge_cases.csv").open("w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=["case_id", "issue_type", "employee_id", "expected_decision"])
        writer.writeheader()
        writer.writerows([{k: case[k] for k in writer.fieldnames} for case in supporting["quality_cases"]])
    reports = validate(tables, supporting["quality_cases"])
    (output / "validation_summary.json").write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "evaluation_metrics.json").write_text(json.dumps(evaluate(tables), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "feature_manifest.json").write_text(json.dumps({"feature_cutoff": FEATURE_CUTOFF, "included_sources": ["engagement_surveys", "workload_snapshots", "tenure_snapshots", "promotion_history"], "excluded_sources": ["attrition_outcomes", "interventions", "ground_truth.json"], "rules": ["only records dated on or before the feature cutoff are used", "missing survey values remain null and reduce confidence", "scores carry a human review requirement and are not employment decisions"]}, indent=2) + "\n", encoding="utf-8")
    with (output / "source_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        import csv
        writer = csv.writer(f); writer.writerow(["source", "version", "retrieved_date", "license", "transformation"])
        writer.writerow(["synthetic generator in this repository", "1.0.0", "N/A", "no external source", "deterministic seeded generation"])
    checksums = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "checksums.sha256").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
    return {"manifest": supporting["manifest"], "validation": reports, "checksums": checksums}

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from typing import Any

from .model import TABLES


def validate(tables: dict[str, list[dict[str, Any]]], quality_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    for name, columns in TABLES.items():
        ids = [row[columns[0]] for row in tables.get(name, [])]
        ok = len(ids) == len(set(ids))
        checks[f"{name}.primary_key_unique"] = ok
        if not ok: errors.append(f"{name}: duplicate primary key")

    def fk(child: str, field: str, parent: str, parent_field: str) -> bool:
        allowed = {r[parent_field] for r in tables[parent]}
        return all(r[field] in allowed for r in tables[child])
    relations = [
        ("employees", "role_id", "roles", "role_id"), ("employees", "team_id", "teams", "team_id"),
        ("tenure_snapshots", "employee_id", "employees", "employee_id"), ("tenure_snapshots", "role_id", "roles", "role_id"),
        ("tenure_snapshots", "team_id", "teams", "team_id"), ("tenure_snapshots", "band_id", "compensation_bands", "band_id"),
        ("engagement_surveys", "employee_id", "employees", "employee_id"), ("workload_snapshots", "employee_id", "employees", "employee_id"),
        ("promotion_history", "employee_id", "employees", "employee_id"), ("team_transfers", "employee_id", "employees", "employee_id"),
        ("team_transfers", "from_team_id", "teams", "team_id"), ("team_transfers", "to_team_id", "teams", "team_id"),
        ("attrition_outcomes", "employee_id", "employees", "employee_id"),
        ("interventions", "employee_id", "employees", "employee_id"), ("risk_scores", "employee_id", "employees", "employee_id"),
        ("intervention_events", "intervention_id", "interventions", "intervention_id"),
    ]
    for child, field, parent, parent_field in relations:
        ok = fk(child, field, parent, parent_field)
        checks[f"{child}.{field}_references_{parent}"] = ok
        if not ok: errors.append(f"{child}.{field}: orphan foreign key")

    employees = {e["employee_id"]: e for e in tables["employees"]}
    outcomes = {o["employee_id"]: o for o in tables["attrition_outcomes"]}
    cutoff = "2026-06-30"
    survey_ok = all((s["response_status"] == "missing" and s["engagement_score"] is None and s["manager_support_score"] is None and s["career_growth_score"] is None) or (s["response_status"] == "responded" and all(s[k] is not None and 1 <= s[k] <= 5 for k in ("engagement_score", "manager_support_score", "career_growth_score"))) for s in tables["engagement_surveys"])
    checks["survey_missingness_explicit_not_negative"] = survey_ok
    if not survey_ok: errors.append("survey response_status and values do not reconcile")

    outcome_ok = all((o["voluntary_attrition"] == 1 and o["termination_date"] is not None and "2026-07-01" <= o["termination_date"] <= "2026-12-31") or (o["voluntary_attrition"] == 0 and o["termination_date"] is None) for o in tables["attrition_outcomes"])
    checks["outcome_label_matches_termination_date"] = outcome_ok
    if not outcome_ok: errors.append("attrition outcome label/termination date mismatch")
    status_ok = all((employees[eid]["status"] == "voluntarily_exited") == bool(o["voluntary_attrition"]) for eid, o in outcomes.items())
    checks["employee_lifecycle_matches_outcome"] = status_ok
    if not status_ok: errors.append("employee lifecycle state disagrees with outcome")

    cutoff_ok = all(r["score_date"] == cutoff and r["human_review_required"] == 1 and bool(r["explanation"].strip()) for r in tables["risk_scores"])
    checks["score_date_explanation_human_review"] = cutoff_ok
    if not cutoff_ok: errors.append("risk score missing cutoff, explanation, or human review")
    # Histories can extend after the cutoff. Recompute each result through the
    # scorer to assert post-cutoff rows cannot alter the recorded feature score.
    from .scoring import score_all, score_one, safe_for_review
    expected_scores = score_all(tables, cutoff)
    checks["feature_cutoff_enforced_by_scoring"] = all(expected["risk_score"] == actual["risk_score"] and expected["explanation"] == actual["explanation"] for expected, actual in zip(expected_scores, tables["risk_scores"]))
    if not checks["feature_cutoff_enforced_by_scoring"]: errors.append("risk scores do not reconcile to cutoff-filtered source data")

    ranges_ok = all(0 <= w["hours_worked"] <= 400 and 0 <= w["overtime_hours"] <= 200 and 0 <= w["utilization_pct"] <= 150 for w in tables["workload_snapshots"])
    checks["workload_units_and_ranges"] = ranges_ok
    if not ranges_ok: errors.append("workload outside allowed units or range")
    hours_ok = all(abs((w["hours_worked"] - 160) - w["overtime_hours"]) <= 20 for w in tables["workload_snapshots"])
    checks["workload_hours_reconcile_to_overtime"] = hours_ok
    if not hours_ok: errors.append("hours worked and overtime do not reconcile")
    quarter_ok = len({(s["employee_id"], s["snapshot_quarter"]) for s in tables["tenure_snapshots"]}) == len(tables["tenure_snapshots"])
    checks["snapshot_employee_quarter_unique"] = quarter_ok
    if not quarter_ok: errors.append("duplicate employee-quarter snapshot")

    role_level = {r["role_id"]: r["level"] for r in tables["roles"]}
    band_level = {b["band_id"]: b["level"] for b in tables["compensation_bands"]}
    assignment_ok = all(role_level[s["role_id"]] == band_level[s["band_id"]] for s in tables["tenure_snapshots"])
    checks["snapshot_role_band_levels_reconcile"] = assignment_ok
    if not assignment_ok: errors.append("snapshot role and compensation band levels disagree")
    date_order_ok = all(date.fromisoformat(e["hire_date"]) <= date.fromisoformat(s["snapshot_month"] + "-01") for s in tables["tenure_snapshots"] for e in [employees[s["employee_id"]]])
    checks["hire_date_precedes_snapshots"] = date_order_ok
    if not date_order_ok: errors.append("snapshot precedes employee hire date")
    history_dates = [(row["employee_id"], row["snapshot_month"] + "-01") for entity in ("tenure_snapshots", "workload_snapshots") for row in tables[entity]] + [(row["employee_id"], row["survey_date"]) for row in tables["engagement_surveys"]]
    no_post_exit = all(not outcomes[eid]["voluntary_attrition"] or date.fromisoformat(record_date) <= date.fromisoformat(outcomes[eid]["termination_date"]) for eid, record_date in history_dates)
    checks["no_records_after_exit"] = no_post_exit
    if not no_post_exit: errors.append("history record exists after termination date")
    grouped_transfers: dict[str, list[dict[str, Any]]] = {}
    for tr in tables["team_transfers"]: grouped_transfers.setdefault(tr["employee_id"], []).append(tr)
    employee_current_team = {e["employee_id"]: e["team_id"] for e in tables["employees"]}
    snapshots_by_employee: dict[str, list[dict[str, Any]]] = {}
    for snap in tables["tenure_snapshots"]: snapshots_by_employee.setdefault(snap["employee_id"], []).append(snap)
    transfer_chain = True
    for employee_id, snapshots in snapshots_by_employee.items():
        snapshots.sort(key=lambda s: s["snapshot_month"])
        events = sorted(grouped_transfers.get(employee_id, []), key=lambda t: t["effective_date"])
        initial = snapshots[0]["team_id"]
        team = initial
        for event in events:
            if event["from_team_id"] != team or event["from_team_id"] == event["to_team_id"] or event["effective_date"] < "2025-01-01":
                transfer_chain = False
            team = event["to_team_id"]
        if employee_current_team[employee_id] != team:
            transfer_chain = False
        for snap in snapshots:
            expected = initial
            for event in events:
                if event["effective_date"] <= snap["snapshot_month"] + "-31": expected = event["to_team_id"]
            if snap["team_id"] != expected: transfer_chain = False
    checks["transfer_events_valid"] = transfer_chain
    if not transfer_chain: errors.append("invalid internal transfer event")
    intervention_dates = all(i["created_date"] >= cutoff and (i["closed_date"] is None or i["closed_date"] >= i["created_date"]) for i in tables["interventions"])
    checks["intervention_lifecycle_dates_valid"] = intervention_dates
    if not intervention_dates: errors.append("intervention lifecycle date ordering invalid")
    by_intervention: dict[str, list[dict[str, Any]]] = {}
    for event in tables["intervention_events"]: by_intervention.setdefault(event["intervention_id"], []).append(event)
    event_lifecycle_ok = True
    for intervention in tables["interventions"]:
        history = sorted(by_intervention.get(intervention["intervention_id"], []), key=lambda e: (e["event_date"], e["intervention_event_id"]))
        if not history or history[0]["from_status"] is not None or history[0]["to_status"] != "planned": event_lifecycle_ok = False
        for previous, current in zip(history, history[1:]):
            if previous["to_status"] != current["from_status"] or current["event_date"] < previous["event_date"]: event_lifecycle_ok = False
        if history and (history[-1]["to_status"] != intervention["status"] or history[-1]["simulated_outcome"] != intervention["simulated_outcome"]): event_lifecycle_ok = False
    checks["intervention_event_history_reconciles"] = event_lifecycle_ok
    if not event_lifecycle_ok: errors.append("intervention event history does not reconcile to current lifecycle record")

    anomalies_ok = {c["issue_type"] for c in (quality_cases or [])} == {"future_information_leak", "missing_survey_treated_as_negative", "outcome_label_date_inconsistent", "individual_score_without_explanation_or_human_review"}
    checks["labelled_negative_scenarios_present"] = anomalies_ok
    if not anomalies_ok: errors.append("required labelled exception scenarios missing")

    # Execute the four specified exception pathways against tiny isolated fixtures.
    fixture_id = "EMP-999999"
    fixture_tables = {
        "employees": [{"employee_id": fixture_id, "hire_date": "2020-01-01"}],
        "roles": [{"role_id": "ROL-T-1", "job_family": "Engineering"}],
        "tenure_snapshots": [{"employee_id": fixture_id, "snapshot_month": "2026-06", "tenure_months": 18, "role_id": "ROL-T-1"}],
        "engagement_surveys": [{"employee_id": fixture_id, "survey_date": cutoff, "response_status": "missing", "engagement_score": None, "manager_support_score": None, "career_growth_score": None}],
        "workload_snapshots": [{"employee_id": fixture_id, "snapshot_month": f"2026-{month:02d}", "overtime_hours": 2.0} for month in range(1, 7)],
        "promotion_history": [],
    }
    missing_result = score_one(fixture_id, fixture_tables, cutoff)
    missing_ok = missing_result["risk_score"] == 25 and missing_result["confidence"] == "low" and "no negative score was imputed" in missing_result["explanation"]
    checks["edge_missing_survey_is_unknown_and_lowers_confidence"] = missing_ok
    if not missing_ok: errors.append("missing survey exception did not stay neutral with lower confidence")

    before_future = score_one(fixture_id, fixture_tables, cutoff)
    leaked = deepcopy(fixture_tables)
    leaked["engagement_surveys"].append({"employee_id": fixture_id, "survey_date": "2026-09-30", "response_status": "responded", "engagement_score": 1, "manager_support_score": 1, "career_growth_score": 1})
    leaked["workload_snapshots"].append({"employee_id": fixture_id, "snapshot_month": "2026-09", "overtime_hours": 30.0})
    after_future = score_one(fixture_id, leaked, cutoff)
    future_ok = before_future["risk_score"] == after_future["risk_score"] and before_future["explanation"] == after_future["explanation"]
    checks["edge_future_features_do_not_change_score"] = future_ok
    if not future_ok: errors.append("future-dated feature leak changed the score")

    inconsistent = {"voluntary_attrition": 0, "termination_date": "2026-09-30"}
    case3_rejected = not ((inconsistent["voluntary_attrition"] == 1 and inconsistent["termination_date"] is not None) or (inconsistent["voluntary_attrition"] == 0 and inconsistent["termination_date"] is None))
    checks["edge_inconsistent_outcome_label_rejected"] = case3_rejected
    if not case3_rejected: errors.append("inconsistent outcome label exception was not rejected")

    unsafe_score = {"explanation": "", "human_review_required": 0, "decision_guardrail": ""}
    case4_blocked = not safe_for_review(unsafe_score)
    checks["edge_unsupported_individual_score_blocked"] = case4_blocked
    if not case4_blocked: errors.append("score without explanation and review was not blocked")

    attrition_count = sum(o["voluntary_attrition"] for o in tables["attrition_outcomes"])
    rate = attrition_count / max(1, len(tables["attrition_outcomes"]))
    checks["attrition_rate_in_5_to_15_percent"] = .05 <= rate <= .15
    if tables["attrition_outcomes"] and not checks["attrition_rate_in_5_to_15_percent"]:
        errors.append(f"synthetic attrition rate {rate:.3%} falls outside 5%-15%; adjust cohort size/seed")
    return {
        "passed": not errors,
        "checks_run": len(checks),
        "checks": checks,
        "errors": errors,
        "entity_row_counts": {name: len(rows) for name, rows in tables.items()},
        "attrition_rate": round(rate, 4),
        "notes": ["Future-dated history is stored as outcomes/history but excluded by the scorer's cutoff filters.", "Synthetic QA fixtures are separate from input features and are not used for scoring."],
    }

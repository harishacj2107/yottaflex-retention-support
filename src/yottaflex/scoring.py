from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any


def score_one(employee_id: str, tables: dict[str, list[dict[str, Any]]], cutoff: str) -> dict[str, Any]:
    """Explainable rules using only dated features at or before the cutoff."""
    surveys = sorted((s for s in tables["engagement_surveys"] if s["employee_id"] == employee_id and s["survey_date"] <= cutoff), key=lambda s: s["survey_date"])
    recent_records = surveys[-2:]
    recent_surveys = [s for s in recent_records if s["response_status"] == "responded"]
    workloads = sorted((w for w in tables["workload_snapshots"] if w["employee_id"] == employee_id and w["snapshot_month"] <= cutoff[:7]), key=lambda w: w["snapshot_month"])
    recent_workloads = workloads[-6:]
    snapshots = [s for s in tables["tenure_snapshots"] if s["employee_id"] == employee_id and s["snapshot_month"] <= cutoff[:7]]
    last_snapshot = max(snapshots, key=lambda s: s["snapshot_month"])
    role = next(r for r in tables["roles"] if r["role_id"] == last_snapshot["role_id"])
    promotions = [p for p in tables["promotion_history"] if p["employee_id"] == employee_id and p["effective_date"] <= cutoff]
    reasons: list[str] = []
    score = 25

    if recent_surveys:
        latest = recent_surveys[-1]
        if latest["engagement_score"] is not None and latest["engagement_score"] <= 2:
            score += 18; reasons.append("recent engagement rating is low")
        elif latest["engagement_score"] is not None and latest["engagement_score"] <= 3:
            score += 9; reasons.append("recent engagement rating is below the positive range")
        if latest["manager_support_score"] is not None and latest["manager_support_score"] <= 2:
            score += 12; reasons.append("reported manager support is low")
        if latest["career_growth_score"] is not None and latest["career_growth_score"] <= 2:
            score += 13; reasons.append("reported career growth is low")
        if len(recent_surveys) == 2:
            prior, latest = recent_surveys
            if prior["engagement_score"] is not None and latest["engagement_score"] is not None:
                delta = latest["engagement_score"] - prior["engagement_score"]
                if delta <= -2:
                    score += 15; reasons.append("engagement declined by at least two scale points")
                elif delta == -1:
                    score += 7; reasons.append("engagement declined by one scale point")
    if not recent_surveys:
        reasons.append("no recent survey response; no negative score was imputed")
    elif recent_records and recent_records[-1]["response_status"] == "missing":
        reasons.append("latest survey is missing; no negative score was imputed")

    if recent_workloads:
        avg_ot = sum(w["overtime_hours"] for w in recent_workloads) / len(recent_workloads)
        role_baseline = {"Engineering": 12, "Operations": 13, "Customer Success": 10, "Product": 11, "Finance": 9}.get(role["job_family"], 11)
        if avg_ot >= role_baseline + 4:
            score += 17; reasons.append("sustained overtime is elevated")
        elif avg_ot >= role_baseline:
            score += 10; reasons.append(f"recent overtime is above the {role['job_family']} review threshold")
        if len(recent_workloads) >= 4:
            prior_avg = sum(w["overtime_hours"] for w in recent_workloads[:-3]) / max(1, len(recent_workloads[:-3]))
            last_avg = sum(w["overtime_hours"] for w in recent_workloads[-3:]) / 3
            if last_avg - prior_avg >= 5:
                score += 8; reasons.append("overtime has increased recently")

    months_since_promotion = 999
    if promotions:
        latest_promotion = max(promotions, key=lambda p: p["effective_date"])
        p_date = date.fromisoformat(latest_promotion["effective_date"])
        c_date = date.fromisoformat(cutoff)
        months_since_promotion = (c_date.year - p_date.year) * 12 + c_date.month - p_date.month
    else:
        hired_date = date.fromisoformat(next(e["hire_date"] for e in tables["employees"] if e["employee_id"] == employee_id))
        cutoff_date = date.fromisoformat(cutoff)
        months_since_promotion = (cutoff_date.year - hired_date.year) * 12 + cutoff_date.month - hired_date.month
    if last_snapshot["tenure_months"] >= 24 and months_since_promotion >= 48:
        score += 8; reasons.append("long time since the last recorded promotion; ask about growth interests")

    score = min(100, score)
    priority = "priority" if score >= 60 else "monitor" if score >= 40 else "no_signal"
    survey_coverage = len(recent_surveys)
    latest_responded = bool(recent_records and recent_records[-1]["response_status"] == "responded")
    confidence = "high" if survey_coverage >= 2 and latest_responded and len(recent_workloads) >= 6 else "medium" if survey_coverage >= 1 and len(recent_workloads) >= 3 else "low"
    return {
        "employee_id": employee_id,
        "score_date": cutoff,
        "risk_score": score,
        "priority_band": priority,
        "confidence": confidence,
        "explanation": "; ".join(reasons) if reasons else "no rule threshold crossed; continue routine supportive check-ins",
        "human_review_required": 1,
        "decision_guardrail": "supportive conversation cue only; never an automated employment decision",
    }


def score_all(tables: dict[str, list[dict[str, Any]]], cutoff: str) -> list[dict[str, Any]]:
    # Index once instead of rescanning the full history for every employee.
    indexed: dict[str, dict[str, list[dict[str, Any]]]] = {
        name: defaultdict(list) for name in ("engagement_surveys", "workload_snapshots", "tenure_snapshots", "promotion_history")
    }
    for name, by_employee in indexed.items():
        for row in tables[name]: by_employee[row["employee_id"]].append(row)
    output = []
    for employee in tables["employees"]:
        employee_id = employee["employee_id"]
        view = {"employees": [employee], "roles": tables["roles"]}
        for name, by_employee in indexed.items(): view[name] = by_employee[employee_id]
        output.append(score_one(employee_id, view, cutoff))
    return output


def safe_for_review(row: dict[str, Any]) -> bool:
    """Fail closed when an individual score lacks rationale or human review."""
    return bool(str(row.get("explanation", "")).strip()) and str(row.get("human_review_required", "0")) == "1" and "not an automated employment decision" in str(row.get("decision_guardrail", ""))


def evaluate(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Evaluate a temporal holdout: pre-cutoff scores vs later outcome horizon."""
    outcomes = {o["employee_id"]: o["voluntary_attrition"] for o in tables["attrition_outcomes"]}
    scores = [s for s in tables["risk_scores"] if int(s["employee_id"][-6:]) % 5 == 0]
    pairs = [(s["risk_score"], outcomes[s["employee_id"]]) for s in scores]
    n = len(pairs)
    positives = sum(y for _, y in pairs)
    k = max(1, round(n * .20)) if n else 0
    ranked = sorted(scores, key=lambda s: (-s["risk_score"], s["employee_id"]))[:k]
    top_pos = sum(outcomes[s["employee_id"]] for s in ranked)
    prevalence = positives / n if n else 0.0
    # Mann–Whitney form of ROC AUC, with average ranks for ties.
    ordered = sorted(pairs, key=lambda pair: pair[0])
    rank_sum = 0.0; i = 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][0] == ordered[i][0]: j += 1
        avg_rank = (i + 1 + j) / 2
        rank_sum += avg_rank * sum(y for _, y in ordered[i:j])
        i = j
    auc = (rank_sum - positives * (positives + 1) / 2) / (positives * (n - positives)) if positives and positives < n else None
    return {
        "evaluation_type": "temporal holdout; score uses records through 2026-06-30 and target uses 2026-07-01 through 2026-12-31",
        "split_rule": "employee_id numeric suffix divisible by 5 (20% holdout); deterministic cohort split",
        "held_out_employee_count": n,
        "holdout_attrition_count": positives,
        "holdout_prevalence": round(prevalence, 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "precision_at_top_20pct": round(top_pos / k, 4) if k else None,
        "recall_at_top_20pct": round(top_pos / positives, 4) if positives else None,
        "lift_at_top_20pct": round((top_pos / k) / prevalence, 4) if k and prevalence else None,
        "interpretation": "Synthetic internal evaluation only; rule prioritization is not a validated employment prediction model and must not determine employment outcomes.",
    }

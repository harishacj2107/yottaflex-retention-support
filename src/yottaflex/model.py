from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


TABLES: dict[str, list[str]] = {
    "roles": ["role_id", "role_name", "job_family", "level", "active"],
    "teams": ["team_id", "team_name", "function", "active"],
    "employees": ["employee_id", "role_id", "team_id", "hire_date", "initial_level", "status", "synthetic"],
    "compensation_bands": ["band_id", "level", "currency", "min_annual", "max_annual", "effective_from", "effective_to"],
    "tenure_snapshots": ["snapshot_id", "employee_id", "snapshot_quarter", "snapshot_month", "tenure_months", "role_id", "team_id", "band_id", "employment_status"],
    "engagement_surveys": ["survey_id", "employee_id", "survey_date", "quarter", "engagement_score", "manager_support_score", "career_growth_score", "response_status"],
    "workload_snapshots": ["workload_id", "employee_id", "snapshot_month", "hours_worked", "overtime_hours", "utilization_pct", "benign_peak"],
    "promotion_history": ["promotion_id", "employee_id", "effective_date", "from_level", "to_level", "reason"],
    "team_transfers": ["transfer_id", "employee_id", "effective_date", "from_team_id", "to_team_id", "reason"],
    "attrition_outcomes": ["outcome_id", "employee_id", "feature_cutoff", "horizon_end", "voluntary_attrition", "termination_date", "label_rule"],
    "interventions": ["intervention_id", "employee_id", "created_date", "intervention_type", "priority_band", "status", "simulated_outcome", "closed_date"],
    "intervention_events": ["intervention_event_id", "intervention_id", "event_date", "from_status", "to_status", "simulated_outcome"],
    "risk_scores": ["employee_id", "score_date", "risk_score", "priority_band", "confidence", "explanation", "human_review_required", "decision_guardrail"],
}

TABLE_SQL: dict[str, str] = {
    "roles": "role_id TEXT PRIMARY KEY, role_name TEXT NOT NULL, job_family TEXT NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5), active INTEGER NOT NULL CHECK(active IN (0,1))",
    "teams": "team_id TEXT PRIMARY KEY, team_name TEXT NOT NULL, function TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1))",
    "employees": "employee_id TEXT PRIMARY KEY, role_id TEXT NOT NULL REFERENCES roles(role_id), team_id TEXT NOT NULL REFERENCES teams(team_id), hire_date TEXT NOT NULL, initial_level INTEGER NOT NULL CHECK(initial_level BETWEEN 1 AND 5), status TEXT NOT NULL CHECK(status IN ('active','voluntarily_exited')), synthetic INTEGER NOT NULL CHECK(synthetic=1)",
    "compensation_bands": "band_id TEXT PRIMARY KEY, level INTEGER NOT NULL UNIQUE CHECK(level BETWEEN 1 AND 5), currency TEXT NOT NULL CHECK(currency='USD'), min_annual INTEGER NOT NULL, max_annual INTEGER NOT NULL CHECK(max_annual>min_annual), effective_from TEXT NOT NULL, effective_to TEXT",
    "tenure_snapshots": "snapshot_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), snapshot_quarter TEXT NOT NULL, snapshot_month TEXT NOT NULL, tenure_months INTEGER NOT NULL CHECK(tenure_months>=0), role_id TEXT NOT NULL REFERENCES roles(role_id), team_id TEXT NOT NULL REFERENCES teams(team_id), band_id TEXT NOT NULL REFERENCES compensation_bands(band_id), employment_status TEXT NOT NULL CHECK(employment_status='active'), UNIQUE(employee_id,snapshot_quarter)",
    "engagement_surveys": "survey_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), survey_date TEXT NOT NULL, quarter TEXT NOT NULL, engagement_score INTEGER CHECK(engagement_score BETWEEN 1 AND 5), manager_support_score INTEGER CHECK(manager_support_score BETWEEN 1 AND 5), career_growth_score INTEGER CHECK(career_growth_score BETWEEN 1 AND 5), response_status TEXT NOT NULL CHECK(response_status IN ('responded','missing'))",
    "workload_snapshots": "workload_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), snapshot_month TEXT NOT NULL, hours_worked REAL NOT NULL CHECK(hours_worked BETWEEN 0 AND 400), overtime_hours REAL NOT NULL CHECK(overtime_hours BETWEEN 0 AND 200), utilization_pct REAL NOT NULL CHECK(utilization_pct BETWEEN 0 AND 150), benign_peak INTEGER NOT NULL CHECK(benign_peak IN (0,1)), UNIQUE(employee_id,snapshot_month)",
    "promotion_history": "promotion_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), effective_date TEXT NOT NULL, from_level INTEGER NOT NULL, to_level INTEGER NOT NULL CHECK(to_level=from_level+1), reason TEXT NOT NULL",
    "team_transfers": "transfer_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), effective_date TEXT NOT NULL, from_team_id TEXT NOT NULL REFERENCES teams(team_id), to_team_id TEXT NOT NULL REFERENCES teams(team_id), reason TEXT NOT NULL CHECK(reason='internal_transfer')",
    "attrition_outcomes": "outcome_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL UNIQUE REFERENCES employees(employee_id), feature_cutoff TEXT NOT NULL, horizon_end TEXT NOT NULL, voluntary_attrition INTEGER NOT NULL CHECK(voluntary_attrition IN (0,1)), termination_date TEXT, label_rule TEXT NOT NULL",
    "interventions": "intervention_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id), created_date TEXT NOT NULL, intervention_type TEXT NOT NULL, priority_band TEXT NOT NULL CHECK(priority_band IN ('priority','monitor')), status TEXT NOT NULL CHECK(status IN ('planned','completed','declined','no_response')), simulated_outcome TEXT NOT NULL CHECK(simulated_outcome IN ('supportive_response','no_change','declined','pending')), closed_date TEXT",
    "intervention_events": "intervention_event_id TEXT PRIMARY KEY, intervention_id TEXT NOT NULL REFERENCES interventions(intervention_id), event_date TEXT NOT NULL, from_status TEXT CHECK(from_status IS NULL OR from_status IN ('planned','completed','declined','no_response')), to_status TEXT NOT NULL CHECK(to_status IN ('planned','completed','declined','no_response')), simulated_outcome TEXT NOT NULL CHECK(simulated_outcome IN ('supportive_response','no_change','declined','pending'))",
    "risk_scores": "employee_id TEXT PRIMARY KEY REFERENCES employees(employee_id), score_date TEXT NOT NULL, risk_score INTEGER NOT NULL CHECK(risk_score BETWEEN 0 AND 100), priority_band TEXT NOT NULL CHECK(priority_band IN ('priority','monitor','no_signal')), confidence TEXT NOT NULL CHECK(confidence IN ('high','medium','low')), explanation TEXT NOT NULL, human_review_required INTEGER NOT NULL CHECK(human_review_required=1), decision_guardrail TEXT NOT NULL",
}


def write_rows(directory: Path, tables: dict[str, list[dict[str, Any]]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, columns in TABLES.items():
        rows = tables.get(name, [])
        with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        with (directory / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def write_sqlite(path: Path, tables: dict[str, list[dict[str, Any]]]) -> None:
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        for name, definition in TABLE_SQL.items():
            db.execute(f"CREATE TABLE {name} ({definition})")
        for name, columns in TABLES.items():
            rows = tables.get(name, [])
            if rows:
                placeholders = ",".join("?" for _ in columns)
                sql = f"INSERT INTO {name} ({','.join(columns)}) VALUES ({placeholders})"
                db.executemany(sql, [[row.get(column) for column in columns] for row in rows])
        db.commit()
    finally:
        db.close()


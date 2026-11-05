# Data dictionary

The exports use UTF-8, comma-separated headers, ISO dates, `1`/`0` booleans, and blank cells for optional values. Each table has the primary key marked **PK**; foreign-key fields are marked **FK**. SQLite contains matching type, enum, range, uniqueness, and relationship constraints where practical. Numeric survey units are 1–5 response points; workload hours and utilization are explicit. There are no sensitive demographic fields.

## Role

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `role_id` | string | yes | `ROL-<family>-<level>` | PK | Stable role key; references used by employees and snapshots must exist. |
| `role_name` | string | yes | Synthetic job title | no | Non-empty. |
| `job_family` | string | yes | Engineering, Operations, Customer Success, Product, Finance | no | Must be a generated family. |
| `level` | integer | yes | 1–5 | no | Role seniority range. |
| `active` | boolean integer | yes | 0 or 1 | no | Must be boolean. |

## Team

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `team_id` | string | yes | `TEAM-001`… | PK | Referenced team exists. |
| `team_name` | string | yes | Synthetic team label | no | Non-empty. |
| `function` | string | yes | Generated function list | no | Non-empty. |
| `active` | boolean integer | yes | 0 or 1 | no | Must be boolean. |

## Employee

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `employee_id` | string | yes | `EMP-000001` | PK | Immutable, six-digit zero-padded counter. |
| `role_id` | string | yes | Role key | no | FK to `Role.role_id`. |
| `team_id` | string | yes | Team key | no | FK to `Team.team_id`; final known assignment. |
| `hire_date` | date | yes | ISO date | no | Before first cohort snapshot. |
| `initial_level` | integer | yes | 1–5 | no | Valid role level. |
| `status` | string | yes | `active`, `voluntarily_exited` | no | Must reconcile to outcome label. |
| `synthetic` | boolean integer | yes | Always 1 | no | Prevents mistaken real-data interpretation. |

## TenureSnapshot

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `snapshot_id` | string | yes | `SNAP-<employee-id>-YYYYQn` | PK | Deterministic from employee and quarter. |
| `employee_id` | string | yes | Employee key | no | FK; employee-quarter pair unique. |
| `snapshot_quarter` | string | yes | `2025Q1`…`2026Q4` | no | Valid cohort quarter. |
| `snapshot_month` | string | yes | `YYYY-MM` quarter-end month | no | Must agree with quarter. |
| `tenure_months` | integer | yes | Months | no | Non-negative; derived from hire date and snapshot month. |
| `role_id` | string | yes | Role key | no | FK; assignment at this effective time. |
| `team_id` | string | yes | Team key | no | FK; assignment at this effective time. |
| `band_id` | string | yes | Compensation band key | no | FK; level agrees with the snapshot role. |
| `employment_status` | string | yes | `active` | no | Snapshot must not be later than exit. |

## EngagementSurvey

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `survey_id` | string | yes | `SURV-YYYY-000001` | PK | Global zero-padded counter. |
| `employee_id` | string | yes | Employee key | no | FK. |
| `survey_date` | date | yes | ISO date | no | Quarter-end date; no survey after exit. |
| `quarter` | string | yes | `YYYYQn` | no | Must agree with survey date. |
| `engagement_score` | nullable integer | conditional | 1–5 points | no | Required for responded; null for missing. |
| `manager_support_score` | nullable integer | conditional | 1–5 points | no | Required for responded; null for missing. |
| `career_growth_score` | nullable integer | conditional | 1–5 points | no | Required for responded; null for missing. |
| `response_status` | string | yes | `responded`, `missing` | no | Scores all null if missing; all valid if responded. |

## WorkloadSnapshot

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `workload_id` | string | yes | `LOAD-<employee-id>-YYYYMM` | PK | Deterministic employee-month key. |
| `employee_id` | string | yes | Employee key | no | FK; employee-month pair unique. |
| `snapshot_month` | string | yes | `YYYY-MM` | no | In 24-month cohort and not after exit. |
| `hours_worked` | decimal | yes | Hours/month, 0–400 | no | Reconciles to baseline hours plus overtime within documented noise tolerance. |
| `overtime_hours` | decimal | yes | Hours/month, 0–200 | no | Non-negative and within range. |
| `utilization_pct` | decimal | yes | Percent, 0–150 | no | Within range. |
| `benign_peak` | boolean integer | yes | 0 or 1 | no | Marks an intentionally benign high-workload period. |

## CompensationBand

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `band_id` | string | yes | `BAND-L1`…`BAND-L5` | PK | Stable level band key. |
| `level` | integer | yes | 1–5 | unique | One band per level. |
| `currency` | string | yes | `USD` | no | ISO currency code. |
| `min_annual` | integer | yes | Annual salary units | no | Greater than zero and below maximum. |
| `max_annual` | integer | yes | Annual salary units | no | Greater than minimum. |
| `effective_from` | date | yes | ISO date | no | No later than snapshot use. |
| `effective_to` | nullable date | no | ISO date or blank | no | If present, later than effective-from. |

## PromotionHistory

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `promotion_id` | string | yes | `PROM-000001` | PK | Immutable global counter. |
| `employee_id` | string | yes | Employee key | no | FK. |
| `effective_date` | date | yes | ISO date | no | Within cohort and before snapshots that show new role. |
| `from_level` | integer | yes | 1–4 | no | Existing level. |
| `to_level` | integer | yes | `from_level + 1` | no | Higher level, max 5. |
| `reason` | string | yes | `career_progression` | no | Allowed event reason. |

## TeamTransfer (additional event entity)

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `transfer_id` | string | yes | `XFER-000001` | PK | Immutable global counter. |
| `employee_id` | string | yes | Employee key | no | FK. |
| `effective_date` | date | yes | ISO date | no | Within cohort; no later than last eligible snapshot. |
| `from_team_id` | string | yes | Team key | no | FK; must match prior assignment. |
| `to_team_id` | string | yes | Team key | no | FK; must differ from source team. |
| `reason` | string | yes | `internal_transfer` | no | Allowed event reason. |

## AttritionOutcome

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `outcome_id` | string | yes | `OUT-<employee-id>-2026` | PK | Deterministic employee-year key. |
| `employee_id` | string | yes | Employee key | unique | FK; exactly one outcome per employee. |
| `feature_cutoff` | date | yes | `2026-06-30` | no | Features stop here. |
| `horizon_end` | date | yes | `2026-12-31` | no | Later than cutoff. |
| `voluntary_attrition` | boolean integer | yes | 0 or 1 | no | Derived from generated termination event. |
| `termination_date` | nullable date | conditional | Future horizon or blank | no | Present iff attrition=1 and between cutoff and horizon. |
| `label_rule` | string | yes | Documented generator rule ID | no | Identifies seeded driver-based propensity rule. |

## Intervention

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `intervention_id` | string | yes | `INT-2026-000001` | PK | Immutable global zero-padded counter. |
| `employee_id` | string | yes | Employee key | no | FK. |
| `created_date` | date | yes | ISO date | no | At/after feature cutoff. |
| `intervention_type` | string | yes | `manager_supportive_check_in` | no | Supportive, non-disciplinary action. |
| `priority_band` | string | yes | `priority`, `monitor` | no | From reviewed score queue. |
| `status` | string | yes | `planned`, `completed`, `declined`, `no_response` | no | Valid lifecycle state. |
| `simulated_outcome` | string | yes | `pending`, `supportive_response`, `no_change`, `declined` | no | Illustrative only; not causal evidence. |
| `closed_date` | nullable date | no | ISO date or blank | no | Required for closed states; not before creation. |

## InterventionEvent (append-only lifecycle event)

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `intervention_event_id` | string | yes | `IEVT-2026-000001` | PK | Immutable global zero-padded counter. |
| `intervention_id` | string | yes | Intervention key | no | FK to `Intervention.intervention_id`. |
| `event_date` | date | yes | ISO date | no | At or after intervention creation; nondecreasing within history. |
| `from_status` | nullable string | conditional | Blank for creation, otherwise lifecycle status | no | Must equal prior event's `to_status`. |
| `to_status` | string | yes | `planned`, `completed`, `declined`, `no_response` | no | Allowed transition state. |
| `simulated_outcome` | string | yes | `pending`, `supportive_response`, `no_change`, `declined` | no | Final event must reconcile with intervention summary. |

## RiskScore (derived review artifact)

| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| `employee_id` | string | yes | Employee key | PK/FK | Exactly one score per employee. |
| `score_date` | date | yes | `2026-06-30` | no | Feature cutoff exactly. |
| `risk_score` | integer | yes | 0–100 points | no | Recomputed from documented rule factors. |
| `priority_band` | string | yes | `priority`, `monitor`, `no_signal` | no | Derived from thresholds 60 and 40. |
| `confidence` | string | yes | `high`, `medium`, `low` | no | Based on survey coverage and workload coverage. |
| `explanation` | string | yes | Human-readable factor list | no | Must not be blank. |
| `human_review_required` | boolean integer | yes | Always 1 | no | Mandatory safeguard. |
| `decision_guardrail` | string | yes | Supportive-use disclaimer | no | Must state not an automated employment decision. |

# Schema and relationships

All primary keys are immutable strings. Date fields use ISO `YYYY-MM-DD`; month keys use `YYYY-MM`; quarter keys use `YYYYQn`. The cohort spans January 2025 through December 2026. Snapshots, surveys, and event histories are append-only generated records. A transfer or promotion adds an event and affects later snapshots; prior snapshots are retained.

| Parent | Child | Cardinality | Optionality and rule |
|---|---|---|---|
| Role | Employee | 1:N | Each employee has one current role; role is required. |
| Team | Employee | 1:N | Each employee has one current team; team is required. |
| Employee | TenureSnapshot | 1:N | Eight quarterly snapshots maximum; employees who exit have no later snapshots. |
| Role, Team, CompensationBand | TenureSnapshot | each 1:N | Required effective assignment references for each snapshot. |
| Employee | EngagementSurvey | 1:N | Quarterly survey event; survey response is optional and missingness is explicit. |
| Employee | WorkloadSnapshot | 1:N | Monthly history; no row after exit. |
| Employee | PromotionHistory | 1:N | Zero or more dated promotion events. |
| Employee | TeamTransfer | 1:N | Zero or more dated internal transfer events with from/to teams. |
| Employee | AttritionOutcome | 1:1 | One future-horizon label per employee; termination date is optional for a non-exit. |
| Employee | Intervention | 1:N | Zero or more supportive intervention lifecycle records. |
| Intervention | InterventionEvent | 1:N | Append-only status transitions such as planned to completed. |
| Employee | RiskScore | 1:1 | One score at the documented feature cutoff. |

There are no many-to-many relationships in this synthetic workflow, so no bridge table is required. All relationships are enforced by SQLite foreign keys and checked by the generator's validation report.

## IDs and states

- Employee: `EMP-000001`.
- Tenure snapshot: `SNAP-EMP-000001-2026Q1`.
- Survey: `SURV-2026-000001`.
- Intervention: `INT-2026-000001`.
- Outcome: `OUT-EMP-000001-2026`.
- Other immutable event IDs use `LOAD-`, `PROM-`, `XFER-`, and `IEVT-` prefixes.
- Employee state is `active` or `voluntarily_exited`; intervention state is `planned`, `completed`, `declined`, or `no_response`. Simulated outcome is `pending`, `supportive_response`, `no_change`, or `declined`.

## Lifecycle and derived values

Every employee gets one outcome row. A positive label requires a termination date in the future horizon; a negative label requires no termination date. Employee status reconciles to that label. Survey score fields are nullable only when `response_status=missing`; missing is not a low score. Risk scores are recomputed from dated survey, workload, tenure, role, and promotion source rows. Interventions are created from the score queue and never change a score or outcome label. Intervention state changes are appended as `InterventionEvent` rows. Labelled negative scenarios are held in separate QA artifacts, not mixed into normal input rows.
